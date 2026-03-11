-- Self-contained FTS5 table (no content= parameter to avoid column name conflicts)
CREATE VIRTUAL TABLE transcript_fts USING fts5(
  raw_text,
  segment_id,
  conversation_id,
  tokenize='porter unicode61'
);

CREATE TRIGGER trig_fts_insert AFTER INSERT ON transcript_segments BEGIN
  INSERT INTO transcript_fts(raw_text, segment_id, conversation_id)
  VALUES (new.raw_text, new.id, new.conversation_id);
END;

CREATE TRIGGER trig_fts_delete AFTER DELETE ON transcript_segments BEGIN
  DELETE FROM transcript_fts WHERE segment_id = old.id;
END;

CREATE TRIGGER trig_fts_update AFTER UPDATE ON transcript_segments BEGIN
  DELETE FROM transcript_fts WHERE segment_id = old.id;
  INSERT INTO transcript_fts(raw_text, segment_id, conversation_id)
  VALUES (new.raw_text, new.id, new.conversation_id);
END;
