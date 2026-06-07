"""SQLite schema for Hermes Memory OS."""

SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS raw_events (
  id TEXT PRIMARY KEY,
  source TEXT NOT NULL,
  client TEXT,
  conversation_id TEXT,
  source_ref TEXT,
  role TEXT,
  content TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  created_at TEXT NOT NULL,
  metadata_json TEXT,
  status TEXT DEFAULT 'active'
);

CREATE TABLE IF NOT EXISTS memories (
  id TEXT PRIMARY KEY,
  memory_type TEXT NOT NULL,
  scope TEXT NOT NULL,
  title TEXT,
  summary TEXT NOT NULL,
  canonical_text TEXT NOT NULL,
  source_event_ids TEXT,
  source_paths TEXT,
  entities_json TEXT,
  tags_json TEXT,
  confidence REAL DEFAULT 0.5,
  trust_score REAL DEFAULT 0.5,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  last_recalled_at TEXT,
  status TEXT DEFAULT 'active',
  supersedes_id TEXT,
  superseded_by_id TEXT,
  qdrant_collection TEXT,
  qdrant_point_id TEXT
);

CREATE TABLE IF NOT EXISTS sources (
  id TEXT PRIMARY KEY,
  title TEXT,
  author_or_speaker TEXT,
  source_type TEXT NOT NULL,
  source_path TEXT NOT NULL,
  source_date TEXT,
  ingested_at TEXT NOT NULL,
  status TEXT DEFAULT 'active',
  summary TEXT,
  metadata_json TEXT,
  content_hash TEXT NOT NULL,
  UNIQUE(source_path, content_hash)
);

CREATE TABLE IF NOT EXISTS source_chunks (
  id TEXT PRIMARY KEY,
  source_id TEXT NOT NULL REFERENCES sources(id),
  chunk_index INTEGER NOT NULL,
  heading TEXT,
  chapter TEXT,
  section TEXT,
  page_start INTEGER,
  page_end INTEGER,
  timestamp_start TEXT,
  timestamp_end TEXT,
  text TEXT NOT NULL,
  summary TEXT,
  content_hash TEXT NOT NULL,
  qdrant_point_id TEXT,
  created_at TEXT NOT NULL,
  UNIQUE(source_id, chunk_index, content_hash)
);

CREATE TABLE IF NOT EXISTS retrieval_log (
  id TEXT PRIMARY KEY,
  query TEXT NOT NULL,
  query_context_json TEXT,
  retrieved_ids_json TEXT,
  scores_json TEXT,
  created_at TEXT NOT NULL,
  latency_ms INTEGER,
  result_count INTEGER DEFAULT 0,
  suppressed INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS injection_log (
  id TEXT PRIMARY KEY,
  turn_id TEXT,
  memory_ids_json TEXT,
  injected_text TEXT,
  token_estimate INTEGER,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS feedback (
  id TEXT PRIMARY KEY,
  memory_id TEXT,
  retrieval_id TEXT,
  feedback_type TEXT NOT NULL,
  details TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_learning_events (
  id TEXT PRIMARY KEY,
  event_type TEXT NOT NULL,
  summary TEXT NOT NULL,
  evidence_json TEXT,
  candidate_change TEXT,
  status TEXT DEFAULT 'pending_review',
  created_at TEXT NOT NULL,
  reviewed_at TEXT
);

CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts
USING fts5(memory_id UNINDEXED, title, summary, canonical_text);

CREATE VIRTUAL TABLE IF NOT EXISTS source_chunks_fts
USING fts5(chunk_id UNINDEXED, source_id UNINDEXED, heading, text);
"""
