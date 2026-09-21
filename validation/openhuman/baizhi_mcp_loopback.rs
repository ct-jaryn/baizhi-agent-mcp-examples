// SPDX-License-Identifier: GPL-3.0-only
//! Local-only integration checks for an authenticated remote MCP declaration.
//! Real OpenHuman config/store/host/tool factory and TinyAgents tool-batch dispatch.
//! The HTTP peer and scheduled tool call are synthetic; no model or product UI runs.
use axum::{
    extract::State,
    http::{HeaderMap, StatusCode, Uri},
    response::{IntoResponse, Response},
    routing::post,
    Json, Router,
};
use openhuman_core::{
    config::Config,
    mcp::{
        host,
        registry::{config_ops, ops},
    },
    security::{AuditLogger, SecurityPolicy},
};
use serde_json::{json, Value};
use std::{
    collections::HashMap,
    sync::{Arc, Mutex},
    time::Duration,
};
use tinyagents_harness::{
    agent_loop::phases::execute_tool_batch,
    context::{RunConfig, RunContext},
    events::HarnessRunStatus,
    middleware::AgentRun,
    runtime::AgentHarness,
};
use tinyinference_llm::tool::ToolCall;
use tinytools::Tool;

const KEY: &str = "Bearer synthetic-openhuman-alpha";
const NEXT_KEY: &str = "Bearer synthetic-openhuman-beta";
#[derive(Default)]
struct PeerState {
    expected: String,
    methods: Vec<String>,
    calls: Vec<Value>,
    rejects: usize,
    deletes: usize,
    require_tenant: bool,
    saw_query: bool,
}
struct Peer {
    url: String,
    state: Arc<Mutex<PeerState>>,
    task: tokio::task::JoinHandle<()>,
}
impl Drop for Peer {
    fn drop(&mut self) {
        self.task.abort();
    }
}
async fn post_mcp(
    State(s): State<Arc<Mutex<PeerState>>>,
    uri: Uri,
    headers: HeaderMap,
    Json(body): Json<Value>,
) -> Response {
    let mut s = s.lock().unwrap();
    s.saw_query |= uri.query().is_some();
    let authorized = headers.get("authorization").and_then(|v| v.to_str().ok())
        == Some(s.expected.as_str())
        && (!s.require_tenant
            || headers.get("x-tenant").and_then(|v| v.to_str().ok()) == Some("synthetic-tenant"));
    if !authorized {
        s.rejects += 1;
        return (StatusCode::UNAUTHORIZED, "synthetic authorization rejected").into_response();
    }
    let method = body["method"].as_str().unwrap_or("").to_string();
    s.methods.push(method.clone());
    let result = match method.as_str() {
        "initialize" => {
            json!({"protocolVersion":"2024-11-05","capabilities":{"tools":{}},"serverInfo":{"name":"synthetic-guide-peer","version":"1"}})
        }
        "notifications/initialized" => return StatusCode::ACCEPTED.into_response(),
        "tools/list" => {
            json!({"tools":[{"name":"synthetic_echo","description":"Returns a synthetic fixture result.","inputSchema":{"type":"object","properties":{"message":{"type":"string"}},"required":["message"]}}]})
        }
        "tools/call" => {
            s.calls.push(body["params"].clone());
            json!({"content":[{"type":"text","text":body["params"]["arguments"]["message"]}],"structuredContent":{"fixture":true,"arguments":body["params"]["arguments"]},"isError":false})
        }
        "ping" => json!({}),
        _ => return (StatusCode::BAD_REQUEST, "unexpected fixture method").into_response(),
    };
    let mut response =
        Json(json!({"jsonrpc":"2.0","id":body["id"],"result":result})).into_response();
    response
        .headers_mut()
        .insert("mcp-session-id", "synthetic-session".parse().unwrap());
    response
}
async fn delete_mcp(State(s): State<Arc<Mutex<PeerState>>>) -> StatusCode {
    s.lock().unwrap().deletes += 1;
    StatusCode::NO_CONTENT
}
async fn peer() -> Peer {
    let state = Arc::new(Mutex::new(PeerState {
        expected: KEY.into(),
        ..Default::default()
    }));
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let url = format!("http://{}/mcp", listener.local_addr().unwrap());
    let app = Router::new()
        .route("/mcp", post(post_mcp).delete(delete_mcp))
        .with_state(state.clone());
    let task = tokio::spawn(async move { axum::serve(listener, app).await.unwrap() });
    Peer { url, state, task }
}
fn config() -> (tempfile::TempDir, Config) {
    let dir = tempfile::tempdir().unwrap();
    let mut c = Config::default();
    c.workspace_dir = dir.path().join("state");
    c.config_path = dir.path().join("config.toml");
    c.action_dir = dir.path().join("actions");
    std::fs::create_dir_all(&c.workspace_dir).unwrap();
    std::fs::create_dir_all(&c.action_dir).unwrap();
    c.api_url = Some("http://127.0.0.1:9".into());
    c.secrets.encrypt = false;
    (dir, c)
}
fn declaration(url: &str, key: Option<&str>) -> Value {
    let mut entry = json!({"url":url,"enabled":false});
    if let Some(key) = key {
        entry["headers"] = json!({"Authorization":key});
    }
    entry
}
async fn put(c: &Config, doc: Value) -> Value {
    config_ops::mcp_clients_config_set(c, doc)
        .await
        .expect("native config_set")
        .value
}
async fn get(c: &Config) -> Value {
    config_ops::mcp_clients_config_get(c)
        .await
        .expect("native config_get")
        .value
}
fn id(c: &Config, name: &str) -> String {
    host::for_config(c)
        .unwrap()
        .dynamic()
        .installed_list()
        .unwrap()
        .into_iter()
        .find(|s| s.qualified_name == name)
        .unwrap()
        .server_id
}
async fn connect(c: &Config, sid: &str) -> Result<Value, String> {
    ops::mcp_clients_set_enabled(c, sid.into(), true).await?;
    tokio::time::timeout(
        Duration::from_secs(8),
        ops::mcp_clients_connect(c, sid.into()),
    )
    .await
    .map_err(|_| "local connect timed out".to_string())?
    .map(|x| x.value)
}
async fn dispatch(c: &Config, sid: &str, message: &str) -> Value {
    // Actual product tool factory binds each tool to this workspace's Config.
    let security = Arc::new(SecurityPolicy::from_config(
        &c.autonomy,
        &c.workspace_dir,
        &c.action_dir,
    ));
    let tools = openhuman_core::tools::ops::all_tools(
        Arc::new(c.clone()),
        &security,
        AuditLogger::disabled(),
        &c.browser,
        &c.http_request,
        &c.action_dir,
        &HashMap::new(),
        c,
    );
    let tool = tools
        .into_iter()
        .find(|t| t.name() == "mcp_registry_tool_call")
        .expect("native factory registered MCP bridge");
    let mut harness = AgentHarness::<(), ()>::new();
    harness.register_tool(Arc::<dyn Tool>::from(tool));
    let mut context = RunContext::new(RunConfig::new("baizhi-synthetic-validation"), ());
    let mut status = HarnessRunStatus::new(
        context.config.run_id.clone(),
        "baizhi-loopback-validation".into(),
    );
    let mut run = AgentRun::new();
    let mut messages = Vec::new();
    let result = execute_tool_batch(
        &harness,
        &(),
        &mut context,
        &mut run,
        &mut status,
        &mut messages,
        vec![ToolCall::new(
            "fixture-call",
            "mcp_registry_tool_call",
            json!({"server_id":sid,"tool_name":"synthetic_echo","arguments":{"message":message}}),
        )],
    )
    .await
    .expect("native harness tool-batch scheduling");
    assert_eq!(result.executed_tools, ["mcp_registry_tool_call"]);
    assert_eq!(run.model_calls, 0);
    serde_json::to_value(result.results).unwrap()
}
async fn cleanup(c: &Config) {
    put(c, json!({"mcpServers":{}})).await;
    assert!(host::for_config(c)
        .unwrap()
        .dynamic()
        .installed_list()
        .unwrap()
        .is_empty());
}

