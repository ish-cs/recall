use r2d2::Pool;
use r2d2_sqlite::SqliteConnectionManager;
use std::path::Path;

pub type DbPool = Pool<SqliteConnectionManager>;

pub fn create_pool(db_path: &Path) -> anyhow::Result<DbPool> {
    let manager = SqliteConnectionManager::file(db_path).with_init(|conn| {
        conn.execute_batch("
            PRAGMA journal_mode = WAL;
            PRAGMA foreign_keys = ON;
            PRAGMA synchronous = NORMAL;
            PRAGMA busy_timeout = 5000;
        ")
    });

    let pool = r2d2::Pool::builder()
        .max_size(8)
        .build(manager)
        .map_err(|e| anyhow::anyhow!("Failed to create DB pool: {}", e))?;

    Ok(pool)
}
