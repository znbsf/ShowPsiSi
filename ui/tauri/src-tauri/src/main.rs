#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]
use std::{io::{BufRead,BufReader,Read,Write},process::{Child,ChildStdin,Command,Stdio},sync::{Arc,Mutex},time::{Duration,Instant}};
use tauri::{Emitter,Manager};
use serde_json::{json,Value};
mod agent;
use agent::{agent_next, agent_reply, save_diagnostics};
struct Core { child:Mutex<Child>, input:Mutex<ChildStdin>, started:Instant, root:String, trace:Option<String> }
fn mark(core:&Core,event:&str) { if let Some(path)=&core.trace { if let Ok(mut f)=std::fs::OpenOptions::new().create(true).append(true).open(path) {let _=writeln!(f,"{}",json!({"event":event,"ms":core.started.elapsed().as_secs_f64()*1000.0,"wall_ms":std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap().as_secs_f64()*1000.0}));} } }
#[tauri::command]
fn request(message:Value,core:tauri::State<Core>)->Result<(),String>{
    if core.child.lock().map_err(|e| e.to_string())?.try_wait().map_err(|e| e.to_string())?.is_some() {
        return Err("Native backend stopped. Restart the application.".into());
    }
    if message["method"]=="analyze" { mark(&core,"analyze_requested"); }
    let mut input=core.input.lock().map_err(|e|e.to_string())?;
    writeln!(input,"{}",message).and_then(|_|input.flush()).map_err(|e|e.to_string())
}
#[tauri::command]
fn environment(core:tauri::State<Core>,agent:tauri::State<agent::Agent>)->Value{json!({"agent_enabled":agent.enabled(),"backend_alive":core.child.lock().ok().and_then(|mut child| child.try_wait().ok()).map(|status| status.is_none()).unwrap_or(false),"root":core.root,"sample":std::env::var("SHOWPSISI_SAMPLE").unwrap_or_else(|_|format!("{}/samples/generated/lab.ts",core.root)),"auto":std::env::var("SHOWPSISI_AUTO").unwrap_or_default(),"delay":std::env::var("SHOWPSISI_AUTO_DELAY_MS").unwrap_or_default(),"driver":if cfg!(target_os = "windows") { "Tauri / WebView2" } else if cfg!(target_os = "macos") { "Tauri / WKWebView" } else { "Tauri / WebKitGTK" },"script":std::env::var("SHOWPSISI_SCRIPT").unwrap_or_default()})}
#[tauri::command]
fn milestone(event:String,core:tauri::State<Core>){mark(&core,&event);}
// Only explicit user clicks on URLs in the bundled standards registry may launch a browser.
fn contains_reference(value: &Value, url: &str) -> bool {
    match value {
        Value::Object(map) => map.iter().any(|(key, value)|
            (key == "url" && value.as_str() == Some(url)) || contains_reference(value, url)),
        Value::Array(items) => items.iter().any(|item| contains_reference(item, url)),
        _ => false,
    }
}
fn is_https_reference(url: &str) -> bool {
    url.starts_with("https://") && !url.chars().any(|c| c.is_control())
}
// A successful spawn only means the OS helper started. Report its failure instead
// of silently swallowing it. Some helpers stay alive with a browser; bound the
// confirmation wait without killing that browser, and reap it in the background.
fn run_reference_launcher(mut command: Command, timeout: Duration) -> Result<(), String> {
    let mut child = command.stdin(Stdio::null()).stdout(Stdio::null()).stderr(Stdio::piped())
        .spawn().map_err(|e| format!("Could not start the desktop browser launcher: {e}"))?;
    // Drain stderr continuously so a noisy helper cannot block on a full pipe.
    // Retain at most 512 bytes, and never wait indefinitely for inherited pipes.
    let diagnostics = Arc::new(Mutex::new(Vec::<u8>::new()));
    let captured = Arc::clone(&diagnostics);
    let mut stderr = child.stderr.take().expect("piped launcher stderr");
    let reader = std::thread::spawn(move || {
        let mut buffer = [0u8; 4096];
        while let Ok(count) = stderr.read(&mut buffer) {
            if count == 0 { break; }
            if let Ok(mut bytes) = captured.lock() {
                let keep = count.min(512usize.saturating_sub(bytes.len()));
                bytes.extend_from_slice(&buffer[..keep]);
            }
        }
    });
    let started = Instant::now();
    loop {
        match child.try_wait() {
            Ok(Some(status)) => {
                if status.success() { return Ok(()); }
                let read_deadline = Instant::now() + Duration::from_millis(100);
                while !reader.is_finished() && Instant::now() < read_deadline {
                    std::thread::sleep(Duration::from_millis(5));
                }
                let detail = diagnostics.lock().map(|bytes| String::from_utf8_lossy(&bytes)
                    .chars().map(|c| if c.is_control() { ' ' } else { c }).collect::<String>()
                    .split_whitespace().collect::<Vec<_>>().join(" ")).unwrap_or_default();
                return Err(format!("The desktop browser launcher failed ({status}){}{}",
                    if detail.is_empty() { "" } else { ": " }, detail));
            },
            Ok(None) if started.elapsed() < timeout => std::thread::sleep(Duration::from_millis(25)),
            Ok(None) => {
                std::thread::spawn(move || { let _ = child.wait(); });
                return Err("The desktop browser launcher is still running; opening could not be confirmed".into());
            },
            Err(error) => {
                std::thread::spawn(move || { let _ = child.wait(); });
                return Err(format!("Could not check the desktop browser launcher: {error}"));
            },
        }
    }
}
#[tauri::command]
async fn open_reference(url: String, core: tauri::State<'_, Core>) -> Result<(), String> {
    if !is_https_reference(&url) {
        return Err("Only HTTPS standards references are allowed".into());
    }
    let path = std::path::Path::new(&core.root).join("references/standards.json");
    let bytes = std::fs::read(path).map_err(|e| e.to_string())?;
    let registry: Value = serde_json::from_slice(&bytes).map_err(|e| e.to_string())?;
    if !contains_reference(&registry, &url) {
        return Err("URL is not in the bundled standards reference index".into());
    }
    #[cfg(target_os = "windows")]
    let mut command = { let mut c = Command::new("rundll32.exe"); c.arg("url.dll,FileProtocolHandler"); c };
    #[cfg(target_os = "macos")]
    let mut command = Command::new("open");
    #[cfg(all(unix, not(target_os = "macos")))]
    let mut command = Command::new("xdg-open");
    command.arg(&url);
    tauri::async_runtime::spawn_blocking(move || run_reference_launcher(command, Duration::from_secs(5)))
        .await.map_err(|error| format!("Browser launcher task failed: {error}"))?

}
fn main(){
    let started=Instant::now();
    tauri::Builder::default().plugin(tauri_plugin_dialog::init()).setup(move |app| {
        let root=std::env::var("SHOWPSISI_ROOT").unwrap_or_else(|_|std::env::current_dir().unwrap().to_string_lossy().into_owned());
        let exe=std::env::var("SHOWPSISI_CORE").unwrap_or_else(|_|format!("{}/build/bin/{}",root, if cfg!(windows) { "showpsisi-core.exe" } else { "showpsisi-core" }));
        let mut command=Command::new(exe);command.args(["--root",&root]).stdin(Stdio::piped()).stdout(Stdio::piped()).stderr(Stdio::null());
        #[cfg(windows)] {use std::os::windows::process::CommandExt;command.creation_flags(0x08000000);}
        app.manage(agent::Agent::new().map_err(std::io::Error::other)?);
        let mut child=command.spawn()?;let input=child.stdin.take().unwrap();let output=child.stdout.take().unwrap();
        app.manage(Core{child:Mutex::new(child),input:Mutex::new(input),started,root,trace:std::env::var("SHOWPSISI_TRACE").ok()});
        let handle=app.handle().clone();std::thread::spawn(move||{for line in BufReader::new(output).lines(){match line{Ok(line)=>{if let Ok(value)=serde_json::from_str::<Value>(&line){let _=handle.emit("core-message",value);}},Err(_)=>break}}let _=handle.emit("core-message",json!({"event":"backend_exit","error":"Native backend stopped. Restart the application."}));});
        mark(&app.state::<Core>(),"native_setup");Ok(())
    }).invoke_handler(tauri::generate_handler![request,environment,milestone,open_reference,agent_next,agent_reply,save_diagnostics]).build(tauri::generate_context!()).expect("Tauri startup").run(|app,event|{
        if let tauri::RunEvent::Exit = event {let core=app.state::<Core>();if let Ok(mut child)=core.child.lock(){let _=child.kill();let _=child.wait();};}
    });
}

