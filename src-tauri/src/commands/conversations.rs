use crate::db::models::{ConversationDetail, ConversationSummary, SpeakerInstance, TranscriptSegment};
use crate::db::DbPool;
use rusqlite::params;
use tauri::State;

#[tauri::command]
pub async fn list_conversations(
    db: State<'_, DbPool>,
    limit: i64,
    offset: i64,
    date_from: Option<i64>,
    date_to: Option<i64>,
) -> Result<Vec<ConversationSummary>, String> {
    let conn = db.get().map_err(|e| e.to_string())?;

    let mut query = String::from(
        "SELECT c.id, c.started_at, c.ended_at, c.title, c.summary, c.topic_tags,
                COALESCE((SELECT COUNT(*) FROM transcript_segments WHERE conversation_id = c.id), 0) as segment_count,
                COALESCE((SELECT COUNT(DISTINCT speaker_instance_id) FROM transcript_segments WHERE conversation_id = c.id AND speaker_instance_id IS NOT NULL), 0) as speaker_count
         FROM conversations c
         WHERE 1=1",
    );

    if date_from.is_some() {
        query.push_str(" AND c.started_at >= ?3");
    }
    if date_to.is_some() {
        query.push_str(" AND c.started_at <= ?4");
    }
    query.push_str(" ORDER BY c.started_at DESC LIMIT ?1 OFFSET ?2");

    let mut stmt = conn.prepare(&query).map_err(|e| e.to_string())?;

    let rows = stmt
        .query_map(params![limit, offset, date_from.unwrap_or(0), date_to.unwrap_or(i64::MAX)], |row| {
            let topic_tags_json: String = row.get(5).unwrap_or_else(|_| "[]".to_string());
            let topic_tags: Vec<String> =
                serde_json::from_str(&topic_tags_json).unwrap_or_default();
            Ok(ConversationSummary {
                id: row.get(0)?,
                started_at: row.get(1)?,
                ended_at: row.get(2)?,
                title: row.get(3)?,
                summary: row.get(4)?,
                topic_tags,
                segment_count: row.get(6)?,
                speaker_count: row.get(7)?,
            })
        })
        .map_err(|e| e.to_string())?;

    let mut convs = Vec::new();
    for row in rows {
        convs.push(row.map_err(|e| e.to_string())?);
    }
    Ok(convs)
}

#[tauri::command]
pub async fn get_conversation(
    db: State<'_, DbPool>,
    id: String,
) -> Result<ConversationDetail, String> {
    let conn = db.get().map_err(|e| e.to_string())?;

    let conv: ConversationSummary = conn
        .query_row(
            "SELECT c.id, c.started_at, c.ended_at, c.title, c.summary, c.topic_tags,
                    COALESCE((SELECT COUNT(*) FROM transcript_segments WHERE conversation_id = c.id), 0),
                    COALESCE((SELECT COUNT(DISTINCT speaker_instance_id) FROM transcript_segments WHERE conversation_id = c.id AND speaker_instance_id IS NOT NULL), 0)
             FROM conversations c WHERE c.id = ?1",
            params![id],
            |row| {
                let topic_tags_json: String = row.get(5).unwrap_or_else(|_| "[]".to_string());
                let topic_tags: Vec<String> =
                    serde_json::from_str(&topic_tags_json).unwrap_or_default();
                Ok(ConversationSummary {
                    id: row.get(0)?,
                    started_at: row.get(1)?,
                    ended_at: row.get(2)?,
                    title: row.get(3)?,
                    summary: row.get(4)?,
                    topic_tags,
                    segment_count: row.get(6)?,
                    speaker_count: row.get(7)?,
                })
            },
        )
        .map_err(|e| format!("Conversation not found: {}", e))?;

    let mut seg_stmt = conn
        .prepare(
            "SELECT id, conversation_id, speaker_instance_id, started_at, ended_at,
                    COALESCE(normalized_text, raw_text) as text, confidence
             FROM transcript_segments WHERE conversation_id = ?1
             ORDER BY started_at ASC",
        )
        .map_err(|e| e.to_string())?;

    let segments: Vec<TranscriptSegment> = seg_stmt
        .query_map(params![id], |row| {
            Ok(TranscriptSegment {
                id: row.get(0)?,
                conversation_id: row.get(1)?,
                speaker_instance_id: row.get(2)?,
                started_at: row.get(3)?,
                ended_at: row.get(4)?,
                text: row.get(5)?,
                confidence: row.get(6)?,
            })
        })
        .map_err(|e| e.to_string())?
        .filter_map(|r| r.ok())
        .collect();

    let mut si_stmt = conn
        .prepare(
            "SELECT si.id, si.conversation_id, si.diarization_label, si.speaker_profile_id,
                    sp.display_name, si.confidence, si.segment_count
             FROM speaker_instances si
             LEFT JOIN speaker_profiles sp ON si.speaker_profile_id = sp.id
             WHERE si.conversation_id = ?1",
        )
        .map_err(|e| e.to_string())?;

    let speakers: Vec<SpeakerInstance> = si_stmt
        .query_map(params![id], |row| {
            Ok(SpeakerInstance {
                id: row.get(0)?,
                conversation_id: row.get(1)?,
                diarization_label: row.get(2)?,
                speaker_profile_id: row.get(3)?,
                speaker_display_name: row.get(4)?,
                confidence: row.get(5)?,
                segment_count: row.get(6)?,
            })
        })
        .map_err(|e| e.to_string())?
        .filter_map(|r| r.ok())
        .collect();

    Ok(ConversationDetail {
        id: conv.id,
        started_at: conv.started_at,
        ended_at: conv.ended_at,
        title: conv.title,
        summary: conv.summary,
        topic_tags: conv.topic_tags,
        segment_count: conv.segment_count,
        speaker_count: conv.speaker_count,
        segments,
        speakers,
    })
}

