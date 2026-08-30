"""Read-only concept-overlap review for graph promotion.

The reviewer deliberately separates candidate discovery from human resolution. It
queries the Memory OS semantic backend (Qdrant) first, then Neo4j entities, and
only writes a Markdown review artifact when requested by the caller.
"""

from __future__ import annotations

import hashlib
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable

import yaml

from hermes_memory_os.utils import now_iso


EXACT_CONFIDENCE = 1.0
LEXICAL_REVIEW_THRESHOLD = 0.72


def concept_candidates(source_id: str, concepts: Iterable[str]) -> list[dict[str, str]]:
    """Return deterministic, de-duplicated concept candidates for a source."""

    seen: set[tuple[str, str]] = set()
    candidates: list[dict[str, str]] = []
    for value in concepts:
        canonical_name = " ".join(str(value).split())
        normalized = normalize_name(canonical_name)
        key = ("concept", normalized)
        if not normalized or key in seen:
            continue
        seen.add(key)
        candidates.append(
            {
                "source_id": source_id,
                "canonical_name": canonical_name,
                "entity_type": "concept",
            }
        )
    return candidates


def candidate_digest(candidates: Iterable[dict[str, Any]]) -> str:
    """Hash only the identity fields a reviewer is approving."""

    canonical = sorted(
        {
            (
                str(item.get("source_id") or ""),
                str(item.get("entity_type") or "concept"),
                normalize_name(str(item.get("canonical_name") or "")),
            )
            for item in candidates
            if normalize_name(str(item.get("canonical_name") or ""))
        }
    )
    payload = "\n".join("\t".join(item) for item in canonical)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def collect_overlap_review(
    candidates: Iterable[dict[str, Any]],
    *,
    graph_client: Any | None,
    memory_app: Any | None = None,
    semantic_limit: int = 5,
    graph_limit: int = 500,
    vault_root: Path | None = None,
) -> dict[str, Any]:
    """Collect review-only overlap candidates without changing any source system."""

    requested = _validated_candidates(candidates)
    warnings: list[str] = []
    semantic_by_candidate: dict[str, list[dict[str, Any]]] = {}

    # Use the semantic backend directly so this review does not log a retrieval
    # event or write to SQLite. It is Qdrant-first when configured.
    semantic_backend = getattr(getattr(memory_app, "retriever", None), "semantic_backend", None)
    if semantic_backend is None:
        warnings.append("qdrant_semantic_review_unavailable")
    else:
        for candidate in requested:
            key = _candidate_key(candidate)
            try:
                semantic_by_candidate[key] = _compact_semantic_hits(
                    _semantic_overlap_search(semantic_backend, candidate["canonical_name"], semantic_limit)
                )
            except Exception as exc:
                semantic_by_candidate[key] = []
                warnings.append(f"qdrant_semantic_review_failed:{exc.__class__.__name__}")

    graph_entities: list[dict[str, Any]] = []
    if graph_client is None:
        warnings.append("graph_entity_review_unavailable")
    else:
        try:
            graph_entities = graph_client.execute(
                """
                MATCH (entity:Entity)
                RETURN entity.id AS id,
                       entity.canonical_name AS canonical_name,
                       entity.entity_type AS entity_type,
                       coalesce(entity.aliases, []) AS aliases,
                       entity.home_vault_path AS home_vault_path,
                       entity.confidence AS confidence
                LIMIT $limit
                """,
                {"limit": graph_limit},
            )
        except Exception as exc:
            warnings.append(f"graph_entity_review_failed:{exc.__class__.__name__}")

    vault_entities = _vault_entities(vault_root, warnings)

    items = []
    for candidate in requested:
        key = _candidate_key(candidate)
        graph_matches = _graph_matches(candidate, graph_entities)
        vault_matches = _vault_matches(candidate, vault_entities)
        semantic_hits = semantic_by_candidate.get(key, [])
        if (graph_matches and graph_matches[0]["match_kind"] == "exact") or (vault_matches and vault_matches[0]["match_kind"] == "exact"):
            status = "review_required"
            recommended_action = "Attach only after a human verifies that this is the same canonical concept."
        elif graph_matches or vault_matches or semantic_hits:
            status = "review_required"
            recommended_action = "Classify as same_concept, broader_or_narrower, related_but_distinct, or uncertain."
        else:
            status = "no_match_found"
            recommended_action = "No automatic action. A human must still approve this review before graph upsert."
        items.append(
            {
                **candidate,
                "status": status,
                "recommended_action": recommended_action,
                "graph_matches": graph_matches,
                "vault_matches": vault_matches,
                "semantic_hits": semantic_hits,
            }
        )

    return {
        "type": "graph-overlap-review",
        "status": ("incomplete" if warnings else "pending_human_review"),
        "generated_at": now_iso(),
        "candidate_digest": candidate_digest(requested),
        "review_complete": not warnings,
        "candidates": items,
        "counts": {
            "candidates": len(items),
            "review_required": sum(item["status"] == "review_required" for item in items),
            "no_match_found": sum(item["status"] == "no_match_found" for item in items),
        },
        "review_warnings": list(dict.fromkeys(warnings)),
        "auto_merged": False,
        "notes_rewritten": False,
        "memory_os_written": False,
        "qdrant_written": False,
        "neo4j_written": False,
    }