#[cfg(test)]
mod tests {
    use super::{contains_reference, is_https_reference, run_reference_launcher};
    use std::{process::Command, time::{Duration, Instant}};
    use serde_json::json;

    fn exit_command(code: u8) -> Command {
        #[cfg(windows)]
        { let mut command = Command::new("cmd"); command.args(["/C", &format!("exit {code}")]); command }
        #[cfg(not(windows))]
        { let mut command = Command::new("sh"); command.args(["-c", &format!("exit {code}")]); command }
    }

    #[test]
    fn launcher_accepts_successful_helper_exit() {
        assert!(run_reference_launcher(exit_command(0), Duration::from_secs(2)).is_ok());
    }

    #[test]
    fn launcher_reports_nonzero_helper_exit() {
        let error = run_reference_launcher(exit_command(7), Duration::from_secs(2)).unwrap_err();
        assert!(error.contains("launcher failed"), "{error}");
        assert!(error.contains('7'), "{error}");
    }

    #[test]
    fn launcher_bounds_and_drains_failure_diagnostics() {
        let text = "x".repeat(6000);
        #[cfg(windows)]
        let command = { let mut c = Command::new("cmd"); c.args(["/C", &format!("echo {text} 1>&2 & exit 7")]); c };
        #[cfg(not(windows))]
        let command = { let mut c = Command::new("sh"); c.args(["-c", &format!("printf '{text}' >&2; exit 7")]); c };
        let error = run_reference_launcher(command, Duration::from_secs(2)).unwrap_err();
        assert!(error.contains("xxxxxxxx"), "{error}");
        assert!(error.len() < 650, "{} bytes", error.len());
    }