#[tokio::test]
async fn baizhi_authenticated_native_dispatch_roundtrip_and_cleanup() {
    let p = peer().await;
    let (_dir, c) = config();
    let reply = put(
        &c,
        json!({"mcpServers":{"baizhi":declaration(&p.url,Some(KEY))}}),
    )
    .await;
    assert!(!reply.to_string().contains(KEY));
    let sid = id(&c, "baizhi");
    assert!(host::for_config(&c)
        .unwrap()
        .dynamic()
        .store()
        .load_env_values(&sid)
        .unwrap()
        .get("Authorization")
        .is_some_and(|v| v == KEY));
    let read = get(&c).await;
    assert_eq!(read["mcpServers"]["baizhi"]["authConfigured"], true);
    assert!(read["mcpServers"]["baizhi"].get("headers").is_none());
    assert!(!read.to_string().contains(KEY));
    let connected = connect(&c, &sid).await.unwrap();
    assert_eq!(connected["tools"][0]["name"], "synthetic_echo");
    let output = dispatch(&c, &sid, "synthetic 你好 — nested result").await;
    assert!(output.to_string().contains("synthetic 你好"));
    let calls = p.state.lock().unwrap().calls.clone();
    assert_eq!(calls.len(), 1);
    assert_eq!(
        calls[0]["arguments"],
        json!({"message":"synthetic 你好 — nested result"})
    );
    cleanup(&c).await;
    let st = p.state.lock().unwrap();
    assert!(st.methods.iter().any(|x| x == "initialize"));
    assert!(st.methods.iter().any(|x| x == "tools/list"));
    assert!(st.deletes >= 1);
    assert!(!st.saw_query);
}
async fn rejected(key: Option<&str>) {
    let p = peer().await;
    let (_dir, c) = config();
    put(&c, json!({"mcpServers":{"baizhi":declaration(&p.url,key)}})).await;
    let sid = id(&c, "baizhi");
    let err = connect(&c, &sid)
        .await
        .expect_err("unauthorized peer must reject connection");
    if let Some(k) = key {
        assert!(!err.contains(k));
    }
    assert!(p.state.lock().unwrap().rejects > 0);
    assert!(p.state.lock().unwrap().calls.is_empty());
    cleanup(&c).await;
}
#[tokio::test]
async fn baizhi_missing_key_is_rejected() {
    rejected(None).await;
}
#[tokio::test]
async fn baizhi_wrong_key_is_rejected() {
    rejected(Some("Bearer synthetic-wrong")).await;
}
#[tokio::test]
async fn baizhi_literal_environment_placeholder_is_not_a_key() {
    rejected(Some("Bearer ${BAIZHI_API_KEY}")).await;
}

