from types import SimpleNamespace

from hermes_memory_os.graph import autopromote


def _config(tmp_path):
    vault = tmp_path / "vault"
    card = vault / "05_QUEUE" / "book-ingestion" / "incoming" / "book-one.md"
    card.parent.mkdir(parents=True)
    card.write_text("---\nsource_id: book-one\n---\n", encoding="utf-8")
    return SimpleNamespace(vault_root=vault, reports_root=tmp_path / "reports", min_edge_confidence=0.75)




def test_queued_source_ids_exclude_superseded_and_cleanup_cards(tmp_path):
    config = _config(tmp_path)
    queue = config.vault_root / "05_QUEUE" / "book-ingestion" / "completed"
    queue.mkdir(parents=True)
    (queue / "superseded.md").write_text(
        "---\nsource_id: old-book\nsuperseded_by: completed/new-book.md\n---\n",
        encoding="utf-8",
    )
    (queue / "cleanup.md").write_text(
        "---\nsource_id: generated-note\ncleanup_note: not a book\n---\n",
        encoding="utf-8",
    )
    (queue / "active.md").write_text("---\nsource_id: book-two\n---\n", encoding="utf-8")

    assert autopromote.queued_book_source_ids(config.vault_root) == ["book-one", "book-two"]
def test_queued_promotion_validates_both_dry_runs_before_any_upsert(tmp_path, monkeypatch):
    config = _config(tmp_path)
    calls = []
    book = SimpleNamespace(concepts=("Finite Game",))

    monkeypatch.setattr(autopromote, "discover_book", lambda _vault, _source: book)
    monkeypatch.setattr(autopromote, "embedding_input_limit", lambda _app: 6000)
    monkeypatch.setattr(
        autopromote,
        "prepare_book_artifacts",
        lambda *_args, **_kwargs: {"chunk_bodies_path": str(tmp_path / "chunk-bodies.json")},
    )
    monkeypatch.setattr(
        autopromote,
        "validate_book_artifacts",
        lambda _book: {"safe_for_qdrant_crosswalk": True, "problems": []},
    )

    def crosswalk(_app, _config, _source, _bodies, *, write_mode):
        calls.append(f"crosswalk:{write_mode}")
        return {
            "status": "planned" if write_mode == "dry_run" else "indexed",
            "qdrant_point_ids": {"chunk-one": "point-one"},
        }

    class Builder:
        def __init__(self, _config):
            pass

        def build(self, _source, *, write_mode, qdrant_crosswalk=None, client=None):
            calls.append(f"graph:{write_mode}")
            if write_mode == "upsert":
                assert qdrant_crosswalk == {"chunk-one": "point-one"}
                assert client is not None
            return {"status": "planned" if write_mode == "dry_run" else "upserted", "stats": {}, "warnings": [], "plan": {}}

    monkeypatch.setattr(autopromote, "index_book_crosswalk", crosswalk)
    monkeypatch.setattr(autopromote, "GraphBookBuilder", Builder)
    monkeypatch.setattr(autopromote, "write_crosswalk", lambda _result, path: path)
    monkeypatch.setattr(autopromote, "concept_candidates", lambda *_args: [])
    monkeypatch.setattr(
        autopromote,
        "collect_overlap_review",
        lambda *_args, **_kwargs: {"status": "reported", "counts": {}, "review_warnings": []},
    )
    monkeypatch.setattr(autopromote, "write_overlap_review_report", lambda _review, path: path)
    monkeypatch.setattr(
        autopromote,
        "collect_maintenance",
        lambda *_args, **_kwargs: {"duplicate_entities": [], "claims_without_evidence": []},
    )
    monkeypatch.setattr(autopromote, "write_maintenance_report", lambda _report, path: path)

    app = SimpleNamespace(semantic_indexer=object())
    client = SimpleNamespace(health=lambda: True)
    bodies = tmp_path / "chunk-bodies.json"
    bodies.write_text("{}", encoding="utf-8")

    result = autopromote.promote_queued_book(app, config, "book-one", client=client, chunk_bodies_path=bodies)

    assert result["status"] == "promoted"
    assert calls == ["crosswalk:dry_run", "graph:dry_run", "crosswalk:upsert", "graph:upsert"]
    assert result["authorization"] == "book-ingestion-queue"
    assert result["report_path"]


def test_visual_promotion_uses_manifest_pdf_and_evidence_gates(tmp_path, monkeypatch):
    config = _config(tmp_path)
    book = SimpleNamespace(source_id="book-one")
    calls = []

    monkeypatch.setattr(autopromote, "visual_processing_enabled", lambda: True)
    monkeypatch.setattr(autopromote, "discover_book_pdf", lambda *_args: tmp_path / "book.pdf")
    monkeypatch.setattr(
        autopromote,
        "extract_pdf_visual_evidence",
        lambda *_args: {"pages_rendered": 1, "records": [{"page_number": 1}], "warnings": []},
    )
    monkeypatch.setattr(
        autopromote,
        "visual_evidence_plan",
        lambda *_args, **_kwargs: {
            "nodes": [{"id": "claim"}],
            "relationships": [{"id": "supports"}],
            "visual_records": [{"evidence_id": "evidence"}],
            "warnings": [],
        },
    )

    class Client:
        def upsert(self, nodes, relationships):
            calls.append(("upsert", nodes, relationships))
            return {"nodes": len(nodes), "relationships": len(relationships)}

        def supersede_visual_variants(self, records):
            calls.append(("supersede", records))
            return {"claims": 0, "evidence": 0}

    result = autopromote._promote_visual_evidence(config, book, client=Client(), write_mode="upsert")

    assert result["status"] == "upserted"
    assert result["pages_rendered"] == 1
    assert [call[0] for call in calls] == ["upsert", "supersede"]
