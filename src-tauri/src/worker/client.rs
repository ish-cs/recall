use reqwest::Client;
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use tokio::sync::RwLock;

#[derive(Debug, Clone)]
pub struct WorkerClient {
    client: Client,
    base_url: Arc<RwLock<Option<String>>>,
}

impl WorkerClient {
    pub fn new() -> Self {
        WorkerClient {
            client: Client::builder()
                .timeout(std::time::Duration::from_secs(30))
                .build()
                .expect("Failed to build HTTP client"),
            base_url: Arc::new(RwLock::new(None)),
        }
    }

    pub async fn set_port(&self, port: u16) {
        let mut url = self.base_url.write().await;
        *url = Some(format!("http://127.0.0.1:{}", port));
    }

    pub async fn base_url(&self) -> Option<String> {
        self.base_url.read().await.clone()
    }

    async fn url(&self, path: &str) -> anyhow::Result<String> {
        self.base_url()
            .await
            .map(|base| format!("{}{}", base, path))
            .ok_or_else(|| anyhow::anyhow!("Worker not ready"))
    }

    pub async fn post_empty(&self, path: &str) -> anyhow::Result<serde_json::Value> {
        let url = self.url(path).await?;
        let resp = self.client.post(&url).json(&serde_json::json!({})).send().await?;
        Ok(resp.json().await?)
    }

    pub async fn get_json(&self, path: &str) -> anyhow::Result<serde_json::Value> {
        let url = self.url(path).await?;
        let resp = self.client.get(&url).send().await?;
        Ok(resp.json().await?)
    }

    pub async fn post_json<B: Serialize>(
        &self,
        path: &str,
        body: &B,
    ) -> anyhow::Result<serde_json::Value> {
        let url = self.url(path).await?;
        let resp = self.client.post(&url).json(body).send().await?;
        Ok(resp.json().await?)
    }

    pub async fn get_recording_status(&self) -> anyhow::Result<PipelineStatus> {
        let val = self.get_json("/pipeline/status").await?;
        Ok(serde_json::from_value(val)?)
    }

    pub async fn embed_text(&self, text: &str) -> anyhow::Result<Vec<f32>> {
        #[derive(Serialize)]
        struct EmbedReq<'a> { text: &'a str }
        #[derive(Deserialize)]
        struct EmbedResp { embedding: Vec<f32> }

        let url = self.url("/embed").await?;
        let resp: EmbedResp = self.client
            .post(&url)
            .json(&EmbedReq { text })
            .send()
            .await?
            .json()
            .await?;
        Ok(resp.embedding)
    }
}

#[derive(Debug, Deserialize, Clone)]
pub struct PipelineStatus {
    pub recording: bool,
    pub paused: bool,
    pub current_conversation_id: Option<String>,
    pub hot_queue_depth: Option<i64>,
    pub cold_queue_depth: Option<i64>,
    pub models_ready: bool,
}
