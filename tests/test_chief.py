import json
from pathlib import Path

from hermes_memory_os.app import MemoryApp
from hermes_memory_os.chief import daily_brief, process_inbox, self_review, weekly_connections
from hermes_memory_os.cli import main


def _app(tmp_path: Path) -> MemoryApp:
    app = MemoryApp.from_config(data_dir=tmp_path / "data")
    app.init_storage()
    return app


def test_process_inbox_writes_triage_draft(tmp_path):
    app = _app(tmp_path)
    app.add_memory(
        memory_type="fact",
        scope="system",
        title="Inbox Memory",
        summary="Hermes should triage inbox items into reviewed decisions.",
        canonical_text="Hermes should triage inbox items into reviewed decisions.",
        tags=["inbox"],
        entities=["Hermes"],
    )
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "note.md").write_text(
        "Action: connect this note to Hermes inbox triage.\nRemember to review candidates.",
        encoding="utf-8",
    )

    output = process_inbox(app, paths=[inbox], output_dir=tmp_path / "out")
    text = output.read_text(encoding="utf-8")

    assert "# Inbox Processing Draft" in text
    assert "## Suggested Actions" in text
    assert "Action: connect this note to Hermes inbox triage." in text
    assert "Inbox Memory" in text


def test_daily_brief_writes_recent_turns_and_open_loops(tmp_path):
    app = _app(tmp_path)
    app.store.sync_turn(
        "Need to follow up on semantic retrieval docs?",
        "I will check the live smoke guide.",
        {"client": "hermes-dev", "conversation_id": "daily"},
    )

    output = daily_brief(app, output_dir=tmp_path / "out")
    text = output.read_text(encoding="utf-8")

    assert "# Daily Brief Draft" in text
    assert "## Recent Turns" in text
    assert "Need to follow up" in text
    assert "## Open Loops" in text


def test_weekly_connections_writes_memory_clusters(tmp_path):
    app = _app(tmp_path)
    app.add_memory(
        memory_type="fact",
        scope="system",
        title="Long Form",
        summary="Long-form ingestion connects books transcripts and durable memory.",
        canonical_text="Long-form ingestion connects books transcripts and durable memory.",
        tags=["long-form"],
        entities=["Hermes"],
    )

    output = weekly_connections(app, output_dir=tmp_path / "out")
    text = output.read_text(encoding="utf-8")

    assert "# Weekly Connections Draft" in text
    assert "## Recurring Ideas" in text
    assert "## Memory Clusters" in text
    assert "Long Form" in text


def test_self_review_writes_candidates_and_learning_events(tmp_path):
    app = _app(tmp_path)
    event_id = app.store.add_raw_event("Review this durable candidate.")
    candidate_id = app.store.create_extraction_candidate(
        source_event_ids=[event_id],
        memory_type="fact",
        scope="system",
        title="Candidate",
        summary="Hermes should stage candidates for review.",
        canonical_text="Hermes should stage candidates for review.",
        confidence=0.8,
    )
    learning_id = app.store.log_agent_learning_event(
        event_type="retrieval_miss",
        summary="Hermes missed a useful recall.",
        evidence={"query": "chief"},
    )

    output = self_review(app, output_dir=tmp_path / "out")
    text = output.read_text(encoding="utf-8")

    assert "# Self-Review Draft" in text
    assert candidate_id in text
    assert learning_id in text
    assert "hermes-memory candidates update" in text


def test_chief_cli_writes_daily_brief(tmp_path, capsys):
    data_dir = tmp_path / "data"
    output_dir = tmp_path / "out"
    assert (
        main(
            [
                "--data-dir",
                str(data_dir),
                "chief",
                "daily-brief",
                "--output-dir",
                str(output_dir),
            ]
        )
        == 0
    )
    result = json.loads(capsys.readouterr().out)
    output = Path(result["output_path"])
    assert output.exists()
    assert output.parent == output_dir
    assert "# Daily Brief Draft" in output.read_text(encoding="utf-8")
