use crate::db::models::RecordingStatus;
use crate::worker::WorkerClient;
use tauri::State;

#[tauri::command]
pub async fn start_recording(worker: State<'_, WorkerClient>) -> Result<(), String> {
    worker.post_empty("/pipeline/start").await.map(|_| ()).map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn stop_recording(worker: State<'_, WorkerClient>) -> Result<(), String> {
    worker.post_empty("/pipeline/stop").await.map(|_| ()).map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn pause_recording(worker: State<'_, WorkerClient>) -> Result<(), String> {
    worker.post_empty("/pipeline/pause").await.map(|_| ()).map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn resume_recording(worker: State<'_, WorkerClient>) -> Result<(), String> {
    worker.post_empty("/pipeline/resume").await.map(|_| ()).map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn get_recording_status(worker: State<'_, WorkerClient>) -> Result<RecordingStatus, String> {
    match worker.get_recording_status().await {
        Ok(status) => Ok(RecordingStatus {
            recording: status.recording,
            paused: status.paused,
            current_conversation_id: status.current_conversation_id,
        }),
        Err(e) => {
            // Worker may not be ready yet, return default status
            log::warn!("Could not get recording status: {}", e);
            Ok(RecordingStatus {
                recording: false,
                paused: false,
                current_conversation_id: None,
            })
        }
    }
}
