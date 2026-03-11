use std::path::{Path, PathBuf};

pub fn audio_path_for_conversation(audio_dir: &Path, conversation_id: &str, started_at_ms: i64) -> PathBuf {
    let secs = started_at_ms / 1000;
    let dt = time_from_unix(secs);
    audio_dir
        .join(format!("{:04}", dt.0))
        .join(format!("{:02}", dt.1))
        .join(format!("{:02}", dt.2))
        .join(format!("{}.wav", conversation_id))
}

/// Returns (year, month, day) from unix timestamp
fn time_from_unix(secs: i64) -> (i32, u8, u8) {
    // Simple approximation using chrono-style calculation
    // days since epoch
    let days = secs / 86400;
    let year_day = days_to_ymd(days);
    year_day
}

fn days_to_ymd(days: i64) -> (i32, u8, u8) {
    // Algorithm from https://howardhinnant.github.io/date_algorithms.html
    let z = days + 719468;
    let era = if z >= 0 { z } else { z - 146096 } / 146097;
    let doe = z - era * 146097;
    let yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365;
    let y = yoe + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = doy - (153 * mp + 2) / 5 + 1;
    let m = if mp < 10 { mp + 3 } else { mp - 9 };
    let y = if m <= 2 { y + 1 } else { y };
    (y as i32, m as u8, d as u8)
}

pub fn delete_audio_older_than(audio_dir: &Path, cutoff_ms: i64) -> (u64, u64) {
    let mut files_deleted = 0u64;
    let mut bytes_freed = 0u64;

    if !audio_dir.exists() {
        return (0, 0);
    }

    if let Ok(entries) = std::fs::read_dir(audio_dir) {
        for entry in entries.flatten() {
            let path = entry.path();
            if path.is_dir() {
                let (f, b) = delete_audio_older_than(&path, cutoff_ms);
                files_deleted += f;
                bytes_freed += b;
            } else if path.extension().and_then(|s| s.to_str()) == Some("wav") {
                if let Ok(meta) = std::fs::metadata(&path) {
                    if let Ok(modified) = meta.modified() {
                        let modified_ms = modified
                            .duration_since(std::time::UNIX_EPOCH)
                            .unwrap_or_default()
                            .as_millis() as i64;
                        if modified_ms < cutoff_ms {
                            bytes_freed += meta.len();
                            if std::fs::remove_file(&path).is_ok() {
                                files_deleted += 1;
                            }
                        }
                    }
                }
            }
        }
    }

    (files_deleted, bytes_freed)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_audio_path_format() {
        let dir = Path::new("/audio");
        // 2025-01-15 00:00:00 UTC = 1736899200s = 1736899200000ms
        let path = audio_path_for_conversation(dir, "test-uuid", 1736899200000);
        let path_str = path.to_string_lossy();
        assert!(path_str.contains("2025"));
        assert!(path_str.contains("test-uuid.wav"));
    }
}
