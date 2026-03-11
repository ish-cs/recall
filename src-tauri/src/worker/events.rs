use crate::worker::WorkerClient;
use futures_util::StreamExt;
use tauri::{AppHandle, Emitter};
use tokio::time::{sleep, Duration};

pub async fn sse_listener_task(client: WorkerClient, app: AppHandle) {
    loop {
        match connect_and_stream(&client, &app).await {
            Ok(_) => log::info!("SSE stream ended, reconnecting..."),
            Err(e) => log::error!("SSE stream error: {}, reconnecting in 2s", e),
        }
        sleep(Duration::from_secs(2)).await;
    }
}

async fn connect_and_stream(client: &WorkerClient, app: &AppHandle) -> anyhow::Result<()> {
    let base = client
        .base_url()
        .await
        .ok_or_else(|| anyhow::anyhow!("Worker not ready for SSE"))?;

    let url = format!("{}/events", base);
    log::info!("Connecting to SSE stream: {}", url);

    let reqwest_client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(30)) // 30 sec timeout for initial connection
        .build()?;

    let result = reqwest_client
        .get(&url)
        .header("Accept", "text/event-stream")
        .header("Cache-Control", "no-cache")
        .send()
        .await;

    let response = match result {
        Ok(r) => {
            log::info!("SSE response status: {}", r.status());
            log::info!("SSE response headers: {:?}", r.headers());
            r
        }
        Err(e) => {
            return Err(anyhow::anyhow!("SSE request failed: {}", e));
        }
    };
    let mut stream = response.bytes_stream();

    let mut buffer = String::new();

    while let Some(chunk) = stream.next().await {
        let chunk = match chunk {
            Ok(c) => c,
            Err(e) => {
                log::error!("SSE stream read error: {}", e);
                return Err(anyhow::anyhow!("SSE stream read error: {}", e));
            }
        };
        let text = match std::str::from_utf8(&chunk) {
            Ok(t) => t,
            Err(e) => {
                log::error!("SSE UTF-8 decode error: {}", e);
                continue;
            }
        };
        buffer.push_str(text);

        // Process complete SSE messages (terminated by \n\n)
        while let Some(pos) = buffer.find("\n\n") {
            let message = buffer[..pos].to_string();
            buffer = buffer[pos + 2..].to_string();
            process_sse_message(&message, app);
        }
    }

    Ok(())
}

fn process_sse_message(message: &str, app: &AppHandle) {
    let mut event_type = String::from("message");
    let mut data = String::new();

    for line in message.lines() {
        if let Some(t) = line.strip_prefix("event: ") {
            event_type = t.trim().to_string();
        } else if let Some(d) = line.strip_prefix("data: ") {
            data = d.trim().to_string();
        }
    }

    if data.is_empty() {
        return;
    }

    // Parse the JSON data to get the type field
    if let Ok(json) = serde_json::from_str::<serde_json::Value>(&data) {
        let type_field = json
            .get("type")
            .and_then(|t| t.as_str())
            .unwrap_or(&event_type);

        // Map SSE event type to Tauri event name (replace . with :)
        let tauri_event = type_field.replace('.', ":");

        log::debug!("SSE → Tauri event: {}", tauri_event);

        if let Err(e) = app.emit(&tauri_event, &json) {
            log::error!("Failed to emit Tauri event {}: {}", tauri_event, e);
        }
    }
}
