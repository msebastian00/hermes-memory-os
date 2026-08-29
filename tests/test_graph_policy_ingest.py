from pathlib import Path

from hermes_memory_os.graph.config import GraphConfig
from hermes_memory_os.graph.policy import GraphPolicyBuilder


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _config(tmp_path: Path) -> GraphConfig:
    config = tmp_path / "graph.yml"
    _write(config, "paths:\n  vault_root: vault\ngraph:\n  default_write_mode: dry_run\n")
    return GraphConfig.load(config)


def test_policy_ingest_dry_run_is_evidence_backed_and_idempotent(tmp_path):
    policy = tmp_path / "vault/04_SYSTEM/policies/example.md"
    _write(
        policy,
        "---\ntitle: Example Policy\n---\n\n# Example Policy\n\n"
        "Hermes MUST preserve evidence for every graph relationship.\n"
        "- A policy job MUST NOT rewrite canonical source content.\n",
    )
    builder = GraphPolicyBuilder(_config(tmp_path))

    first = builder.build(policy_paths=[policy], write_mode="dry_run")
    second = builder.build(policy_paths=[policy], write_mode="dry_run")

    assert first["status"] == second["status"] == "planned"
    assert first["stats"]["nodes"] > 0
    assert first["stats"]["relationships"] > 0
    assert first["warnings"] == []
    assert {node["label"] for node in first["plan"]["nodes"]} >= {
        "Source", "Document", "Policy", "Chunk", "Claim", "Evidence"
    }
    assert {node["id"] for node in first["plan"]["nodes"]} == {
        node["id"] for node in second["plan"]["nodes"]
    }
    assert all(edge["properties"]["evidence_id"] for edge in first["plan"]["relationships"])