#[tauri::command]
pub async fn delete_conversation(
    db: State<'_, DbPool>,
    id: String,
    delete_audio: bool,
) -> Result<(), String> {
    let conn = db.get().map_err(|e| e.to_string())?;

    if delete_audio {
        let audio_path: Option<String> = conn
            .query_row(
                "SELECT audio_path FROM conversations WHERE id = ?1",
                params![id],
                |row| row.get(0),
            )
            .ok()
            .flatten();

        if let Some(path) = audio_path {
            let _ = std::fs::remove_file(path);
        }
    }

    conn.execute("DELETE FROM conversations WHERE id = ?1", params![id])
        .map_err(|e| e.to_string())?;
    Ok(())
}

#[tauri::command]
pub async fn split_conversation(
    db: State<'_, DbPool>,
    id: String,
    at_segment_id: String,
) -> Result<String, String> {
    let conn = db.get().map_err(|e| e.to_string())?;

    // Get the segment's started_at to use as split point
    let split_at: i64 = conn
        .query_row(
            "SELECT started_at FROM transcript_segments WHERE id = ?1 AND conversation_id = ?2",
            params![at_segment_id, id],
            |row| row.get(0),
        )
        .map_err(|e| format!("Segment not found: {}", e))?;

    let new_id = uuid::Uuid::new_v4().to_string();
    let now_ms = now_millis();

    // Create new conversation starting at split point
    conn.execute(
        "INSERT INTO conversations (id, started_at, ended_at, title, created_at, updated_at, topic_tags)
         SELECT ?1, ?2, ended_at, NULL, ?3, ?3, '[]'
         FROM conversations WHERE id = ?4",
        params![new_id, split_at, now_ms, id],
    )
    .map_err(|e| e.to_string())?;

    // Move segments from split point forward to new conversation
    conn.execute(
        "UPDATE transcript_segments SET conversation_id = ?1 WHERE conversation_id = ?2 AND started_at >= ?3",
        params![new_id, id, split_at],
    )
    .map_err(|e| e.to_string())?;

    // Update original conversation's ended_at
    conn.execute(
        "UPDATE conversations SET ended_at = ?1, updated_at = ?2 WHERE id = ?3",
        params![split_at, now_ms, id],
    )
    .map_err(|e| e.to_string())?;

    Ok(new_id)
}

fn now_millis() -> i64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis() as i64
}
