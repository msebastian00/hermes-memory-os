import json

from hermes_memory_os.cli import doctor_strict_failures, main


def test_candidates_cli_create_list_and_update(tmp_path, capsys):
    data_dir = tmp_path / "data"

    assert (
        main(
            [
                "--data-dir",
                str(data_dir),
                "candidates",
                "create",
                "--source-event-id",
                "evt_1",
                "--type",
                "fact",
                "--scope",
                "system",
                "--title",
                "Candidate",
                "--summary",
                "Candidate summary.",
                "--text",
                "Candidate canonical text.",
                "--entity",
                "Hermes",
                "--tag",
                "review",
                "--confidence",
                "0.8",
                "--reason",
                "Useful durable fact.",
            ]
        )
        == 0
    )
    created = json.loads(capsys.readouterr().out)
    candidate_id = created["candidate_id"]

    assert main(["--data-dir", str(data_dir), "candidates", "list"]) == 0
    listed = json.loads(capsys.readouterr().out)
    assert listed["candidates"][0]["id"] == candidate_id
    assert listed["candidates"][0]["source_event_ids"] == ["evt_1"]

    assert (
        main(
            [
                "--data-dir",
                str(data_dir),
                "candidates",
                "update",
                candidate_id,
                "--status",
                "approved",
                "--confidence",
                "0.9",
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert main(["--data-dir", str(data_dir), "candidates", "list", "--status", "approved"]) == 0
    approved = json.loads(capsys.readouterr().out)
    assert approved["candidates"][0]["id"] == candidate_id
    assert approved["candidates"][0]["confidence"] == 0.9
    assert approved["candidates"][0]["reviewed_at"] is not None


def test_doctor_reports_paths_and_local_service_config(tmp_path, capsys):
    wiki = tmp_path / "wiki"
    config_path = tmp_path / "config.yml"
    data_dir = tmp_path / "data"
    config_path.write_text(
        f"""
paths:
  base_dir: {data_dir}
  vault_dir: {data_dir / "vault"}
  sqlite_path: {data_dir / "db" / "memory.sqlite"}
  logs_dir: {data_dir / "logs"}
wiki_brain:
  enabled: true
  paths:
    - {wiki}
embeddings:
  provider: none
qdrant:
  enabled: false
""",
        encoding="utf-8",
    )

    assert main(["--config", str(config_path), "doctor"]) == 0
    status = json.loads(capsys.readouterr().out)

    assert status["base_dir"] == str(data_dir)
    assert status["base_dir_exists"] is True
    assert status["sqlite_path"] == str(data_dir / "db" / "memory.sqlite")
    assert status["embedding_provider"] == "none"
    assert status["semantic_enabled"] is False
    assert status["qdrant_enabled"] is False
    assert status["wiki_path_status"] == [{"path": str(wiki), "exists": False}]


def test_doctor_strict_failures_require_semantic_services():
    failures = doctor_strict_failures(
        {
            "base_dir_exists": True,
            "vault_dir_exists": True,
            "sqlite_exists": True,
            "logs_dir_exists": True,
            "cloud_allowed": False,
            "embedding_provider": "none",
            "semantic_enabled": False,
            "qdrant_enabled": False,
        }
    )

    assert "semantic_disabled" in failures
    assert "embedding_provider_none" in failures
    assert "qdrant_disabled" in failures


def test_doctor_strict_failures_pass_when_all_services_are_ready():
    failures = doctor_strict_failures(
        {
            "base_dir_exists": True,
            "vault_dir_exists": True,
            "sqlite_exists": True,
            "logs_dir_exists": True,
            "cloud_allowed": False,
            "embedding_provider": "ollama",
            "embedding_reachable": True,
            "semantic_enabled": True,
            "qdrant_enabled": True,
            "qdrant_reachable": True,
            "qdrant_collections": {
                "memories": {"exists": True},
                "sources": {"exists": True},
            },
        }
    )

    assert failures == []
