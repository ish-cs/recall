use crate::config::AppConfig;
use crate::db::models::{DeleteScope, DeletionSummary, StorageUsage};
use crate::db::DbPool;
use rusqlite::params;
use std::path::Path;
use tauri::State;

#[tauri::command]
pub async fn get_storage_usage(
    _config: State<'_, AppConfig>,
    db: State<'_, DbPool>,
) -> Result<StorageUsage, String> {
    let config = _config.inner().clone();
    let audio_bytes = dir_size(&config.audio_dir);
    let models_bytes = dir_size(&config.models_dir);
    let transcript_db_bytes = std::fs::metadata(&config.db_path)
        .map(|m| m.len())
        .unwrap_or(0);

    Ok(StorageUsage {
        audio_bytes,
        transcript_db_bytes,
        models_bytes,
    })
}

#[tauri::command]
pub async fn delete_data_by_age(
    db: State<'_, DbPool>,
    config: State<'_, AppConfig>,
    older_than_days: u32,
    scope: DeleteScope,
) -> Result<DeletionSummary, String> {
    let cutoff_ms = {
        let now = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_millis() as i64;
        now - (older_than_days as i64 * 24 * 60 * 60 * 1000)
    };

    let conn = db.get().map_err(|e| e.to_string())?;

    let old_conv_ids: Vec<(String, Option<String>)> = {
        let mut stmt = conn
            .prepare("SELECT id, audio_path FROM conversations WHERE started_at < ?1")
            .map_err(|e| e.to_string())?;
        let rows: Vec<_> = stmt
            .query_map(params![cutoff_ms], |row| Ok((row.get(0)?, row.get(1)?)))
            .map_err(|e| e.to_string())?
            .filter_map(|r| r.ok())
            .collect();
        rows
    };

    let mut audio_files_deleted = 0u64;
    let mut bytes_freed = 0u64;
    let mut conversations_deleted = 0u64;
    let mut segments_deleted = 0u64;

    for (conv_id, audio_path) in &old_conv_ids {
        match scope {
            DeleteScope::Audio | DeleteScope::Both => {
                if let Some(path) = audio_path {
                    if let Ok(meta) = std::fs::metadata(path) {
                        bytes_freed += meta.len();
                    }
                    if std::fs::remove_file(path).is_ok() {
                        audio_files_deleted += 1;
                    }
                }
            }
            DeleteScope::Transcripts => {}
        }

        match scope {
            DeleteScope::Transcripts | DeleteScope::Both => {
                let seg_count: i64 = conn
                    .query_row(
                        "SELECT COUNT(*) FROM transcript_segments WHERE conversation_id = ?1",
                        params![conv_id],
                        |r| r.get(0),
                    )
                    .unwrap_or(0);
                segments_deleted += seg_count as u64;

                conn.execute("DELETE FROM conversations WHERE id = ?1", params![conv_id])
                    .map_err(|e| e.to_string())?;
                conversations_deleted += 1;
            }
            DeleteScope::Audio => {}
        }
    }

    if matches!(scope, DeleteScope::Audio) {
        conn.execute(
            "UPDATE conversations SET audio_path = NULL WHERE started_at < ?1",
            params![cutoff_ms],
        )
        .map_err(|e| e.to_string())?;
    }

    Ok(DeletionSummary {
        conversations_deleted,
        segments_deleted,
        audio_files_deleted,
        bytes_freed,
    })
}

#[tauri::command]
pub async fn export_transcripts(
    db: State<'_, DbPool>,
    output_path: String,
) -> Result<(), String> {
    let conn = db.get().map_err(|e| e.to_string())?;

    let conversations: Vec<serde_json::Value> = {
        let mut stmt = conn
            .prepare("SELECT id, started_at, ended_at, title, summary, topic_tags FROM conversations ORDER BY started_at")
            .map_err(|e| e.to_string())?;
        let rows: Vec<_> = stmt
            .query_map([], |row| {
                Ok(serde_json::json!({
                    "id": row.get::<_, String>(0)?,
                    "started_at": row.get::<_, i64>(1)?,
                    "ended_at": row.get::<_, Option<i64>>(2)?,
                    "title": row.get::<_, Option<String>>(3)?,
                    "summary": row.get::<_, Option<String>>(4)?,
                    "topic_tags": row.get::<_, String>(5).unwrap_or("[]".to_string()),
                }))
            })
            .map_err(|e| e.to_string())?
            .filter_map(|r| r.ok())
            .collect();
        rows
    };

    let segments: Vec<serde_json::Value> = {
        let mut stmt = conn
            .prepare("SELECT id, conversation_id, started_at, ended_at, raw_text, confidence FROM transcript_segments ORDER BY started_at")
            .map_err(|e| e.to_string())?;
        let rows: Vec<_> = stmt
            .query_map([], |row| {
                Ok(serde_json::json!({
                    "id": row.get::<_, String>(0)?,
                    "conversation_id": row.get::<_, String>(1)?,
                    "started_at": row.get::<_, i64>(2)?,
                    "ended_at": row.get::<_, i64>(3)?,
                    "text": row.get::<_, String>(4)?,
                    "confidence": row.get::<_, Option<f64>>(5)?,
                }))
            })
            .map_err(|e| e.to_string())?
            .filter_map(|r| r.ok())
            .collect();
        rows
    };

    let speakers: Vec<serde_json::Value> = {
        let mut stmt = conn
            .prepare("SELECT id, display_name, is_user, created_at FROM speaker_profiles")
            .map_err(|e| e.to_string())?;
        let rows: Vec<_> = stmt
            .query_map([], |row| {
                Ok(serde_json::json!({
                    "id": row.get::<_, String>(0)?,
                    "display_name": row.get::<_, Option<String>>(1)?,
                    "is_user": row.get::<_, i64>(2)? != 0,
                    "created_at": row.get::<_, i64>(3)?,
                }))
            })
            .map_err(|e| e.to_string())?
            .filter_map(|r| r.ok())
            .collect();
        rows
    };

    let export = serde_json::json!({
        "conversations": conversations,
        "segments": segments,
        "speakers": speakers,
    });

    std::fs::write(&output_path, serde_json::to_string_pretty(&export).unwrap())
        .map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn delete_all_data(
    db: State<'_, DbPool>,
    config: State<'_, AppConfig>,
) -> Result<(), String> {
    let audio_dir = config.audio_dir.clone();
    if audio_dir.exists() {
        std::fs::remove_dir_all(&audio_dir).map_err(|e| e.to_string())?;
        std::fs::create_dir_all(&audio_dir).map_err(|e| e.to_string())?;
    }

    let conn = db.get().map_err(|e| e.to_string())?;
    conn.execute_batch("
        DELETE FROM transcript_segments;
        DELETE FROM speaker_instances;
        DELETE FROM speaker_embeddings;
        DELETE FROM speaker_profiles;
        DELETE FROM conversations;
        DELETE FROM topic_tags;
        DELETE FROM conversation_topic_links;
        UPDATE app_settings SET value = 'false' WHERE key = 'onboarding_complete';
    ")
    .map_err(|e| e.to_string())
}

fn dir_size(path: &Path) -> u64 {
    if !path.exists() {
        return 0;
    }
    walkdir_size(path)
}

fn walkdir_size(path: &Path) -> u64 {
    let mut total = 0u64;
    if let Ok(entries) = std::fs::read_dir(path) {
        for entry in entries.flatten() {
            let p = entry.path();
            if p.is_dir() {
                total += walkdir_size(&p);
            } else if let Ok(meta) = std::fs::metadata(&p) {
                total += meta.len();
            }
        }
    }
    total
}
