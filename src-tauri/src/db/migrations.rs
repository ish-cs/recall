use crate::db::DbPool;
use std::path::Path;

pub fn run_migrations(pool: &DbPool, migrations_dir: &Path) -> anyhow::Result<()> {
    let conn = pool.get()?;

    // Create schema_versions table if it doesn't exist
    conn.execute_batch("
        CREATE TABLE IF NOT EXISTS schema_versions (
            version INTEGER PRIMARY KEY,
            applied_at INTEGER NOT NULL
        );
    ")?;

    // Read migration files sorted by name
    let mut entries: Vec<_> = std::fs::read_dir(migrations_dir)?
        .filter_map(|e| e.ok())
        .filter(|e| {
            e.path().extension().and_then(|s| s.to_str()) == Some("sql")
        })
        .collect();
    entries.sort_by_key(|e| e.file_name());

    for entry in entries {
        let path = entry.path();
        let filename = path.file_name().unwrap().to_string_lossy().to_string();

        // Extract version number from filename (e.g. 001_initial_schema.sql → 1)
        let version: i64 = filename
            .split('_')
            .next()
            .and_then(|s| s.parse().ok())
            .ok_or_else(|| anyhow::anyhow!("Invalid migration filename: {}", filename))?;

        // Check if already applied
        let already_applied: bool = conn
            .query_row(
                "SELECT COUNT(*) FROM schema_versions WHERE version = ?1",
                rusqlite::params![version],
                |row| row.get::<_, i64>(0),
            )
            .map(|count| count > 0)
            .unwrap_or(false);

        if already_applied {
            log::debug!("Migration {} already applied, skipping", filename);
            continue;
        }

        log::info!("Applying migration: {}", filename);
        let sql = std::fs::read_to_string(&path)?;

        // Migration 003 (vector search) requires the sqlite-vec extension.
        // If it fails, skip with a warning rather than crashing the app.
        let optional = filename.starts_with("003");
        match conn.execute_batch(&sql) {
            Ok(_) => {}
            Err(e) if optional => {
                log::warn!("Optional migration {} skipped (extension may not be loaded): {}", filename, e);
                continue;
            }
            Err(e) => return Err(anyhow::anyhow!("Migration {} failed: {}", filename, e)),
        }

        let now_ms = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_millis() as i64;

        conn.execute(
            "INSERT INTO schema_versions (version, applied_at) VALUES (?1, ?2)",
            rusqlite::params![version, now_ms],
        )?;

        log::info!("Migration {} applied successfully", filename);
    }

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::db::connection::create_pool;
    use tempfile::tempdir;

    fn create_test_migrations(dir: &Path) {
        std::fs::write(
            dir.join("001_initial.sql"),
            "CREATE TABLE test_table (id INTEGER PRIMARY KEY, name TEXT);",
        ).unwrap();
        std::fs::write(
            dir.join("002_add_column.sql"),
            "ALTER TABLE test_table ADD COLUMN value TEXT;",
        ).unwrap();
    }

    #[test]
    fn test_migrations_apply_in_order() {
        let tmp = tempdir().unwrap();
        let db_path = tmp.path().join("test.db");
        let migrations_dir = tmp.path().join("migrations");
        std::fs::create_dir_all(&migrations_dir).unwrap();

        create_test_migrations(&migrations_dir);
        let pool = create_pool(&db_path).unwrap();
        run_migrations(&pool, &migrations_dir).unwrap();

        let conn = pool.get().unwrap();
        // Both migrations applied
        let count: i64 = conn
            .query_row("SELECT COUNT(*) FROM schema_versions", [], |r| r.get(0))
            .unwrap();
        assert_eq!(count, 2);

        // Table and column exist
        conn.execute("INSERT INTO test_table (name, value) VALUES ('a', 'b')", []).unwrap();
    }

    #[test]
    fn test_migrations_idempotent_on_rerun() {
        let tmp = tempdir().unwrap();
        let db_path = tmp.path().join("test.db");
        let migrations_dir = tmp.path().join("migrations");
        std::fs::create_dir_all(&migrations_dir).unwrap();

        create_test_migrations(&migrations_dir);
        let pool = create_pool(&db_path).unwrap();

        // Run twice
        run_migrations(&pool, &migrations_dir).unwrap();
        run_migrations(&pool, &migrations_dir).unwrap();

        let conn = pool.get().unwrap();
        let count: i64 = conn
            .query_row("SELECT COUNT(*) FROM schema_versions", [], |r| r.get(0))
            .unwrap();
        assert_eq!(count, 2);
    }
}
