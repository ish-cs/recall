use crate::db::models::SpeakerProfile;
use crate::db::DbPool;
use crate::worker::WorkerClient;
use rusqlite::params;
use tauri::State;

#[tauri::command]
pub async fn list_speaker_profiles(db: State<'_, DbPool>) -> Result<Vec<SpeakerProfile>, String> {
    let conn = db.get().map_err(|e| e.to_string())?;
    let mut stmt = conn
        .prepare(
            "SELECT sp.id, sp.display_name, sp.is_user, sp.created_at, sp.updated_at,
                    COALESCE((SELECT COUNT(*) FROM speaker_instances si
                              JOIN transcript_segments ts ON ts.speaker_instance_id = si.id
                              WHERE si.speaker_profile_id = sp.id), 0) as segment_count,
                    COALESCE((SELECT COUNT(DISTINCT si.conversation_id) FROM speaker_instances si
                              WHERE si.speaker_profile_id = sp.id), 0) as conversation_count
             FROM speaker_profiles sp
             ORDER BY sp.updated_at DESC",
        )
        .map_err(|e| e.to_string())?;

    let rows = stmt
        .query_map([], |row| {
            Ok(SpeakerProfile {
                id: row.get(0)?,
                display_name: row.get(1)?,
                is_user: row.get::<_, i64>(2)? != 0,
                created_at: row.get(3)?,
                updated_at: row.get(4)?,
                segment_count: row.get(5)?,
                conversation_count: row.get(6)?,
            })
        })
        .map_err(|e| e.to_string())?;

    let mut profiles = Vec::new();
    for row in rows {
        profiles.push(row.map_err(|e| e.to_string())?);
    }
    Ok(profiles)
}

#[tauri::command]
pub async fn rename_speaker_profile(
    db: State<'_, DbPool>,
    id: String,
    display_name: String,
) -> Result<(), String> {
    let conn = db.get().map_err(|e| e.to_string())?;
    let now_ms = now_millis();
    conn.execute(
        "UPDATE speaker_profiles SET display_name = ?1, updated_at = ?2 WHERE id = ?3",
        params![display_name, now_ms, id],
    )
    .map(|_| ())
    .map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn merge_speaker_profiles(
    worker: State<'_, WorkerClient>,
    from_id: String,
    to_id: String,
) -> Result<(), String> {
    worker
        .post_json("/speakers/merge", &serde_json::json!({ "from_profile_id": from_id, "to_profile_id": to_id }))
        .await
        .map(|_| ())
        .map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn delete_speaker_profile(
    db: State<'_, DbPool>,
    id: String,
) -> Result<(), String> {
    let conn = db.get().map_err(|e| e.to_string())?;
    conn.execute("DELETE FROM speaker_profiles WHERE id = ?1", params![id])
        .map(|_| ())
        .map_err(|e| e.to_string())
}

fn now_millis() -> i64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis() as i64
}
