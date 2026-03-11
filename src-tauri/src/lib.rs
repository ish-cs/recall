mod audio;
mod commands;
mod config;
mod db;
mod worker;

use config::AppConfig;
use db::{connection::create_pool, migrations::run_migrations, DbPool};
use std::path::PathBuf;
use std::sync::{Arc, Mutex};
use tauri::{
    menu::{Menu, MenuItem},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    AppHandle, Emitter, Manager,
};
use worker::{
    events::sse_listener_task,
    process::{WorkerProcess, spawn_with_retry},
    WorkerClient,
};

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    env_logger::init();

    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .setup(|app| {
            // Initialize config
            let config = AppConfig::new().expect("Failed to initialize app config");

            // Initialize DB
            let pool = create_pool(&config.db_path).expect("Failed to create DB pool");

            // Run migrations
            let migrations_dir = get_migrations_dir(app);
            if let Err(e) = run_migrations(&pool, &migrations_dir) {
                log::error!("Migration failed: {}", e);
                // Show error dialog? For now, just panic.
                panic!("Database migration failed: {}", e);
            }

            // Initialize worker client
            let worker_client = WorkerClient::new();

            // Spawn Python worker
            let worker_process = Arc::new(Mutex::new(WorkerProcess::new()));
            let ml_worker_path = get_ml_worker_path(app);
            let wc = worker_client.clone();
            let wp = worker_process.clone();
            let app_handle = app.handle().clone();

            tauri::async_runtime::spawn(async move {
                match spawn_with_retry(ml_worker_path, wp).await {
                    Ok(port) => {
                        wc.set_port(port).await;
                        log::info!("Worker ready on port {}", port);

                        // Start SSE listener
                        let wc2 = wc.clone();
                        tauri::async_runtime::spawn(sse_listener_task(wc2, app_handle));
                    }
                    Err(e) => {
                        log::error!("Failed to start worker: {}", e);
                    }
                }
            });

            // Register state
            app.manage(pool);
            app.manage(worker_client);
            app.manage(config);
            app.manage(worker_process);

            // Set up tray icon
            setup_tray(app)?;

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            commands::recording::start_recording,
            commands::recording::stop_recording,
            commands::recording::pause_recording,
            commands::recording::resume_recording,
            commands::recording::get_recording_status,
            commands::conversations::list_conversations,
            commands::conversations::get_conversation,
            commands::conversations::delete_conversation,
            commands::conversations::split_conversation,
            commands::search::search,
            commands::speakers::list_speaker_profiles,
            commands::speakers::rename_speaker_profile,
            commands::speakers::merge_speaker_profiles,
            commands::speakers::delete_speaker_profile,
            commands::settings::get_setting,
            commands::settings::set_setting,
            commands::storage::get_storage_usage,
            commands::storage::delete_data_by_age,
            commands::storage::export_transcripts,
            commands::storage::delete_all_data,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

fn get_migrations_dir(app: &tauri::App) -> PathBuf {
    // In dev, use the project root migrations/ dir
    let resource_dir = app.path().resource_dir().unwrap_or_default();
    let candidate = resource_dir.join("migrations");
    if candidate.exists() {
        return candidate;
    }
    // Fallback: relative to executable
    std::env::current_dir()
        .unwrap_or_default()
        .join("migrations")
}

fn get_ml_worker_path(_app: &tauri::App) -> String {
    if let Ok(path) = std::env::var("RECALL_ML_WORKER_PATH") {
        return path;
    }

    // In dev, executable is in src-tauri/target/debug/, so go up to project root
    let exe_dir = std::env::current_exe()
        .ok()
        .and_then(|p| p.parent().map(|p| p.to_path_buf()))
        .unwrap_or_default();

    // Try project root (three levels up from src-tauri/target/debug/recall)
    let candidate = exe_dir
        .parent() // target/
        .and_then(|p| p.parent()) // src-tauri/
        .and_then(|p| p.parent()) // project root
        .map(|p| p.join("ml-worker").join("main.py"));

    candidate
        .map(|p| p.to_string_lossy().to_string())
        .unwrap_or_else(|| "ml-worker/main.py".to_string())
}

fn setup_tray(app: &tauri::App) -> tauri::Result<()> {
    let open = MenuItem::with_id(app, "open", "Open Recall", true, None::<&str>)?;
    let pause = MenuItem::with_id(app, "pause", "Pause Recording", true, None::<&str>)?;
    let stop = MenuItem::with_id(app, "stop", "Stop Recording", true, None::<&str>)?;
    let quit = MenuItem::with_id(app, "quit", "Quit", true, None::<&str>)?;

    let menu = Menu::with_items(app, &[&open, &pause, &stop, &quit])?;

    TrayIconBuilder::new()
        .menu(&menu)
        .on_menu_event(|app, event| match event.id.as_ref() {
            "open" => {
                if let Some(window) = app.get_webview_window("main") {
                    let _ = window.show();
                    let _ = window.set_focus();
                }
            }
            "pause" => {
                let _ = app.emit("tray:pause", ());
            }
            "stop" => {
                let _ = app.emit("tray:stop", ());
            }
            "quit" => {
                app.exit(0);
            }
            _ => {}
        })
        .on_tray_icon_event(|tray, event| {
            if let TrayIconEvent::Click {
                button: MouseButton::Left,
                button_state: MouseButtonState::Up,
                ..
            } = event
            {
                let app = tray.app_handle();
                if let Some(window) = app.get_webview_window("main") {
                    let _ = window.show();
                    let _ = window.set_focus();
                }
            }
        })
        .build(app)?;

    Ok(())
}