def write_overlap_review_report(review: dict[str, Any], output_path: Path) -> Path:
    """Write a human-reviewable report. Approval is an explicit manual edit."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    frontmatter = {
        "type": review["type"],
        "status": review["status"],
        "generated_at": review["generated_at"],
        "candidate_digest": review["candidate_digest"],
        "review_complete": review["review_complete"],
        "source_ids": sorted({item["source_id"] for item in review["candidates"]}),
        "approved_by": None,
        "approved_at": None,
    }
    lines = ["---", yaml.safe_dump(frontmatter, sort_keys=False).strip(), "---", "", "# Graph Concept Overlap Review", ""]
    lines.extend(
        [
            "This is a review artifact. It does not merge entities, change aliases, rewrite vault notes, or write Qdrant, Neo4j, or Memory OS.",
            "To permit a graph upsert, rerun until `review_complete: true`; then a human must set frontmatter `status: approved`, record `approved_by` and `approved_at`, and resolve every `review_required` candidate below.",
            "",
        ]
    )
    for item in review["candidates"]:
        lines.extend(
            [
                f"## {item['canonical_name']} ({item['entity_type']})",
                f"- Source ID: `{item['source_id']}`",
                f"- Status: `{item['status']}`",
                f"- Recommended action: {item['recommended_action']}",
                "- Resolution: `pending`",
                "",
                "### Graph candidates",
            ]
        )
        if item["graph_matches"]:
            for match in item["graph_matches"]:
                lines.append(
                    f"- `{match['canonical_name']}` (`{match['entity_type']}`, {match['match_kind']}, confidence {match['confidence']:.2f}, id `{match['id']}`)"
                )
        else:
            lines.append("- None.")
        lines.extend(["", "### Vault candidates"])
        if item["vault_matches"]:
            for match in item["vault_matches"]:
                lines.append(
                    f"- `{match['canonical_name']}` ({match['match_kind']}, confidence {match['confidence']:.2f}, path `{match['vault_path']}`)"
                )
        else:
            lines.append("- None.")
        lines.extend(["", "### Qdrant semantic evidence"])
        if item["semantic_hits"]:
            for hit in item["semantic_hits"]:
                locator = hit.get("citation") or hit.get("source") or hit.get("id")
                lines.append(
                    f"- `{locator}` (score {hit.get('semantic_score', 0.0):.2f}; Qdrant point `{hit.get('qdrant_point_id') or 'unknown'}`)"
                )
        else:
            lines.append("- None.")
        lines.append("")
    if review["review_warnings"]:
        lines.append("## Warnings")
        lines.extend(f"- `{warning}`" for warning in review["review_warnings"])
        lines.append("")
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path


def validate_approved_overlap_review(
    path: Path | None, *, source_id: str, candidates: Iterable[dict[str, Any]]
) -> None:
    """Refuse graph upserts without an explicit, matching human review."""

    if path is None or not path.is_file():
        raise ValueError("Graph upsert requires an approved overlap-review report.")
    metadata = _read_frontmatter(path)
    expected_digest = candidate_digest(candidates)
    if metadata.get("type") != "graph-overlap-review":
        raise ValueError("Overlap-review report has an invalid type.")
    if metadata.get("candidate_digest") != expected_digest:
        raise ValueError("Overlap-review report does not match the current source concepts.")
    source_ids = {str(value) for value in metadata.get("source_ids") or []}
    if source_ids != {source_id}:
        raise ValueError("Overlap-review report does not match the requested source ID.")
    if metadata.get("review_complete") is not True:
        raise ValueError("Overlap-review report is incomplete; restore Qdrant and Neo4j then rerun it.")
    if metadata.get("status") != "approved":
        raise ValueError("Overlap-review report must have status: approved before graph upsert.")
    if not str(metadata.get("approved_by") or "").strip() or not str(metadata.get("approved_at") or "").strip():
        raise ValueError("Approved overlap-review report requires approved_by and approved_at.")


def normalize_name(value: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value.lower()).split())


def _validated_candidates(candidates: Iterable[dict[str, Any]]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in candidates:
        name = " ".join(str(item.get("canonical_name") or "").split())
        source_id = str(item.get("source_id") or "").strip()
        entity_type = str(item.get("entity_type") or "concept").strip()
        normalized = normalize_name(name)
        key = (source_id, entity_type, normalized)
        if not source_id or not normalized or key in seen:
            continue
        seen.add(key)
        result.append({"source_id": source_id, "canonical_name": name, "entity_type": entity_type})
    return result


def _candidate_key(candidate: dict[str, str]) -> str:
    return f"{candidate['source_id']}:{candidate['entity_type']}:{normalize_name(candidate['canonical_name'])}"


def _vault_entities(vault_root: Path | None, warnings: list[str]) -> list[dict[str, Any]]:
    if vault_root is None or not vault_root.is_dir():
        warnings.append("vault_entity_review_unavailable")
        return []
    concepts_root = vault_root / "02_WIKI" / "concepts"
    if not concepts_root.is_dir():
        return []
    entities: list[dict[str, Any]] = []
    for path in sorted(concepts_root.rglob("*.md")):
        try:
            metadata = _read_frontmatter(path)
        except (OSError, yaml.YAMLError) as exc:
            warnings.append(f"vault_entity_review_failed:{exc.__class__.__name__}")
            continue
        aliases = metadata.get("aliases") or []
        if isinstance(aliases, str):
            aliases = [aliases]
        entities.append(
            {
                "canonical_name": str(metadata.get("title") or path.stem),
                "entity_type": str(metadata.get("entity_type") or metadata.get("type") or "concept"),
                "aliases": [str(alias) for alias in aliases],
                "vault_path": str(path.relative_to(vault_root)),
            }
        )
    return entities


def _vault_matches(candidate: dict[str, str], entities: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    name = normalize_name(candidate["canonical_name"])
    matches: list[dict[str, Any]] = []
    for entity in entities:
        if str(entity.get("entity_type") or "concept") != candidate["entity_type"]:
            continue
        names = [str(entity.get("canonical_name") or "")] + [str(alias) for alias in entity.get("aliases") or []]
        best = max((lexical_similarity(name, normalize_name(value)) for value in names if normalize_name(value)), default=0.0)
        if best < LEXICAL_REVIEW_THRESHOLD:
            continue
        exact = any(normalize_name(value) == name for value in names)
        matches.append(
            {
                "canonical_name": str(entity.get("canonical_name") or ""),
                "vault_path": str(entity.get("vault_path") or ""),
                "match_kind": "exact" if exact else "lexical_near_match",
                "confidence": EXACT_CONFIDENCE if exact else round(best, 3),
            }
        )
    return sorted(matches, key=lambda item: (-item["confidence"], item["canonical_name"]))


def _graph_matches(candidate: dict[str, str], entities: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    name = normalize_name(candidate["canonical_name"])
    matches: list[dict[str, Any]] = []
    for entity in entities:
        if str(entity.get("entity_type") or "") != candidate["entity_type"]:
            continue
        names = [str(entity.get("canonical_name") or "")] + [str(alias) for alias in entity.get("aliases") or []]
        best = max((lexical_similarity(name, normalize_name(value)) for value in names if normalize_name(value)), default=0.0)
        if best < LEXICAL_REVIEW_THRESHOLD:
            continue
        exact = any(normalize_name(value) == name for value in names)
        matches.append(
            {
                "id": str(entity.get("id") or ""),
                "canonical_name": str(entity.get("canonical_name") or ""),
                "entity_type": str(entity.get("entity_type") or ""),
                "home_vault_path": entity.get("home_vault_path"),
                "match_kind": "exact" if exact else "lexical_near_match",
                "confidence": EXACT_CONFIDENCE if exact else round(best, 3),
            }
        )
    return sorted(matches, key=lambda item: (-item["confidence"], item["canonical_name"]))


def lexical_similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    if left == right:
        return EXACT_CONFIDENCE
    sequence = SequenceMatcher(None, left, right).ratio()
    left_tokens, right_tokens = set(left.split()), set(right.split())
    jaccard = len(left_tokens & right_tokens) / len(left_tokens | right_tokens) if left_tokens | right_tokens else 0.0
    return max(sequence, jaccard)


def _semantic_overlap_search(backend: Any, query: str, limit: int) -> list[dict[str, Any]]:
    overlap_search = getattr(backend, "search_overlap_candidates", None)
    if callable(overlap_search):
        return overlap_search(query, limit=limit)
    return backend.search(query, limit=limit, source_types=None)


def _compact_semantic_hits(hits: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "id": hit.get("id"),
            "kind": hit.get("kind"),
            "source_id": hit.get("source_id"),
            "citation": hit.get("citation"),
            "source": hit.get("source"),
            "qdrant_point_id": hit.get("qdrant_point_id"),
            "semantic_score": round(float(hit.get("semantic_score") or 0.0), 3),
        }
        for hit in hits
    ]


def _read_frontmatter(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}
    _start, _separator, remainder = text.partition("\n---\n")
    if not _separator:
        return {}
    raw = text[4 : len(text) - len(remainder) - len(_separator)]
    parsed = yaml.safe_load(raw) or {}
    return parsed if isinstance(parsed, dict) else {}
