-- Requires sqlite-vec extension loaded at connection time
-- This migration is a no-op if the extension is not available
-- vec0 virtual table for semantic search
CREATE VIRTUAL TABLE IF NOT EXISTS segment_embeddings USING vec0(
  segment_id TEXT PRIMARY KEY,
  embedding   FLOAT[768]
);
