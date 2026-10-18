//! Opt-in local UI diagnostics. No network listener or arbitrary evaluation API.
use serde_json::{json, Value};
use std::{collections::HashSet, fs, io::Write, path::{Path, PathBuf}, sync::{Mutex, atomic::{AtomicU64, Ordering}}, time::{Duration, SystemTime, UNIX_EPOCH}};
use tauri::Manager;

pub struct Agent { directory: Option<PathBuf>, active: Mutex<HashSet<String>> }
fn valid_id(id: &str) -> bool { id.len() == 32 && id.bytes().all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b)) }
fn write_json(path: &Path, value: &Value) -> Result<(), String> {
    let temporary = path.with_extension("pending");
    let bytes = serde_json::to_vec_pretty(value).map_err(|e| e.to_string())?;
    let mut file = fs::OpenOptions::new().write(true).create_new(true).open(&temporary).map_err(|e| e.to_string())?;
    file.write_all(&bytes).and_then(|_| file.sync_all()).map_err(|e| e.to_string())?;
    drop(file);
    fs::rename(temporary, path).map_err(|e| e.to_string())
}
impl Agent {
    pub fn new() -> Result<Self, String> {
        let directory = std::env::var_os("SHOWPSISI_AGENT_DIR").map(PathBuf::from);
        if let Some(path) = &directory {
            if !path.is_absolute() { return Err("Agent directory must be absolute".into()); }
            // create_dir refuses stale sessions, unlike create_dir_all.
            fs::create_dir(path).map_err(|e| format!("Agent session requires a new directory: {e}"))?;
            write_json(&path.join("session.json"), &json!({"schema_version":1,"frontend":"tauri","pid":std::process::id(),
                "methods":["snapshot","capture","action"],"scope":"local UI inspection; no arbitrary eval, engine edits or exports"}))?;
        }
        Ok(Self { directory, active: Mutex::new(HashSet::new()) })
    }
    pub fn enabled(&self) -> bool { self.directory.is_some() }
}
#[tauri::command]
pub fn agent_next(agent: tauri::State<Agent>) -> Result<Value, String> {
    let Some(directory) = &agent.directory else { return Ok(Value::Null); };
    for entry in fs::read_dir(directory).map_err(|e| e.to_string())?.take(4096) {
        let entry = entry.map_err(|e| e.to_string())?;
        let name = entry.file_name().to_string_lossy().into_owned();
        let Some(id) = name.strip_suffix(".request.json").filter(|id| valid_id(id)) else { continue; };
        if directory.join(format!("{id}.consumed.json")).exists() { continue; }
        if entry.metadata().map_err(|e| e.to_string())?.len() > 65536 { continue; }
        let request = fs::read(entry.path()).map_err(|e| e.to_string())?;
        fs::rename(entry.path(), directory.join(format!("{id}.consumed.json"))).map_err(|e| e.to_string())?;
        let request: Value = serde_json::from_slice(&request).unwrap_or(Value::Null);
        if request["id"] != id || !["snapshot","capture","action"].contains(&request["method"].as_str().unwrap_or("")) {
            write_json(&directory.join(format!("{id}.response.json")), &json!({"id":id,"ok":false,"result":{"error":"Invalid UI request"}}))?;
            continue;
        }
        agent.active.lock().map_err(|e| e.to_string())?.insert(id.to_owned());
        return Ok(request);
    }
    Ok(Value::Null)
}
#[tauri::command]
pub fn agent_reply(id: String, result: Value, agent: tauri::State<Agent>) -> Result<(), String> {
    if !valid_id(&id) || !agent.active.lock().map_err(|e| e.to_string())?.remove(&id) { return Err("Request is not active".into()); }
    write_json(&agent.directory.as_ref().ok_or("Agent disabled")?.join(format!("{id}.response.json")),
        &json!({"id":id,"ok":result.get("error").is_none(),"result":result}))
}

