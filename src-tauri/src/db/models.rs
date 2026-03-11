use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Conversation {
    pub id: String,
    pub started_at: i64,
    pub ended_at: Option<i64>,
    pub title: Option<String>,
    pub summary: Option<String>,
    pub topic_tags: Vec<String>,
    pub audio_path: Option<String>,
    pub created_at: i64,
    pub updated_at: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ConversationSummary {
    pub id: String,
    pub started_at: i64,
    pub ended_at: Option<i64>,
    pub title: Option<String>,
    pub summary: Option<String>,
    pub topic_tags: Vec<String>,
    pub segment_count: i64,
    pub speaker_count: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct TranscriptSegment {
    pub id: String,
    pub conversation_id: String,
    pub speaker_instance_id: Option<String>,
    pub started_at: i64,
    pub ended_at: i64,
    pub text: String,
    pub confidence: Option<f64>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SpeakerInstance {
    pub id: String,
    pub conversation_id: String,
    pub diarization_label: String,
    pub speaker_profile_id: Option<String>,
    pub speaker_display_name: Option<String>,
    pub confidence: Option<f64>,
    pub segment_count: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ConversationDetail {
    pub id: String,
    pub started_at: i64,
    pub ended_at: Option<i64>,
    pub title: Option<String>,
    pub summary: Option<String>,
    pub topic_tags: Vec<String>,
    pub segment_count: i64,
    pub speaker_count: i64,
    pub segments: Vec<TranscriptSegment>,
    pub speakers: Vec<SpeakerInstance>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SpeakerProfile {
    pub id: String,
    pub display_name: Option<String>,
    pub is_user: bool,
    pub segment_count: i64,
    pub conversation_count: i64,
    pub created_at: i64,
    pub updated_at: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SearchResult {
    pub segment_id: String,
    pub conversation_id: String,
    pub conversation_started_at: i64,
    pub text: String,
    pub started_at: i64,
    pub speaker_display_name: Option<String>,
    pub match_type: String,
    pub score: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct StorageUsage {
    pub audio_bytes: u64,
    pub transcript_db_bytes: u64,
    pub models_bytes: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct RecordingStatus {
    pub recording: bool,
    pub paused: bool,
    pub current_conversation_id: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum SearchMode {
    Keyword,
    Semantic,
    Hybrid,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SearchQuery {
    pub text: String,
    pub mode: SearchMode,
    pub speaker_profile_id: Option<String>,
    pub date_from: Option<i64>,
    pub date_to: Option<i64>,
    pub topic_tag: Option<String>,
    pub limit: Option<i64>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum DeleteScope {
    Audio,
    Transcripts,
    Both,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DeletionSummary {
    pub conversations_deleted: u64,
    pub segments_deleted: u64,
    pub audio_files_deleted: u64,
    pub bytes_freed: u64,
}