#[tokio::test]
async fn baizhi_rotation_readback_omission_and_empty_value_removal() {
    let p = peer().await;
    let other = peer().await;
    let (_dir, c) = config();
    put(&c,json!({"mcpServers":{"baizhi":declaration(&p.url,Some(KEY)),"other":declaration(&other.url,Some(KEY))}})).await;
    let sid = id(&c, "baizhi");
    let other_id = id(&c, "other");
    connect(&c, &sid).await.unwrap();
    connect(&c, &other_id).await.unwrap();
    // Saving the secret-free readback preserves credentials and server identities.
    let mut read = get(&c).await;
    put(&c, read.clone()).await;
    assert_eq!(id(&c, "baizhi"), sid);
    assert_eq!(id(&c, "other"), other_id);
    assert!(dispatch(&c, &sid, "readback preserved")
        .await
        .to_string()
        .contains("readback preserved"));
    // An explicitly empty Header object is also a no-op, not a request to clear secrets.
    read["mcpServers"]["baizhi"]["headers"] = json!({});
    put(&c, read.clone()).await;
    assert!(host::for_config(&c)
        .unwrap()
        .dynamic()
        .store()
        .load_env_values(&sid)
        .unwrap()
        .get("Authorization")
        .is_some_and(|value| value == KEY));
    assert!(dispatch(&c, &sid, "empty header block preserved")
        .await
        .to_string()
        .contains("empty header block preserved"));
    // Rotation disconnects the old session and reconnects using the new stored Header.
    p.state.lock().unwrap().expected = NEXT_KEY.into();
    read["mcpServers"]["baizhi"]["headers"] = json!({"Authorization":NEXT_KEY});
    read["mcpServers"]["baizhi"]["enabled"] = json!(false);
    put(&c, read).await;
    connect(&c, &sid).await.unwrap();
    assert!(dispatch(&c, &sid, "rotated")
        .await
        .to_string()
        .contains("rotated"));
    assert!(dispatch(&c, &other_id, "other retained")
        .await
        .to_string()
        .contains("other retained"));
    let mut read = get(&c).await;
    read["mcpServers"]["baizhi"]["enabled"] = json!(false);
    read["mcpServers"]["baizhi"]["headers"] = json!({"Authorization":""});
    put(&c, read).await;
    assert!(host::for_config(&c)
        .unwrap()
        .dynamic()
        .store()
        .load_env_values(&sid)
        .unwrap()
        .get("Authorization")
        .is_none());
    assert_eq!(
        get(&c).await["mcpServers"]["baizhi"]["authConfigured"],
        false
    );
    connect(&c, &sid)
        .await
        .expect_err("deleted credential rejected");
    let mut read = get(&c).await;
    read["mcpServers"].as_object_mut().unwrap().remove("baizhi");
    put(&c, read).await;
    assert_eq!(id(&c, "other"), other_id);
    assert!(dispatch(&c, &other_id, "after removal")
        .await
        .to_string()
        .contains("after removal"));
    cleanup(&c).await;
}

#[tokio::test]
async fn baizhi_partial_header_update_retains_other_header() {
    let p = peer().await;
    p.state.lock().unwrap().require_tenant = true;
    let (_dir, c) = config();
    let mut entry = declaration(&p.url, Some(KEY));
    entry["headers"]["X-Tenant"] = json!("synthetic-tenant");
    put(&c, json!({"mcpServers":{"baizhi":entry}})).await;
    let sid = id(&c, "baizhi");
    connect(&c, &sid).await.unwrap();
    let mut read = get(&c).await;
    read["mcpServers"]["baizhi"]["enabled"] = json!(false);
    read["mcpServers"]["baizhi"]["headers"] = json!({"Authorization":NEXT_KEY});
    p.state.lock().unwrap().expected = NEXT_KEY.into();
    put(&c, read).await;
    connect(&c, &sid).await.unwrap();
    assert!(dispatch(&c, &sid, "two independent headers")
        .await
        .to_string()
        .contains("two independent headers"));
    assert!(host::for_config(&c)
        .unwrap()
        .dynamic()
        .store()
        .load_env_values(&sid)
        .unwrap()
        .get("X-Tenant")
        .is_some_and(|v| v == "synthetic-tenant"));
    cleanup(&c).await;
}
