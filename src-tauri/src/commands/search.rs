use crate::db::models::{SearchMode, SearchQuery, SearchResult};
use crate::db::DbPool;
use crate::worker::WorkerClient;
use rusqlite::params;
use tauri::State;

#[tauri::command]
pub async fn search(
    db: State<'_, DbPool>,
    worker: State<'_, WorkerClient>,
    query: SearchQuery,
) -> Result<Vec<SearchResult>, String> {
    match query.mode {
        SearchMode::Keyword => keyword_search(&db, &query),
        SearchMode::Semantic => semantic_search(&db, &worker, &query).await,
        SearchMode::Hybrid => hybrid_search(&db, &worker, &query).await,
    }
}

fn keyword_search(db: &DbPool, query: &SearchQuery) -> Result<Vec<SearchResult>, String> {
    let conn = db.get().map_err(|e| e.to_string())?;
    let limit = query.limit.unwrap_or(20);

    // FTS5: MATCH uses real table name; join on segment_id stored in FTS
    let sql = "SELECT ts.id, ts.conversation_id, c.started_at, ts.raw_text, ts.started_at,
                      sp.display_name, transcript_fts.rank
               FROM transcript_fts
               JOIN transcript_segments ts ON ts.id = transcript_fts.segment_id
               JOIN conversations c ON c.id = transcript_fts.conversation_id
               LEFT JOIN speaker_instances si ON ts.speaker_instance_id = si.id
               LEFT JOIN speaker_profiles sp ON si.speaker_profile_id = sp.id
               WHERE transcript_fts MATCH ?1
                 AND (?2 IS NULL OR c.started_at >= ?2)
                 AND (?3 IS NULL OR c.started_at <= ?3)
                 AND (?4 IS NULL OR si.speaker_profile_id = ?4)
               ORDER BY transcript_fts.rank
               LIMIT ?5";

    let mut stmt = conn.prepare(sql).map_err(|e| e.to_string())?;

    let rows = stmt
        .query_map(
            params![
                query.text,
                query.date_from,
                query.date_to,
                query.speaker_profile_id,
                limit
            ],
            |row| {
                let rank: f64 = row.get::<_, f64>(6).unwrap_or(0.0);
                Ok(SearchResult {
                    segment_id: row.get(0)?,
                    conversation_id: row.get(1)?,
                    conversation_started_at: row.get(2)?,
                    text: row.get(3)?,
                    started_at: row.get(4)?,
                    speaker_display_name: row.get(5)?,
                    match_type: "keyword".to_string(),
                    score: -rank, // FTS5 rank is negative
                })
            },
        )
        .map_err(|e| e.to_string())?;

    let mut results = Vec::new();
    for row in rows {
        results.push(row.map_err(|e| e.to_string())?);
    }
    Ok(results)
}

async fn semantic_search(
    db: &DbPool,
    worker: &WorkerClient,
    query: &SearchQuery,
) -> Result<Vec<SearchResult>, String> {
    // Get embedding from worker
    let embedding = worker
        .embed_text(&query.text)
        .await
        .map_err(|e| format!("Embed failed: {}", e))?;

    let embedding_blob: Vec<u8> = embedding
        .iter()
        .flat_map(|f| f.to_le_bytes())
        .collect();

    let conn = db.get().map_err(|e| e.to_string())?;
    let limit = query.limit.unwrap_or(20);

    let sql = "SELECT ts.id, ts.conversation_id, c.started_at, ts.raw_text, ts.started_at,
                      sp.display_name, se.distance
               FROM (
                   SELECT segment_id, vec_distance_cosine(embedding, ?1) as distance
                   FROM segment_embeddings
                   ORDER BY distance
                   LIMIT ?2
               ) se
               JOIN transcript_segments ts ON ts.id = se.segment_id
               JOIN conversations c ON c.id = ts.conversation_id
               LEFT JOIN speaker_instances si ON ts.speaker_instance_id = si.id
               LEFT JOIN speaker_profiles sp ON si.speaker_profile_id = sp.id
               WHERE se.distance < 0.4
                 AND (?3 IS NULL OR c.started_at >= ?3)
                 AND (?4 IS NULL OR c.started_at <= ?4)
               ORDER BY se.distance";

    let mut stmt = conn.prepare(sql).map_err(|e| e.to_string())?;

    let rows = stmt
        .query_map(
            params![embedding_blob, limit, query.date_from, query.date_to],
            |row| {
                let distance: f64 = row.get(6)?;
                Ok(SearchResult {
                    segment_id: row.get(0)?,
                    conversation_id: row.get(1)?,
                    conversation_started_at: row.get(2)?,
                    text: row.get(3)?,
                    started_at: row.get(4)?,
                    speaker_display_name: row.get(5)?,
                    match_type: "semantic".to_string(),
                    score: 1.0 - distance,
                })
            },
        )
        .map_err(|e| e.to_string())?;

    let mut results = Vec::new();
    for row in rows {
        results.push(row.map_err(|e| e.to_string())?);
    }
    Ok(results)
}

