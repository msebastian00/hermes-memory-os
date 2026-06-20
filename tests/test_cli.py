import json

from hermes_memory_os.cli import main


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

def test_cli_uses_hermes_memory_config_env(tmp_path, capsys, monkeypatch):
    config_path = tmp_path / "config.yml"
    data_dir = tmp_path / "env-config-data"
    config_path.write_text(
        f"""
paths:
  base_dir: {data_dir}
  vault_dir: {data_dir / "vault"}
  sqlite_path: {data_dir / "db" / "memory.sqlite"}
  logs_dir: {data_dir / "logs"}
embeddings:
  provider: none
qdrant:
  enabled: false
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("HERMES_MEMORY_CONFIG", str(config_path))
    monkeypatch.delenv("HERMES_MEMORY_HOME", raising=False)

    assert main(["doctor"]) == 0
    status = json.loads(capsys.readouterr().out)

    assert status["base_dir"] == str(data_dir)
    assert status["sqlite_path"] == str(data_dir / "db" / "memory.sqlite")
    assert status["qdrant_enabled"] is False



def test_search_min_score_override_returns_low_scoring_source_chunk(tmp_path, capsys):
    data_dir = tmp_path / "data"
    transcript = tmp_path / "talk.srt"
    transcript.write_text(
        "1\n00:00:01,000 --> 00:00:02,000\nResponsibility matters.\n",
        encoding="utf-8",
    )

    assert (
        main(
            [
                "--data-dir",
                str(data_dir),
                "ingest",
                "--path",
                str(transcript),
                "--source-type",
                "subtitle",
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert (
        main(
            [
                "--data-dir",
                str(data_dir),
                "search",
                "responsibility",
                "--source-type",
                "subtitle",
                "--min-score",
                "0.1",
            ]
        )
        == 0
    )
    output = json.loads(capsys.readouterr().out)

    assert output["results"]
    assert output["results"][0]["kind"] == "source_chunk"
