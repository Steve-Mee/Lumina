use std::path::{Path, PathBuf};
use std::process::Command;

use serde::Serialize;

const ENV_OVERRIDE: &str = "NINJATRADER8_PATH";
const EXE_NAME: &str = "NinjaTrader.exe";

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct NinjaTraderDetectResult {
    pub installed: bool,
    pub exe_path: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct NinjaTraderLaunchResult {
    pub launched: bool,
    pub installed: bool,
    pub exe_path: Option<String>,
    pub error: Option<String>,
}

fn candidate_paths() -> Vec<PathBuf> {
    let mut paths = Vec::new();

    if let Ok(override_path) = std::env::var(ENV_OVERRIDE) {
        let trimmed = override_path.trim();
        if !trimmed.is_empty() {
            paths.push(PathBuf::from(trimmed));
        }
    }

    #[cfg(windows)]
    {
        if let Ok(program_files) = std::env::var("ProgramFiles") {
            paths.push(
                PathBuf::from(program_files)
                    .join("NinjaTrader 8")
                    .join("bin")
                    .join(EXE_NAME),
            );
        }

        if let Ok(program_files_x86) = std::env::var("ProgramFiles(x86)") {
            paths.push(
                PathBuf::from(program_files_x86)
                    .join("NinjaTrader 8")
                    .join("bin")
                    .join(EXE_NAME),
            );
        }

        if let Ok(local_app_data) = std::env::var("LOCALAPPDATA") {
            paths.push(
                PathBuf::from(local_app_data)
                    .join("Programs")
                    .join("NinjaTrader 8")
                    .join("bin")
                    .join(EXE_NAME),
            );
        }
    }

    paths
}

pub fn resolve_ninjatrader8_exe() -> Option<PathBuf> {
    resolve_from_candidates(candidate_paths())
}

fn resolve_from_candidates(candidates: impl IntoIterator<Item = PathBuf>) -> Option<PathBuf> {
    candidates.into_iter().find(|path| path.is_file())
}

fn detect_result() -> NinjaTraderDetectResult {
    match resolve_ninjatrader8_exe() {
        Some(path) => NinjaTraderDetectResult {
            installed: true,
            exe_path: Some(path.to_string_lossy().into_owned()),
        },
        None => NinjaTraderDetectResult {
            installed: false,
            exe_path: None,
        },
    }
}

#[tauri::command]
pub fn detect_ninjatrader() -> NinjaTraderDetectResult {
    detect_result()
}

#[tauri::command]
pub fn launch_ninjatrader() -> NinjaTraderLaunchResult {
    let detect = detect_result();

    if !detect.installed {
        return NinjaTraderLaunchResult {
            launched: false,
            installed: false,
            exe_path: None,
            error: None,
        };
    }

    let exe_path = detect.exe_path.clone().unwrap_or_default();
    let path = Path::new(&exe_path);

    match Command::new(path).spawn() {
        Ok(_) => NinjaTraderLaunchResult {
            launched: true,
            installed: true,
            exe_path: detect.exe_path,
            error: None,
        },
        Err(err) => NinjaTraderLaunchResult {
            launched: false,
            installed: true,
            exe_path: detect.exe_path,
            error: Some(format!("Failed to launch NinjaTrader 8: {err}")),
        },
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;
    use std::sync::{Mutex, OnceLock};

    static ENV_LOCK: OnceLock<Mutex<()>> = OnceLock::new();

    fn with_env_lock<F: FnOnce()>(f: F) {
        let lock = ENV_LOCK.get_or_init(|| Mutex::new(()));
        let _guard = lock.lock().unwrap_or_else(|poisoned| poisoned.into_inner());
        f();
    }

    #[test]
    fn resolves_override_path_when_file_exists() {
        with_env_lock(|| {
            let temp_dir = std::env::temp_dir().join(format!(
                "lumina-nt8-test-{}",
                std::process::id()
            ));
            let _ = fs::remove_dir_all(&temp_dir);
            fs::create_dir_all(&temp_dir).expect("create temp dir");

            let exe_path = temp_dir.join(EXE_NAME);
            fs::write(&exe_path, b"fake").expect("write fake exe");

            std::env::set_var(ENV_OVERRIDE, exe_path.to_string_lossy().as_ref());

            let resolved = resolve_ninjatrader8_exe();
            assert_eq!(resolved, Some(exe_path.clone()));

            std::env::remove_var(ENV_OVERRIDE);
            let _ = fs::remove_dir_all(&temp_dir);
        });
    }

    #[test]
    fn returns_none_when_candidates_missing() {
        let resolved = resolve_from_candidates([
            PathBuf::from("C:\\does-not-exist\\NinjaTrader.exe"),
            PathBuf::from("C:\\also-missing\\NinjaTrader 8\\bin\\NinjaTrader.exe"),
        ]);
        assert!(resolved.is_none());
    }
}
