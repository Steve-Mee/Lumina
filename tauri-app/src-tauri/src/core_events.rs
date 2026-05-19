use std::fs::{self, OpenOptions};
use std::io::Write;
use std::path::{Path, PathBuf};

use serde::Serialize;
use serde_json::Value;

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct AppendCoreEventResult {
    pub ok: bool,
    pub path: String,
}

pub fn resolve_state_directory() -> PathBuf {
    if let Ok(raw) = std::env::var("LUMINA_STATE_DIR") {
        let trimmed = raw.trim();
        if !trimmed.is_empty() {
            return PathBuf::from(trimmed);
        }
    }

    if let Ok(cwd) = std::env::current_dir() {
        if let Some(found) = find_state_directory_from(&cwd) {
            return found;
        }
    }

    PathBuf::from("state")
}

fn find_state_directory_from(start: &Path) -> Option<PathBuf> {
    let mut current = Some(start);

    while let Some(dir) = current {
        let state_dir = dir.join("state");
        if state_dir.is_dir() {
            return Some(state_dir);
        }
        if dir.join("config.yaml").is_file() {
            return Some(state_dir);
        }
        current = dir.parent();
    }

    None
}

fn core_events_path(state_dir: &Path) -> PathBuf {
    state_dir.join("core_events.jsonl")
}

#[tauri::command]
pub fn append_core_event(payload: String) -> Result<AppendCoreEventResult, String> {
    let parsed: Value =
        serde_json::from_str(payload.trim()).map_err(|err| format!("Invalid JSON payload: {err}"))?;

    if !parsed.is_object() {
        return Err("Core event payload must be a JSON object".to_string());
    }

    let state_dir = resolve_state_directory();
    fs::create_dir_all(&state_dir).map_err(|err| format!("Failed to create state directory: {err}"))?;

    let path = core_events_path(&state_dir);
    let line = format!("{}\n", parsed);

    let mut file = OpenOptions::new()
        .create(true)
        .append(true)
        .open(&path)
        .map_err(|err| format!("Failed to open core events log: {err}"))?;

    file.write_all(line.as_bytes())
        .map_err(|err| format!("Failed to append core event: {err}"))?;

    Ok(AppendCoreEventResult {
        ok: true,
        path: path.to_string_lossy().into_owned(),
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::{Mutex, OnceLock};

    static ENV_LOCK: OnceLock<Mutex<()>> = OnceLock::new();

    fn with_env_lock<F: FnOnce()>(f: F) {
        let lock = ENV_LOCK.get_or_init(|| Mutex::new(()));
        let _guard = lock.lock().unwrap_or_else(|poisoned| poisoned.into_inner());
        f();
    }

    #[test]
    fn append_core_event_writes_jsonl_line() {
        with_env_lock(|| {
            let temp_dir = std::env::temp_dir().join(format!(
                "lumina-core-events-test-{}",
                std::process::id()
            ));
            let _ = fs::remove_dir_all(&temp_dir);
            fs::create_dir_all(&temp_dir).expect("create temp state dir");

            std::env::set_var("LUMINA_STATE_DIR", temp_dir.to_string_lossy().as_ref());

            let result = append_core_event(
                r#"{"ts":"2026-05-19T15:00:00.000Z","event":"REAL_SAFE_MODE_ENTER"}"#.to_string(),
            )
            .expect("append should succeed");

            assert!(result.ok);
            let log_path = temp_dir.join("core_events.jsonl");
            assert_eq!(result.path, log_path.to_string_lossy());
            let contents = fs::read_to_string(&log_path).expect("read log");
            assert!(contents.contains("REAL_SAFE_MODE_ENTER"));

            std::env::remove_var("LUMINA_STATE_DIR");
            let _ = fs::remove_dir_all(&temp_dir);
        });
    }

    #[test]
    fn rejects_non_object_payload() {
        let err = append_core_event("[1,2,3]".to_string()).expect_err("array should fail");
        assert!(err.contains("JSON object"));
    }
}