async fn hybrid_search(
    db: &DbPool,
    worker: &WorkerClient,
    query: &SearchQuery,
) -> Result<Vec<SearchResult>, String> {
    // Run both in parallel
    let kw_query = SearchQuery {
        mode: SearchMode::Keyword,
        limit: Some(query.limit.unwrap_or(20) * 2),
        ..query.clone()
    };
    let sem_query = SearchQuery {
        mode: SearchMode::Semantic,
        limit: Some(query.limit.unwrap_or(20) * 2),
        ..query.clone()
    };

    let kw_results = keyword_search(db, &kw_query).unwrap_or_default();
    let sem_results = semantic_search(db, worker, &sem_query).await.unwrap_or_default();

    // RRF combination
    let mut scores: std::collections::HashMap<String, (SearchResult, f64)> =
        std::collections::HashMap::new();

    for (rank, result) in kw_results.iter().enumerate() {
        let rrf_score = 1.0 / (60.0 + rank as f64 + 1.0);
        let entry = scores.entry(result.segment_id.clone()).or_insert_with(|| {
            let mut r = result.clone();
            r.match_type = "hybrid".to_string();
            (r, 0.0)
        });
        entry.1 += rrf_score;
    }

    for (rank, result) in sem_results.iter().enumerate() {
        let rrf_score = 1.0 / (60.0 + rank as f64 + 1.0);
        let entry = scores.entry(result.segment_id.clone()).or_insert_with(|| {
            let mut r = result.clone();
            r.match_type = "hybrid".to_string();
            (r, 0.0)
        });
        entry.1 += rrf_score;
    }

    let mut results: Vec<SearchResult> = scores
        .into_values()
        .map(|(mut r, score)| {
            r.score = score;
            r.match_type = "hybrid".to_string();
            r
        })
        .collect();

    results.sort_by(|a, b| b.score.partial_cmp(&a.score).unwrap());
    let limit = query.limit.unwrap_or(20) as usize;
    results.truncate(limit);

    Ok(results)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::db::connection::create_pool;
    use crate::db::migrations::run_migrations;
    use tempfile::tempdir;

    fn setup_test_db() -> (DbPool, tempfile::TempDir) {
        let tmp = tempdir().unwrap();
        let db_path = tmp.path().join("test.db");
        let migrations_dir = tmp.path().join("migrations");
        std::fs::create_dir_all(&migrations_dir).unwrap();

        // Write minimal schema for testing (no schema_versions insert - migration runner handles that)
        let schema = r#"
            PRAGMA journal_mode = WAL;
            PRAGMA foreign_keys = ON;
            CREATE TABLE IF NOT EXISTS schema_versions (version INTEGER PRIMARY KEY, applied_at INTEGER NOT NULL);
            CREATE TABLE conversations (id TEXT PRIMARY KEY, started_at INTEGER NOT NULL, ended_at INTEGER, title TEXT, summary TEXT, topic_tags TEXT DEFAULT '[]', audio_path TEXT, created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL);
            CREATE TABLE speaker_profiles (id TEXT PRIMARY KEY, display_name TEXT, is_user INTEGER NOT NULL DEFAULT 0, embedding BLOB, embedding_count INTEGER NOT NULL DEFAULT 0, notes TEXT, created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL);
            CREATE TABLE speaker_instances (id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE, diarization_label TEXT NOT NULL, speaker_profile_id TEXT REFERENCES speaker_profiles(id), confidence REAL, segment_count INTEGER NOT NULL DEFAULT 0, created_at INTEGER NOT NULL);
            CREATE TABLE transcript_segments (id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE, speaker_instance_id TEXT REFERENCES speaker_instances(id), started_at INTEGER NOT NULL, ended_at INTEGER NOT NULL, raw_text TEXT NOT NULL, normalized_text TEXT, confidence REAL, created_at INTEGER NOT NULL);
            CREATE VIRTUAL TABLE transcript_fts USING fts5(raw_text, segment_id, conversation_id, tokenize='porter unicode61');
            CREATE TRIGGER trig_fts_insert AFTER INSERT ON transcript_segments BEGIN INSERT INTO transcript_fts(raw_text, segment_id, conversation_id) VALUES (new.raw_text, new.id, new.conversation_id); END;
        "#;
        std::fs::write(migrations_dir.join("001_test.sql"), schema).unwrap();

        let pool = create_pool(&db_path).unwrap();
        run_migrations(&pool, &migrations_dir).unwrap();
        (pool, tmp)
    }

    #[test]
    fn test_keyword_search_returns_matching_segments() {
        let (pool, _tmp) = setup_test_db();
        let conn = pool.get().unwrap();

        conn.execute("INSERT INTO conversations VALUES ('c1', 1000, 2000, NULL, NULL, '[]', NULL, 1000, 1000)", []).unwrap();
        conn.execute("INSERT INTO transcript_segments VALUES ('s1', 'c1', NULL, 1000, 1500, 'hello world test', NULL, NULL, 1000)", []).unwrap();

        let query = SearchQuery {
            text: "hello".to_string(),
            mode: SearchMode::Keyword,
            speaker_profile_id: None,
            date_from: None,
            date_to: None,
            topic_tag: None,
            limit: Some(10),
        };

        let results = keyword_search(&pool, &query).unwrap();
        assert!(!results.is_empty());
        assert_eq!(results[0].segment_id, "s1");
    }

    #[test]
    fn test_search_respects_date_filter() {
        let (pool, _tmp) = setup_test_db();
        let conn = pool.get().unwrap();

        conn.execute("INSERT INTO conversations VALUES ('c1', 1000, 2000, NULL, NULL, '[]', NULL, 1000, 1000)", []).unwrap();
        conn.execute("INSERT INTO transcript_segments VALUES ('s1', 'c1', NULL, 1000, 1500, 'searchterm', NULL, NULL, 1000)", []).unwrap();

        // date_from after conversation → no results
        let query = SearchQuery {
            text: "searchterm".to_string(),
            mode: SearchMode::Keyword,
            speaker_profile_id: None,
            date_from: Some(9999000),
            date_to: None,
            topic_tag: None,
            limit: Some(10),
        };

        let results = keyword_search(&pool, &query).unwrap();
        assert!(results.is_empty());
    }
}
