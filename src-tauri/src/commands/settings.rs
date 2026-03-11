use crate::db::DbPool;
use rusqlite::params;
use tauri::State;

#[tauri::command]
pub async fn get_setting(db: State<'_, DbPool>, key: String) -> Result<Option<String>, String> {
    let conn = db.get().map_err(|e| e.to_string())?;
    let result: Result<String, _> = conn.query_row(
        "SELECT value FROM app_settings WHERE key = ?1",
        params![key],
        |row| row.get(0),
    );
    match result {
        Ok(value) => Ok(Some(value)),
        Err(rusqlite::Error::QueryReturnedNoRows) => Ok(None),
        Err(e) => Err(format!("Failed to get setting '{}': {}", key, e)),
    }
}

#[tauri::command]
pub async fn set_setting(
    db: State<'_, DbPool>,
    key: String,
    value: String,
) -> Result<(), String> {
    let conn = db.get().map_err(|e| e.to_string())?;
    conn.execute(
        "INSERT INTO app_settings (key, value) VALUES (?1, ?2)
         ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        params![key, value],
    )
    .map(|_| ())
    .map_err(|e| e.to_string())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::db::connection::create_pool;
    use tempfile::tempdir;

    fn setup_settings_db() -> (DbPool, tempfile::TempDir) {
        let tmp = tempdir().unwrap();
        let db_path = tmp.path().join("test.db");
        let pool = create_pool(&db_path).unwrap();
        let conn = pool.get().unwrap();
        conn.execute_batch("
            PRAGMA journal_mode = WAL;
            CREATE TABLE app_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            INSERT INTO app_settings VALUES ('test_key', 'initial_value');
        ").unwrap();
        (pool, tmp)
    }

    #[tokio::test]
    async fn test_get_setting() {
        // Direct test without Tauri State
        let (pool, _tmp) = setup_settings_db();
        let conn = pool.get().unwrap();
        let value: String = conn.query_row(
            "SELECT value FROM app_settings WHERE key = ?1",
            params!["test_key"],
            |r| r.get(0),
        ).unwrap();
        assert_eq!(value, "initial_value");
    }

    #[tokio::test]
    async fn test_set_setting() {
        let (pool, _tmp) = setup_settings_db();
        let conn = pool.get().unwrap();
        conn.execute(
            "INSERT INTO app_settings (key, value) VALUES (?1, ?2)
             ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            params!["test_key", "new_value"],
        ).unwrap();
        let value: String = conn.query_row(
            "SELECT value FROM app_settings WHERE key = ?1",
            params!["test_key"],
            |r| r.get(0),
        ).unwrap();
        assert_eq!(value, "new_value");
    }
}
