#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]
use std::{io::{BufRead,BufReader,Write},process::{Child,ChildStdin,Command,Stdio},sync::Mutex,time::Instant};
use tauri::{Emitter,Manager};
use serde_json::{json,Value};
struct Core { child:Mutex<Child>, input:Mutex<ChildStdin>, started:Instant, root:String, trace:Option<String> }
fn mark(core:&Core,event:&str) { if let Some(path)=&core.trace { if let Ok(mut f)=std::fs::OpenOptions::new().create(true).append(true).open(path) {let _=writeln!(f,"{}",json!({"event":event,"ms":core.started.elapsed().as_secs_f64()*1000.0,"wall_ms":std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap().as_secs_f64()*1000.0}));} } }
#[tauri::command]
fn request(message:Value,core:tauri::State<Core>)->Result<(),String>{
    if message["method"]=="analyze" { mark(&core,"analyze_requested"); }
    let mut input=core.input.lock().map_err(|e|e.to_string())?;
    writeln!(input,"{}",message).and_then(|_|input.flush()).map_err(|e|e.to_string())
}
#[tauri::command]
fn environment(core:tauri::State<Core>)->Value{json!({"root":core.root,"sample":std::env::var("SHOWPSISI_SAMPLE").unwrap_or_else(|_|format!("{}/samples/generated/lab.ts",core.root)),"auto":std::env::var("SHOWPSISI_AUTO").unwrap_or_default(),"delay":std::env::var("SHOWPSISI_AUTO_DELAY_MS").unwrap_or_default(),"driver":"Tauri / WebView2","script":std::env::var("SHOWPSISI_SCRIPT").unwrap_or_default()})}
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
#[tauri::command]
fn open_reference(url: String, core: tauri::State<Core>) -> Result<(), String> {
    if !url.starts_with("https://") || url.chars().any(|c| c.is_control()) {
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
    let child = command.arg(&url).stdin(Stdio::null()).stdout(Stdio::null()).stderr(Stdio::null())
        .spawn().map_err(|e| e.to_string())?;
    std::thread::spawn(move || { let mut child = child; let _ = child.wait(); });
    Ok(())
}
fn main(){
    let started=Instant::now();
    tauri::Builder::default().plugin(tauri_plugin_dialog::init()).setup(move |app| {
        let root=std::env::var("SHOWPSISI_ROOT").unwrap_or_else(|_|std::env::current_dir().unwrap().to_string_lossy().into_owned());
        let exe=std::env::var("SHOWPSISI_CORE").unwrap_or_else(|_|format!("{}/build/bin/{}",root, if cfg!(windows) { "showpsisi-core.exe" } else { "showpsisi-core" }));
        let mut command=Command::new(exe);command.args(["--root",&root]).stdin(Stdio::piped()).stdout(Stdio::piped()).stderr(Stdio::null());
        #[cfg(windows)] {use std::os::windows::process::CommandExt;command.creation_flags(0x08000000);}
        let mut child=command.spawn()?;let input=child.stdin.take().unwrap();let output=child.stdout.take().unwrap();
        app.manage(Core{child:Mutex::new(child),input:Mutex::new(input),started,root,trace:std::env::var("SHOWPSISI_TRACE").ok()});
        let handle=app.handle().clone();std::thread::spawn(move||{for line in BufReader::new(output).lines(){match line{Ok(line)=>{if let Ok(value)=serde_json::from_str::<Value>(&line){let _=handle.emit("core-message",value);}},Err(_)=>break}}});
        mark(&app.state::<Core>(),"native_setup");Ok(())
    }).invoke_handler(tauri::generate_handler![request,environment,milestone,open_reference]).build(tauri::generate_context!()).expect("Tauri startup").run(|app,event|{
        if let tauri::RunEvent::Exit = event {let core=app.state::<Core>();if let Ok(mut child)=core.child.lock(){let _=child.kill();let _=child.wait();};}
    });
}