#[cfg(windows)]
async fn screenshot(window: tauri::WebviewWindow, path: PathBuf) -> Result<(), String> {
    use windows::{core::PCWSTR, Win32::{System::Com::{IStream, STGM_CREATE, STGM_READWRITE, STGM_SHARE_EXCLUSIVE, STGC_DEFAULT}, UI::Shell::SHCreateStreamOnFileEx}};
    use webview2_com::{CapturePreviewCompletedHandler, Microsoft::Web::WebView2::Win32::COREWEBVIEW2_CAPTURE_PREVIEW_IMAGE_FORMAT_PNG};
    use std::os::windows::ffi::OsStrExt;
    let (sender, receiver) = std::sync::mpsc::channel();
    window.with_webview(move |webview| {
        let send_failure = sender.clone();
        let result = (|| -> windows::core::Result<()> { unsafe {
            let wide: Vec<u16> = path.as_os_str().encode_wide().chain(Some(0)).collect();
            let stream = SHCreateStreamOnFileEx(PCWSTR(wide.as_ptr()), (STGM_CREATE | STGM_READWRITE | STGM_SHARE_EXCLUSIVE).0, 0, true, None::<&IStream>)?;
            let keep = stream.clone();
            let callback = CapturePreviewCompletedHandler::create(Box::new(move |status| {
                let result = status.and_then(|_| keep.Commit(STGC_DEFAULT)).map_err(|e| e.to_string());
                let _ = sender.send(result);
                Ok(())
            }));
            webview.controller().CoreWebView2()?.CapturePreview(COREWEBVIEW2_CAPTURE_PREVIEW_IMAGE_FORMAT_PNG, &stream, &callback)?;
            Ok(())
        }})();
        if let Err(error) = result { let _ = send_failure.send(Err(error.to_string())); }
    }).map_err(|e| e.to_string())?;
    tauri::async_runtime::spawn_blocking(move || receiver.recv_timeout(Duration::from_secs(10)).map_err(|e| e.to_string())?)
        .await.map_err(|e| e.to_string())?
}
#[cfg(not(windows))]
async fn screenshot(_: tauri::WebviewWindow, _: PathBuf) -> Result<(), String> {
    Err("Native screenshot capture is currently implemented for WebView2 on Windows only".into())
}
#[tauri::command]
pub async fn save_diagnostics(window: tauri::WebviewWindow, state: Value, agent: tauri::State<'_, Agent>) -> Result<Value, String> {
    if state["settled"] != true { return Err("UI is busy; wait for settled=true".into()); }
    if serde_json::to_vec(&state).map_err(|e| e.to_string())?.len() > 8 * 1024 * 1024 { return Err("UI state exceeds 8 MiB".into()); }
    let base = match &agent.directory {
        Some(path) => path.join("captures"),
        None => window.app_handle().path().picture_dir().map_err(|e| e.to_string())?.join("ShowPsiSi"),
    };
    static SEQUENCE: AtomicU64 = AtomicU64::new(0);
    let id = format!("{}-{}-{}", SystemTime::now().duration_since(UNIX_EPOCH).map_err(|e| e.to_string())?.as_millis(), std::process::id(), SEQUENCE.fetch_add(1, Ordering::Relaxed));
    fs::create_dir_all(&base).map_err(|e| e.to_string())?;
    let directory = base.join(&id);
    fs::create_dir(&directory).map_err(|e| e.to_string())?;
    screenshot(window, directory.join("screenshot.png")).await?;
    let png = fs::read(directory.join("screenshot.png")).map_err(|e| e.to_string())?;
    if png.len() < 24 || &png[..8] != b"\x89PNG\r\n\x1a\n" { return Err("Capture did not produce a PNG".into()); }
    write_json(&directory.join("state.json"), &state)?;
    let manifest = json!({"schema_version":1,"frontend":"tauri","capture_id":id,"screenshot":"screenshot.png","state":"state.json",
        "width":u32::from_be_bytes(png[16..20].try_into().unwrap()),"height":u32::from_be_bytes(png[20..24].try_into().unwrap()),"screenshot_bytes":png.len(),"complete":true});
    write_json(&directory.join("manifest.json"), &manifest)?;
    Ok(json!({"directory":directory,"manifest":manifest}))
}
