//! Synthetic HTTP fixture. No model, production endpoint, user config, or real credentials.
use anyhow::Result;
use moltis_agents::tool_registry::ToolRegistry;
use moltis_mcp::{McpManager, McpRegistry, parse_server_config};
use moltis_mcp_agent_bridge::sync_mcp_tools;
use serde_json::{Value, json};
use std::{collections::HashMap, sync::Arc, time::Duration};
use tokio::{
    io::{AsyncReadExt, AsyncWriteExt},
    net::{TcpListener, TcpStream},
    sync::{Mutex, RwLock},
    task::JoinHandle,
};

const SYNTHETIC_TOKEN: &str = "synthetic-moltis-fixture-not-a-real-key";
struct Fixture {
    url: String,
    events: Arc<Mutex<Vec<Value>>>,
    task: JoinHandle<()>,
}
impl Fixture {
    async fn start() -> Result<Self> {
        let listener = TcpListener::bind("127.0.0.1:0").await?;
        let url = format!("http://{}/mcp?purpose=fixture", listener.local_addr()?);
        let events = Arc::new(Mutex::new(Vec::new()));
        let shared = Arc::clone(&events);
        let task = tokio::spawn(async move {
            while let Ok((socket, _)) = listener.accept().await {
                let shared = Arc::clone(&shared);
                tokio::spawn(async move {
                    let _ = serve(socket, shared).await;
                });
            }
        });
        Ok(Self { url, events, task })
    }
    async fn events(&self) -> Vec<Value> {
        self.events.lock().await.clone()
    }
}
impl Drop for Fixture {
    fn drop(&mut self) {
        self.task.abort();
    }
}
async fn serve(mut socket: TcpStream, events: Arc<Mutex<Vec<Value>>>) -> Result<()> {
    let mut bytes = Vec::new();
    let header_end;
    loop {
        let mut chunk = [0; 4096];
        let size = socket.read(&mut chunk).await?;
        if size == 0 {
            return Ok(());
        }
        bytes.extend_from_slice(&chunk[..size]);
        if let Some(pos) = bytes.windows(4).position(|w| w == b"\r\n\r\n") {
            header_end = pos + 4;
            break;
        }
        anyhow::ensure!(bytes.len() < 65_536, "fixture header too large");
    }
    let header = String::from_utf8(bytes[..header_end].to_vec())?;
    let mut lines = header.lines();
    let first = lines.next().unwrap_or_default();
    let parts: Vec<_> = first.split_whitespace().collect();
    let verb = parts.first().copied().unwrap_or_default();
    let path = parts.get(1).copied().unwrap_or_default();
    let headers: HashMap<String, String> = lines
        .filter_map(|l| l.split_once(':'))
        .map(|(k, v)| (k.to_lowercase(), v.trim().to_owned()))
        .collect();
    let length: usize = headers
        .get("content-length")
        .and_then(|v| v.parse().ok())
        .unwrap_or(0);
    while bytes.len() < header_end + length {
        let mut chunk = [0; 4096];
        let n = socket.read(&mut chunk).await?;
        if n == 0 {
            break;
        }
        bytes.extend_from_slice(&chunk[..n]);
    }
    let request: Value = serde_json::from_slice(&bytes[header_end..]).unwrap_or(Value::Null);
    let authorized = headers
        .get("authorization")
        .is_some_and(|v| v == &format!("Bearer {SYNTHETIC_TOKEN}"));
    let trace_ok = headers
        .get("x-fixture-scope")
        .is_some_and(|v| v == "scope-fixed");
    let session_ok = headers
        .get("mcp-session-id")
        .is_some_and(|v| v == "fixture-session");
    events.lock().await.push(json!({"verb":verb,"path":path,"method":request["method"],"authorized":authorized,"trace_ok":trace_ok,"session_ok":session_ok,"params":request["params"]}));
    let method = request["method"].as_str().unwrap_or_default();
    let (status, body) = if !path.starts_with("/mcp?") {
        (404, String::new())
    } else if !authorized {
        (401, String::new())
    } else if verb == "DELETE" {
        (204, String::new())
    } else if verb == "GET" {
        (405, String::new())
    } else if method == "notifications/initialized" {
        (202, String::new())
    } else {
        let result = match method {
            "initialize" => {
                json!({"protocolVersion":"2024-11-05","capabilities":{"tools":{}},"serverInfo":{"name":"synthetic-baizhi-fixture","version":"1"}})
            }
            "tools/list" => json!({"tools":[
                {"name":"search","description":"Synthetic search only","inputSchema":{"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}},
                {"name":"read","description":"Synthetic read only","inputSchema":{"type":"object","properties":{"url":{"type":"string"}},"required":["url"]}}]}),
            "tools/call" => {
                let args = &request["params"]["arguments"];
                if args["query"] == "slow" {
                    tokio::time::sleep(Duration::from_secs(3)).await;
                }
                if args["query"] == "error" {
                    json!({"isError":true,"content":[{"type":"text","text":"synthetic tool failure"}]})
                } else {
                    json!({"content":[{"type":"text","text":json!({"synthetic":true,"tool":request["params"]["name"],"arguments":args}).to_string()}]})
                }
            }
            "ping" => json!({}),
            _ => json!({}),
        };
        (
            200,
            json!({"jsonrpc":"2.0","id":request["id"],"result":result}).to_string(),
        )
    };
    let session = if status == 200 && method == "initialize" {
        "Mcp-Session-Id: fixture-session\r\n"
    } else {
        ""
    };
    let response = format!(
        "HTTP/1.1 {status} Fixture\r\nContent-Type: application/json\r\nContent-Length: {}\r\n{session}Connection: close\r\n\r\n{body}",
        body.len()
    );
    socket.write_all(response.as_bytes()).await?;
    Ok(())
}
fn registry() -> McpRegistry {
    static COUNTER: std::sync::atomic::AtomicUsize = std::sync::atomic::AtomicUsize::new(0);
    let dir = std::env::var("MOLTIS_CONFIG_DIR").expect("isolated config dir required by fixture");
    let fixture_root = std::env::var("MOLTIS_FIXTURE_ROOT")
        .expect("runner must provide a fresh isolated fixture root");
    assert_eq!(
        std::path::Path::new(&dir)
            .canonicalize()
            .expect("fixture config dir"),
        std::path::Path::new(&fixture_root)
            .join("config")
            .canonicalize()
            .expect("fixture root config"),
        "fixture must use the runner's isolated config dir"
    );
    let index = COUNTER.fetch_add(1, std::sync::atomic::Ordering::Relaxed);
    let path = std::path::Path::new(&dir).join(format!(
        "fixture-registry-{}-{index}.json",
        std::process::id()
    ));
    McpRegistry::load(&path).expect("isolated registry initialization")
}
fn manager() -> McpManager {
    McpManager::new_with_env_overrides(
        registry(),
        HashMap::from([("BAIZHI_API_KEY".to_owned(), SYNTHETIC_TOKEN.to_owned())]),
        Duration::from_secs(1),
    )
}
fn config(url: &str, token: &str) -> Result<moltis_mcp::McpServerConfig> {
    Ok(parse_server_config(
        &json!({"transport":"streamable-http","url":url,"headers":{"Authorization":token,"x-fixture-scope":"scope-fixed"},"enabled":true}),
        None,
    )?)
}
async fn attach(manager: &McpManager, fixture: &Fixture) -> Result<Arc<RwLock<ToolRegistry>>> {
    manager
        .add_server(
            "baizhi".to_owned(),
            config(&fixture.url, "Bearer ${BAIZHI_API_KEY}")?,
            true,
        )
        .await?;
    let registry = Arc::new(RwLock::new(ToolRegistry::new()));
    sync_mcp_tools(manager, &registry).await;
    Ok(registry)
}
#[tokio::test]
async fn native_host_registration_call_and_authenticated_cleanup() -> Result<()> {
    let f = Fixture::start().await?;
    let m = manager();
    let reg = attach(&m, &f).await?;
    assert_eq!(reg.read().await.list_schemas().len(), 2);
    let search = reg
        .read()
        .await
        .get("mcp__baizhi__search")
        .ok_or_else(|| anyhow::anyhow!("missing search registration"))?;
    let out = search
        .execute(json!({"query":"百智 MCP","optional":null,"_session_key":"synthetic-session"}))
        .await?;
    assert_eq!(
        out,
        json!({"synthetic":true,"tool":"search","arguments":{"query":"百智 MCP"}})
    );
    let read = reg
        .read()
        .await
        .get("mcp__baizhi__read")
        .ok_or_else(|| anyhow::anyhow!("missing read registration"))?;
    assert_eq!(
        read.execute(json!({"url":"https://example.invalid/synthetic"}))
            .await?["tool"],
        "read"
    );
    let status = serde_json::to_string(&m.status("baizhi").await)?;
    assert!(!status.contains(SYNTHETIC_TOKEN));
    assert!(!status.contains("Bearer"));
    m.stop_server("baizhi").await;
    sync_mcp_tools(&m, &reg).await;
    assert!(reg.read().await.is_empty());
    assert!(search.execute(json!({"query":"after stop"})).await.is_err());
    let events = f.events().await;
    assert!(events.iter().any(|e| e["method"] == "initialize"));
    assert!(
        events
            .iter()
            .any(|e| e["method"] == "notifications/initialized")
    );
    assert!(
        events
            .iter()
            .any(|e| e["verb"] == "DELETE" && e["session_ok"] == true)
    );
    assert!(events.iter().all(|e| e["authorized"] == true
        && e["trace_ok"] == true
        && e["path"] == "/mcp?purpose=fixture"));
    println!(
        "validated initialize/list/2 calls/status redaction/stop/unregister/DELETE; all requests loopback with expected auth"
    );
    Ok(())
}
#[tokio::test]
async fn wrong_key_rejected_without_tool_registration() -> Result<()> {
    let f = Fixture::start().await?;
    let m = manager();
    assert!(
        m.add_server(
            "wrong".into(),
            config(&f.url, "Bearer synthetic-wrong")?,
            true
        )
        .await
        .is_err()
    );
    assert!(m.tool_bridges().await.is_empty());
    assert!(
        f.events()
            .await
            .iter()
            .any(|e| e["method"] == "initialize" && e["authorized"] == false)
    );
    m.stop_server("wrong").await;
    Ok(())
}
#[tokio::test]
async fn absent_managed_variable_is_rejected_by_server_not_silently_disabled() -> Result<()> {
    let f = Fixture::start().await?;
    let m = McpManager::new(registry());
    assert!(
        m.add_server(
            "missing".into(),
            config(&f.url, "Bearer ${BAIZHI_API_KEY}")?,
            true
        )
        .await
        .is_err()
    );
    assert!(m.tool_bridges().await.is_empty());
    assert!(
        f.events()
            .await
            .iter()
            .any(|e| e["method"] == "initialize" && e["authorized"] == false)
    );
    m.stop_server("missing").await;
    Ok(())
}
#[tokio::test]
async fn invalid_header_is_rejected_before_network() -> Result<()> {
    let f = Fixture::start().await?;
    let m = manager();
    let result = m
        .add_server(
            "invalid".into(),
            config(&f.url, "Bearer synthetic\ninvalid")?,
            true,
        )
        .await;
    assert!(
        result
            .unwrap_err()
            .to_string()
            .contains("invalid remote MCP header value")
    );
    assert!(f.events().await.is_empty());
    Ok(())
}
#[tokio::test]
async fn tool_error_propagates_through_native_agent_adapter() -> Result<()> {
    let f = Fixture::start().await?;
    let m = manager();
    let reg = attach(&m, &f).await?;
    let search = reg
        .read()
        .await
        .get("mcp__baizhi__search")
        .ok_or_else(|| anyhow::anyhow!("missing tool"))?;
    let error = search
        .execute(json!({"query":"error"}))
        .await
        .unwrap_err()
        .to_string();
    assert!(error.contains("synthetic tool failure"));
    assert!(!error.contains(SYNTHETIC_TOKEN));
    m.stop_server("baizhi").await;
    Ok(())
}
#[tokio::test]
async fn call_timeout_keeps_cleanup_available() -> Result<()> {
    let f = Fixture::start().await?;
    let m = manager();
    let reg = attach(&m, &f).await?;
    let search = reg
        .read()
        .await
        .get("mcp__baizhi__search")
        .ok_or_else(|| anyhow::anyhow!("missing tool"))?;
    let result = tokio::time::timeout(
        Duration::from_secs(2),
        search.execute(json!({"query":"slow"})),
    )
    .await;
    assert!(
        result.is_ok(),
        "client request timeout must finish before outer guard"
    );
    assert!(result?.is_err());
    m.stop_server("baizhi").await;
    assert!(f.events().await.iter().any(|e| e["verb"] == "DELETE"));
    Ok(())
}
