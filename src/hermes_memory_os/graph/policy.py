"""Additive, evidence-backed ingestion plan for authoritative vault policy sources."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Iterable

from hermes_memory_os.utils import now_iso

from .config import GraphConfig
from .ids import claim_id, chunk_id, document_id, evidence_id, relationship_id, stable_id

DEFAULT_POLICY_PATHS = (
    "04_SYSTEM/HERMES.md",
    "04_SYSTEM/MEMORY_POLICY.md",
    "04_SYSTEM/CHIEF_OF_STAFF.md",
    "04_SYSTEM/policies",
)


class PolicyIngestError(ValueError):
    """Raised for invalid policy ingestion requests."""


class GraphPolicyBuilder:
    """Convert policy text into reviewable graph records without altering the vault."""

    extractor_name = "hermes-graph:policy-v1"

    def __init__(self, config: GraphConfig):
        self.config = config

    def build(
        self,
        *,
        policy_paths: Iterable[Path] | None = None,
        write_mode: str = "dry_run",
        client: Any | None = None,
    ) -> dict[str, Any]:
        if write_mode not in {"dry_run", "upsert"}:
            raise PolicyIngestError("write_mode must be dry_run or upsert")
        plan = _PolicyPlan(self.extractor_name)
        paths = list(policy_paths or _default_policy_paths(self.config.vault_root))
        for path in _expand_paths(paths):
            self._plan_file(plan, path)
        result = {
            "write_mode": write_mode,
            "status": "planned",
            "generated_at": now_iso(),
            "stats": plan.stats(),
            "warnings": plan.warnings,
        }
        if write_mode == "upsert":
            if client is None:
                raise PolicyIngestError("Neo4j client is required for upsert mode")
            result["write_result"] = client.upsert(plan.nodes(), plan.relationships())
            result["status"] = "upserted"
        return {**result, "plan": plan.as_dict()}

    def _plan_file(self, plan: "_PolicyPlan", path: Path) -> None:
        try:
            text = path.read_text(encoding="utf-8")
        except PermissionError:
            plan.warn(f"policy_unreadable:{path}")
            return
        except OSError:
            plan.warn(f"policy_missing:{path}")
            return
        relative = _relative(self.config.vault_root, path)
        source_id = stable_id("policy-source", relative)
        doc_id = document_id(source_id, relative)
        policy_id = stable_id("policy", relative, _digest(text))
        title = _title(text, path.stem)
        directives = _directives(text)
        if not directives:
            plan.warn(f"policy_has_no_directives:{relative}")
            return
        stamp = now_iso()
        plan.node("Source", source_id, {
            "source_type": "policy", "title": title, "uri": relative,
            "checksum": _digest(text), "source_authority": "authoritative", "vault_path": relative,
            "created_at": stamp, "updated_at": stamp,
        })
        plan.node("Document", doc_id, {
            "source_id": source_id, "title": title, "document_type": "policy", "uri": relative,
            "source_authority": "authoritative",
        })
        plan.node("Policy", policy_id, {
            "title": title, "source_id": source_id, "document_id": doc_id, "status": "active",
            "authority": "vault-policy", "source_path": relative, "confidence": 1.0,
            "content_hash": _digest(text), "created_at": stamp, "updated_at": stamp,
        })
        first_evidence = None
        for index, directive in enumerate(directives):
            graph_chunk_id = chunk_id(doc_id, index, _digest(directive["text"]))
            graph_evidence_id = evidence_id(graph_chunk_id, directive["start"], directive["end"], directive["text"])
            graph_claim_id = claim_id(_normalize(directive["text"]), f"policy:{policy_id}")
            if first_evidence is None:
                first_evidence = graph_evidence_id
            plan.node("Chunk", graph_chunk_id, {
                "source_id": source_id, "document_id": doc_id, "chunk_index": index,
                "text_hash": _digest(directive["text"]), "heading": directive["heading"],
                "source_chunk_id": f"policy:{relative}:{index}", "created_at": stamp,
            })
            plan.node("Claim", graph_claim_id, {
                "claim_text": directive["text"], "normalized_text": _normalize(directive["text"]),
                "claim_kind": "policy_instruction", "claim_basis": "policy", "status": "active",
                "verification_status": "authoritative-source", "confidence": 1.0,
                "source_id": source_id, "policy_id": policy_id, "created_at": stamp, "updated_at": stamp,
            })
            plan.node("Evidence", graph_evidence_id, {
                "source_id": source_id, "document_id": doc_id, "chunk_id": graph_chunk_id,
                "quote": directive["text"], "span_start": directive["start"], "span_end": directive["end"],
                "evidence_type": "policy_text", "confidence": 1.0, "source_locator": relative,
                "extracted_by": self.extractor_name, "created_at": stamp,
            })
            plan.relation("HAS_CHUNK", doc_id, graph_chunk_id, graph_evidence_id, 1.0)
            plan.relation("FROM_CHUNK", graph_evidence_id, graph_chunk_id, graph_evidence_id, 1.0)
            plan.relation("SUPPORTS", graph_evidence_id, graph_claim_id, graph_evidence_id, 1.0)
            plan.relation("GOVERNS", policy_id, graph_claim_id, graph_evidence_id, 1.0)
        assert first_evidence is not None
        plan.relation("CONTAINS", source_id, doc_id, first_evidence, 1.0)
        plan.relation("HAS_POLICY", doc_id, policy_id, first_evidence, 1.0)


class _PolicyPlan:
    def __init__(self, source: str):
        self.source = source
        self._nodes: dict[str, dict[str, Any]] = {}
        self._relationships: dict[str, dict[str, Any]] = {}
        self.warnings: list[str] = []

    def node(self, label: str, node_id: str, properties: dict[str, Any]) -> None:
        self._nodes[node_id] = {"label": label, "id": node_id, "properties": {"id": node_id, **properties}}

    def relation(self, kind: str, left: str, right: str, evidence: str, confidence: float) -> None:
        relation_id = relationship_id(kind, left, right, evidence)
        stamp = now_iso()
        self._relationships[relation_id] = {
            "id": relation_id, "type": kind, "from_id": left, "to_id": right,
            "properties": {"id": relation_id, "confidence": confidence, "source": self.source,
                           "evidence_id": evidence, "created_at": stamp, "updated_at": stamp},
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


def _default_policy_paths(vault_root: Path) -> list[Path]:
    return [vault_root / path for path in DEFAULT_POLICY_PATHS]


def _expand_paths(paths: Iterable[Path]) -> Iterable[Path]:
    for path in paths:
        if path.is_dir():
            yield from sorted(candidate for candidate in path.rglob("*.md") if candidate.is_file())
        else:
            yield path


def _directives(text: str) -> list[dict[str, Any]]:
    directives = []
    heading = "Policy"
    offset = 0
    in_frontmatter = text.startswith("---\n")
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        start = offset + line.find(stripped) if stripped else offset
        offset += len(line)
        if in_frontmatter:
            if stripped == "---" and start != 0:
                in_frontmatter = False
            continue
        if stripped.startswith("#"):
            heading = stripped.lstrip("#").strip() or heading
            continue
        candidate = re.sub(r"^(?:[-*]|\d+[.)])\s+", "", stripped)
        if len(candidate) >= 12 and not candidate.startswith(("```", "`")):
            directives.append({"text": candidate, "start": start, "end": start + len(stripped), "heading": heading})
    return directives


def _title(text: str, fallback: str) -> str:
    for line in text.splitlines():
        if line.startswith("#"):
            return line.lstrip("#").strip() or fallback
    return fallback


def _relative(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path.resolve())


def _normalize(value: str) -> str:
    return " ".join(value.lower().split())


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
