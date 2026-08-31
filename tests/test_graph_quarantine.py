from types import SimpleNamespace

import pytest

from hermes_memory_os.graph import autopromote
from hermes_memory_os.graph.quarantine import quarantine_book_source


class _Store:
    def __init__(self):
        self.quarantined: list[tuple[str, str]] = []

    def list_sources_by_path_prefix(self, _prefix, *, status):
        assert status == "active"
        return [{"id": "source-one"}]

    def quarantine_source(self, source_id, *, reason):
        self.quarantined.append((source_id, reason))
        return True


class _Client:
    def __init__(self):
        self.calls: list[tuple[str, str]] = []

    def quarantine_source(self, source_id, *, reason):
        self.calls.append((source_id, reason))
        return True


def test_quarantine_preserves_audit_data_and_is_dry_run_safe():
    app = SimpleNamespace(store=_Store())
    client = _Client()

    dry_run = quarantine_book_source(
        app, client, "book-one", reason="source_integrity:section_markers_incomplete"
    )

    assert dry_run["memory_source_ids"] == ["source-one"]
    assert dry_run["memory_sources_quarantined"] == 0
    assert dry_run["graph_source_quarantined"] is False
    assert not app.store.quarantined
    assert not client.calls

    result = quarantine_book_source(
        app,
        client,
        "book-one",
        reason="source_integrity:section_markers_incomplete",
        write_mode="upsert",
    )

    assert result["memory_sources_quarantined"] == 1
    assert result["graph_source_quarantined"] is True
    assert app.store.quarantined == [("source-one", "source_integrity:section_markers_incomplete")]
    assert client.calls == [("book-one", "source_integrity:section_markers_incomplete")]


def test_invalid_source_is_quarantined_before_artifact_generation(tmp_path, monkeypatch):
    config = SimpleNamespace(vault_root=tmp_path / "vault", reports_root=tmp_path / "reports")
    config.reports_root.mkdir()
    integrity = {
        "safe_for_qdrant_crosswalk": False,
        "problems": ["section_markers_incomplete"],
        "source_id": "book-one",
    }
    calls: list[str] = []

    monkeypatch.setattr(autopromote, "is_queued_book_source", lambda *_args: True)
    monkeypatch.setattr(autopromote, "discover_book", lambda *_args: object())
    monkeypatch.setattr(autopromote, "validate_book_artifacts", lambda _book: integrity)
    monkeypatch.setattr(
        autopromote,
        "quarantine_book_source",
        lambda *_args, **_kwargs: calls.append("quarantine") or {"write_mode": "dry_run"},
    )
    monkeypatch.setattr(
        autopromote,
        "prepare_book_artifacts",
        lambda *_args, **_kwargs: pytest.fail("artifact preparation must not run"),
    )

    with pytest.raises(autopromote.AutoPromotionError, match="source-integrity"):
        autopromote.promote_queued_book(
            SimpleNamespace(),
            config,
            "book-one",
            client=None,
            write_mode="dry_run",
        )

    assert calls == ["quarantine"]
    assert (config.reports_root / "promotions" / "book-one.deferred.json").is_file()
