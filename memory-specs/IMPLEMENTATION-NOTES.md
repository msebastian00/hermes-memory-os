# Implementation Notes — hermes-memory-os

This folder contains working notes that are not part of the main wiki spec.

## Phase 0 Complete
- Full directory skeleton created
- Basic README, pyproject.toml, config
- Provider stub
- Vault structure with VELLUM.md starter

## Phase 1 Complete
- SQLite schema implemented (`src/hermes_memory_os/db/schema.py`)
- Database connection layer (`src/hermes_memory_os/db/connection.py`)
- Qdrant collection setup script
- Basic embedding pipeline
- Memory CRUD operations (`src/hermes_memory_os/db/memory.py`)

## Phase 2 In Progress
- Core `HermesMemoryOSProvider` with SQLite + Qdrant integration
- Basic `create_memory`, `get_memory`, `list_memories`
- `prefetch()` and `sync_turn()` implemented

---

## Testing Strategy (Added during Phase 2)

### Current State
- No tests existed at the start of Phase 2.
- Minimal test layer added: `tests/test_memory_crud.py`

### Required Test Layers

**1. Unit Tests (Core)**
- Location: `tests/`
- Focus: Individual functions and classes in `src/hermes_memory_os/db/` and `src/hermes_memory_os/`
- Must cover:
  - All CRUD operations in `db/memory.py`
  - Database connection and schema initialization
  - Entity operations (when implemented)
  - Provider methods (`prefetch`, `sync_turn`, `create_memory`, etc.)

**2. Validation Tests (Integration)**
- End-to-end flows:
  - Full ingestion → embedding → retrieval cycle
  - `sync_turn` → memory creation → `prefetch` roundtrip
  - Qdrant + SQLite consistency checks
- Should use the exact collections defined in `hermes-memory-os.yaml`

**3. Spec Compliance Tests**
- Verify that retrieval respects the weights in `hermes-memory-os.yaml`:
  - semantic: 0.45
  - keyword: 0.20
  - entity: 0.15
  - scope: 0.10
  - recency: 0.05
  - trust: 0.05
- Validate `max_injected: 8` and `min_final_score: 0.35`

### Running Tests
```bash
cd /workspace/agent-dev/hermes-memory-os
python -m pytest tests/ -v
```

### Future Additions
- Add `tests/test_retrieval.py`
- Add `tests/test_provider.py`
- Add `tests/test_vellum_workflows.py`
- CI integration for test runs on every change

---

See the full spec at [[hermes-memory-os]] in the wiki.