    #[test]
    fn launcher_reports_missing_helper() {
        let error = run_reference_launcher(Command::new("showpsisi-nonexistent-launcher-test"), Duration::from_secs(2)).unwrap_err();
        assert!(error.contains("Could not start"), "{error}");
    }

    #[cfg(unix)]
    #[test]
    fn launcher_timeout_is_bounded_and_not_success() {
        let mut command = Command::new("sh"); command.args(["-c", "sleep 0.2"]);
        let started = Instant::now();
        let error = run_reference_launcher(command, Duration::from_millis(25)).unwrap_err();
        assert!(error.contains("opening could not be confirmed"), "{error}");
        assert!(started.elapsed() < Duration::from_secs(1));
    }

    #[test]
    fn reference_lookup_requires_exact_url_field() {
        let registry = json!({"items": [{"url": "https://standards.example/spec"}],
            "description": "https://unlisted.example/"});
        assert!(contains_reference(&registry, "https://standards.example/spec"));
        for url in ["https://standards.example/spec?extra=1", "https://standards.example/",
            "https://unlisted.example/", "https://standards.example/spec/../other"] {
            assert!(!contains_reference(&registry, url), "{url}");
        }
    }

    #[test]
    fn reference_scheme_rejects_commands_and_control_characters() {
        assert!(is_https_reference("https://standards.example/spec"));
        for url in ["http://standards.example/", "file:///tmp/spec", "javascript:alert(1)",
            "--help", "https://standards.example/\n", "https://standards.example/\0"] {
            assert!(!is_https_reference(url), "{url:?}");
        }
    }
}
