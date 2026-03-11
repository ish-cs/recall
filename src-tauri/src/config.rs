use std::path::PathBuf;

#[derive(Clone, Debug)]
pub struct AppConfig {
    pub app_support_dir: PathBuf,
    pub db_path: PathBuf,
    pub audio_dir: PathBuf,
    pub models_dir: PathBuf,
    pub logs_dir: PathBuf,
}

impl AppConfig {
    pub fn new() -> anyhow::Result<Self> {
        let app_support_dir = if let Ok(path) = std::env::var("RECALL_DB_PATH") {
            PathBuf::from(path).parent().unwrap_or(&PathBuf::from("/tmp")).to_path_buf()
        } else {
            let home = dirs_next::data_local_dir()
                .or_else(|| dirs_next::home_dir().map(|h| h.join("Library/Application Support")))
                .unwrap_or_else(|| PathBuf::from("/tmp"));
            home.join("Recall")
        };

        let db_path = if let Ok(path) = std::env::var("RECALL_DB_PATH") {
            PathBuf::from(path)
        } else {
            app_support_dir.join("recall.db")
        };

        let audio_dir = if let Ok(path) = std::env::var("RECALL_AUDIO_PATH") {
            PathBuf::from(path)
        } else {
            app_support_dir.join("audio")
        };

        let models_dir = app_support_dir.join("models");
        let logs_dir = app_support_dir.join("logs");

        std::fs::create_dir_all(&app_support_dir)?;
        std::fs::create_dir_all(&audio_dir)?;
        std::fs::create_dir_all(&models_dir)?;
        std::fs::create_dir_all(&logs_dir)?;

        Ok(AppConfig {
            app_support_dir,
            db_path,
            audio_dir,
            models_dir,
            logs_dir,
        })
    }
}
