"""Adapter and deterministic graph builder for already-ingested vault books."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from hermes_memory_os.utils import now_iso

from .config import GraphConfig
from .ids import claim_id, chunk_id, document_id, entity_id, evidence_id, relationship_id
from .source_integrity import validate_book_artifacts


class BookDiscoveryError(ValueError):
    """Raised when an existing book does not expose the required ingestion artifacts."""


@dataclass(frozen=True)
class BookArtifacts:
    source_id: str
    title: str
    authors: tuple[str, ...]
    checksum: str
    raw_path: Path
    raw_relative_path: str
    manifest_path: Path
    synthesis_path: Path
    retrieval_chunks_path: Path
    chunks: tuple[dict[str, Any], ...]
    concepts: tuple[str, ...]
    claims: tuple[str, ...]


def discover_book(vault_root: Path, source_id: str) -> BookArtifacts:
    source_page = _find_source_page(vault_root, source_id)
    synthesis_frontmatter, synthesis_body = _read_frontmatter(source_page)
    raw_manifest = _find_manifest(vault_root, source_id)
    manifest, _ = _read_frontmatter(raw_manifest)
    raw_relative_path = str(manifest.get("source_path") or manifest.get("original_path") or "")
    raw_path = vault_root / raw_relative_path
    if not raw_relative_path or not raw_path.is_file():
        raise BookDiscoveryError(f"Missing immutable raw source for {source_id}: {raw_path}")
    retrieval_chunks_path = vault_root / "06_GENERATED" / "source-analysis" / source_id / "retrieval-chunks.md"
    if not retrieval_chunks_path.is_file():
        raise BookDiscoveryError(f"Missing generated retrieval chunks for {source_id}: {retrieval_chunks_path}")

    chunks = _parse_retrieval_chunks(retrieval_chunks_path)
    if not chunks:
        raise BookDiscoveryError(f"No chunk metadata found in {retrieval_chunks_path}")
    for required in ("chunk_id", "chunk_index", "section"):
        if any(not str(chunk.get(required, "")).strip() for chunk in chunks):
            raise BookDiscoveryError(f"Chunk metadata is missing required field: {required}")

    title = str(synthesis_frontmatter.get("title") or manifest.get("title") or source_id)
    authors = _authors(synthesis_frontmatter.get("authors") or manifest.get("authors") or manifest.get("author"))
    concepts = tuple(str(item) for item in synthesis_frontmatter.get("key_concepts") or [])
    claims = tuple(_parse_claims(synthesis_body))
    if not claims:
        raise BookDiscoveryError(f"No reviewed source claims found in {source_page}")

    return BookArtifacts(
        source_id=source_id,
        title=title,
        authors=authors,
        checksum=str(manifest.get("content_hash") or _sha256(raw_path.read_text(encoding="utf-8"))),
        raw_path=raw_path,
        raw_relative_path=raw_relative_path,
        manifest_path=raw_manifest,
        synthesis_path=source_page,
        retrieval_chunks_path=retrieval_chunks_path,
        chunks=tuple(sorted(chunks, key=lambda item: int(item["chunk_index"]))),
        concepts=concepts,
        claims=claims,
    )


class GraphBookBuilder:
    """Builds a reversible plan from human-reviewed book artifacts."""

    extractor_name = "hermes-graph:deterministic-v1"

    def __init__(self, config: GraphConfig):
        self.config = config

    def build(
        self,
        source_id: str,
        *,
        write_mode: str = "dry_run",
        qdrant_crosswalk: dict[str, str] | None = None,
        client: Any | None = None,
    ) -> dict[str, Any]:
        if write_mode not in {"dry_run", "upsert"}:
            raise ValueError("write_mode must be dry_run or upsert")
        artifacts = discover_book(self.config.vault_root, source_id)
        integrity = validate_book_artifacts(artifacts)
        if write_mode == "upsert" and not integrity["safe_for_neo4j_book_upsert"]:
            raise BookDiscoveryError(
                "Book graph upsert blocked by source-integrity validation: "
                + ", ".join(integrity["problems"])
            )
        plan = _GraphPlan(self.extractor_name)
        if not integrity["safe_for_neo4j_book_upsert"]:
            plan.warn("source_integrity_blocked:" + ",".join(integrity["problems"]))
        self._plan_book(plan, artifacts, qdrant_crosswalk or {})
        report = {
            "source_id": artifacts.source_id,
            "title": artifacts.title,
            "write_mode": write_mode,
            "status": "planned",
            "generated_at": now_iso(),
            "stats": plan.stats(),
            "warnings": plan.warnings,
            "source_integrity": integrity,
        }
        if write_mode == "upsert":
            if client is None:
                raise ValueError("Neo4j client is required for upsert mode")
            report["write_result"] = client.upsert(plan.nodes(), plan.relationships())
            report["status"] = "upserted"
        return {**report, "plan": plan.as_dict()}

    def _plan_book(self, plan: "_GraphPlan", book: BookArtifacts, crosswalk: dict[str, str]) -> None:
        created_at = now_iso()
        raw_document_id = document_id(book.source_id, book.raw_relative_path)
        synthesis_document_id = document_id(book.source_id, _relative(self.config.vault_root, book.synthesis_path))
        book_entity_id = entity_id("book", book.title)

        plan.node(
            "Source",
            book.source_id,
            {
                "source_type": "book",
                "title": book.title,
                "uri": book.raw_relative_path,
                "checksum": book.checksum,
                "created_at": created_at,
                "updated_at": created_at,
                "source_authority": "primary",
                # A successful upsert is source-integrity gated before this plan is written.
                "graph_status": "active",
                "vault_path": _relative(self.config.vault_root, book.raw_path),
            },
        )
        plan.node(
            "Document",
            raw_document_id,
            {
                "source_id": book.source_id,
                "title": book.title,
                "document_type": "book",
                "uri": book.raw_relative_path,
            },
        )
        plan.node(
            "Document",
            synthesis_document_id,
            {
                "source_id": book.source_id,
                "title": f"{book.title} source synthesis",
                "document_type": "note",
                "uri": _relative(self.config.vault_root, book.synthesis_path),
                "source_authority": "derived",
            },
        )
        plan.node(
            "Entity",
            book_entity_id,
            {
                "canonical_name": book.title,
                "entity_type": "book",
                "created_at": created_at,
                "updated_at": created_at,
                "resolution_status": "canonical",
                "home_vault_path": _relative(self.config.vault_root, book.synthesis_path),
                "confidence": 1.0,
            },
        )

        chunk_ids: list[str] = []
        chunk_evidence: dict[str, str] = {}
        for chunk in book.chunks:
            text_hash = _sha256(json.dumps(chunk, sort_keys=True))
            graph_chunk_id = chunk_id(raw_document_id, int(chunk["chunk_index"]), text_hash)
            chunk_ids.append(graph_chunk_id)
            point_id = crosswalk.get(str(chunk["chunk_id"]))
            metadata_quote = (
                f"Reviewed retrieval chunk {chunk['chunk_id']} covers sections {chunk['section']} "
                f"of {book.title}."
            )
            metadata_evidence_id = evidence_id(graph_chunk_id, 0, len(metadata_quote), metadata_quote)
            chunk_evidence[graph_chunk_id] = metadata_evidence_id
            plan.node(
                "Chunk",
                graph_chunk_id,
                {
                    "source_id": book.source_id,
                    "document_id": raw_document_id,
                    "chunk_index": int(chunk["chunk_index"]),
                    "text_hash": text_hash,
                    "qdrant_point_id": point_id,
                    "embedding_missing": point_id is None,
                    "heading": f"Sections {chunk['section']}",
                    "page_start": chunk.get("page_start"),
                    "page_end": chunk.get("page_end"),
                    "source_chunk_id": str(chunk["chunk_id"]),
                    "metadata_path": _relative(self.config.vault_root, book.retrieval_chunks_path),
                    "created_at": created_at,
                },
            )
            plan.evidence(
                metadata_evidence_id,
                book,
                raw_document_id,
                graph_chunk_id,
                metadata_quote,
                0,
                len(metadata_quote),
                "metadata",
                1.0,
            )
            if point_id is None:
                plan.warn(f"embedding_missing:{chunk['chunk_id']}")
            plan.relation("HAS_CHUNK", raw_document_id, graph_chunk_id, metadata_evidence_id, 1.0)
            plan.relation("FROM_CHUNK", metadata_evidence_id, graph_chunk_id, metadata_evidence_id, 1.0)

        structural_evidence = chunk_evidence[chunk_ids[0]]
        plan.relation("CONTAINS", book.source_id, raw_document_id, structural_evidence, 1.0)
        plan.relation("CONTAINS", book.source_id, synthesis_document_id, structural_evidence, 1.0)

        for author in book.authors:
            author_id = entity_id("person", author)
            plan.node(
                "Entity",
                author_id,
                {
                    "canonical_name": author,
                    "entity_type": "person",
                    "created_at": created_at,
                    "updated_at": created_at,
                    "resolution_status": "canonical",
                    "confidence": 1.0,
                },
            )
            plan.relation("AUTHORED_BY", book_entity_id, author_id, structural_evidence, 1.0)

        concepts = self._canonical_concepts(book)
        for concept, concept_id in concepts.items():
            plan.node(
                "Entity",
                concept_id,
                {
                    "canonical_name": concept,
                    "entity_type": "concept",
                    "created_at": created_at,
                    "updated_at": created_at,
                    "resolution_status": "canonical",
                    "home_vault_path": self._concept_path(concept),
                    "confidence": 0.95,
                },
            )
            for graph_chunk_id in _matching_chunks(concept, book.chunks, chunk_ids):
                quote = f"Canonical source-synthesis concept: {concept}."
                mention_evidence_id = evidence_id(graph_chunk_id, 0, len(quote), quote)
                plan.evidence(
                    mention_evidence_id,
                    book,
                    raw_document_id,
                    graph_chunk_id,
                    quote,
                    0,
                    len(quote),
                    "summary",
                    0.95,
                )
                plan.relation("MENTIONS", graph_chunk_id, concept_id, mention_evidence_id, 0.95)

        for claim_text in book.claims:
            normalized = _normalize(claim_text)
            graph_chunk_id = _claim_chunk(claim_text, book.chunks, chunk_ids)
            quote = claim_text
            claim_evidence_id = evidence_id(graph_chunk_id, 0, len(quote), quote)
            graph_claim_id = claim_id(normalized, f"source:{book.source_id}")
            plan.node(
                "Claim",
                graph_claim_id,
                {
                    "claim_text": claim_text,
                    "normalized_text": normalized,
                    "claim_type": "source_claim",
                    "claim_basis": "author-framework",
                    "scope": "source",
                    "confidence": 0.78,
                    "status": "active",
                    "verification_status": "unverified",
                    "asserted_by": list(book.authors),
                    "source_quality": "philosophical source; not empirical",
                    "created_at": created_at,
                    "updated_at": created_at,
                },
            )
            plan.evidence(
                claim_evidence_id,
                book,
                synthesis_document_id,
                graph_chunk_id,
                quote,
                0,
                len(quote),
                "summary",
                0.78,
            )
            plan.relation("SUPPORTS", graph_chunk_id, graph_claim_id, claim_evidence_id, 0.78)
            plan.relation("SUPPORTS", claim_evidence_id, graph_claim_id, claim_evidence_id, 0.78)
            about = _matching_entities(claim_text, concepts) or [book_entity_id]
            for entity in about:
                plan.relation("ABOUT", graph_claim_id, entity, claim_evidence_id, 0.78)

    def _canonical_concepts(self, book: BookArtifacts) -> dict[str, str]:
        return {concept: entity_id("concept", concept) for concept in book.concepts}

    def _concept_path(self, concept: str) -> str | None:
        expected = _slug(concept)
        for candidate in (self.config.vault_root / "02_WIKI" / "concepts").glob("*.md"):
            if _slug(candidate.stem) == expected:
                return _relative(self.config.vault_root, candidate)
        return None


class _GraphPlan:
    def __init__(self, source: str):
        self.source = source
        self._nodes: dict[str, dict[str, Any]] = {}
        self._relationships: dict[str, dict[str, Any]] = {}
        self.warnings: list[str] = []

    def node(self, label: str, node_id: str, properties: dict[str, Any]) -> None:
        self._nodes[node_id] = {"label": label, "id": node_id, "properties": {"id": node_id, **properties}}

    def evidence(
        self,
        node_id: str,
        book: BookArtifacts,
        document: str,
        chunk: str,
        quote: str,
        span_start: int,
        span_end: int,
        evidence_type: str,
        confidence: float,
    ) -> None:
        self.node(
            "Evidence",
            node_id,
            {
                "source_id": book.source_id,
                "document_id": document,
                "chunk_id": chunk,
                "quote": quote,
                "span_start": span_start,
                "span_end": span_end,
                "evidence_type": evidence_type,
                "confidence": confidence,
                "created_at": now_iso(),
                "source_locator": _relative(_vault_root_from_raw_path(book.raw_path), book.synthesis_path)
                if evidence_type == "summary"
                else _relative(_vault_root_from_raw_path(book.raw_path), book.retrieval_chunks_path),
                "extracted_by": self.source,
            },
        )

    def relation(self, relation_type: str, from_id: str, to_id: str, evidence: str, confidence: float) -> None:
        node_id = relationship_id(relation_type, from_id, to_id, evidence)
        created_at = now_iso()
        self._relationships[node_id] = {
            "id": node_id,
            "type": relation_type,
            "from_id": from_id,
            "to_id": to_id,
            "properties": {
                "id": node_id,
                "confidence": confidence,
                "source": self.source,
                "evidence_id": evidence,
                "created_at": created_at,
                "updated_at": created_at,
            },
        }

    def warn(self, warning: str) -> None:
        if warning not in self.warnings:
            self.warnings.append(warning)

    def nodes(self) -> list[dict[str, Any]]:
        return list(self._nodes.values())

    def relationships(self) -> list[dict[str, Any]]:
        return list(self._relationships.values())

    def stats(self) -> dict[str, int]:
        return {"nodes": len(self._nodes), "relationships": len(self._relationships), "warnings": len(self.warnings)}

    def as_dict(self) -> dict[str, Any]:
        return {"nodes": self.nodes(), "relationships": self.relationships()}


def _find_source_page(vault_root: Path, source_id: str) -> Path:
    for candidate in (vault_root / "02_WIKI" / "sources" / "books").glob("*.md"):
        try:
            frontmatter, _ = _read_frontmatter(candidate)
        except (OSError, yaml.YAMLError):
            continue
        if _source_id(frontmatter) == source_id:
            return candidate
    raise BookDiscoveryError(f"No canonical source page for {source_id}")


def _find_manifest(vault_root: Path, source_id: str) -> Path:
    raw_root = vault_root / "03_RESOURCES" / "books" / "raw"
    for candidate in raw_root.glob("**/manifest.md"):
        try:
            frontmatter, _ = _read_frontmatter(candidate)
        except (PermissionError, yaml.YAMLError):
            continue
        if _source_id(frontmatter) == source_id:
            return candidate
    raise BookDiscoveryError(f"No source manifest for {source_id} under {raw_root}")


def _read_frontmatter(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return _loose_frontmatter(text), text
    _, raw, body = text.split("---", 2)
    try:
        return yaml.safe_load(raw) or {}, body
    except yaml.YAMLError:
        return _loose_frontmatter(raw), body


def _loose_frontmatter(raw: str) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for line in raw.splitlines():
        if not line or line.startswith((" ", "-")) or ":" not in line:
            continue
        key, value = line.split(":", 1)
        if key.strip():
            values[key.strip()] = value.strip()
    return values



def _source_id(frontmatter: dict[str, Any]) -> str:
    """Read current and legacy source identities without mutating vault metadata."""

    return str(frontmatter.get("source_id") or frontmatter.get("id") or "").strip()


def _authors(value: Any) -> tuple[str, ...]:
    if isinstance(value, (list, tuple)):
        return tuple(str(item) for item in value if str(item).strip())
    if value is None:
        return ()
    return (str(value),)

def _parse_retrieval_chunks(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    match = re.search(r"[\`][\`][\`]json\s*(\[.*?\])\s*[\`][\`][\`]", text, flags=re.DOTALL)
    if match is None:
        return []
    parsed = json.loads(match.group(1))
    return parsed if isinstance(parsed, list) else []


def _parse_claims(body: str) -> list[str]:
    numbered = re.search(r"### Claims\s*\n(.*?)(?=\n### |\Z)", body, flags=re.DOTALL)
    if numbered is not None:
        claims = [item.strip() for item in re.findall(r"^\d+\.\s+(.+)$", numbered.group(1), flags=re.MULTILINE)]
        if claims:
            return claims

    evidence_backed = re.search(r"### Evidence-Backed Claims\s*\n(.*?)(?=\n### |\Z)", body, flags=re.DOTALL)
    if evidence_backed is not None:
        claims = [item.strip() for item in re.findall(r"^\s*[-*]\s+(.+)$", evidence_backed.group(1), flags=re.MULTILINE)]
        if claims:
            return claims

    table = re.search(r"^## Claims[^\n]*\n(?:\s*\n)*(?P<rows>(?:\|.*\n)+)", body, flags=re.IGNORECASE | re.MULTILINE)
    if table is None:
        return []
    claims: list[str] = []
    for row in table.group("rows").splitlines():
        cells = [cell.strip() for cell in row.strip().strip("|").split("|")]
        if not cells or cells[0].lower() == "claim" or set(cells[0]) <= {"-", ":"}:
            continue
        if cells[0]:
            claims.append(cells[0])
    return claims


def _matching_chunks(concept: str, chunks: tuple[dict[str, Any], ...], graph_ids: list[str]) -> list[str]:
    words = set(_normalize(concept).split())
    matches = []
    for chunk, graph_id in zip(chunks, graph_ids):
        corpus = _normalize(json.dumps(chunk))
        if words & set(corpus.split()):
            matches.append(graph_id)
    return matches or [graph_ids[0]]


def _claim_chunk(claim: str, chunks: tuple[dict[str, Any], ...], graph_ids: list[str]) -> str:
    return _matching_chunks(claim, chunks, graph_ids)[0]


def _matching_entities(claim: str, concepts: dict[str, str]) -> list[str]:
    normalized_claim = _normalize(claim)
    return [entity for concept, entity in concepts.items() if _normalize(concept) in normalized_claim]


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.lower()).strip()


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _vault_root_from_raw_path(raw_path: Path) -> Path:
    for parent in raw_path.parents:
        if parent.name == "03_RESOURCES":
            return parent.parent
    raise BookDiscoveryError(f"Raw source is not located under 03_RESOURCES: {raw_path}")


def _relative(root: Path, path: Path) -> str:
    return str(path.relative_to(root))


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
