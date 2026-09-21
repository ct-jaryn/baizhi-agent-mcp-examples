//! Checks the community guide through real ZeroClaw code and a loopback MCP fixture.
use std::sync::Arc;
use serde_json::json;
use wiremock::{Mock, MockServer, ResponseTemplate, matchers::{method, path, header, body_partial_json}};
use zeroclaw_api::tool::Tool;
use zeroclaw_config::{schema::Config, policy::SecurityPolicy};
use zeroclaw_tools::{mcp_client::McpRegistry, mcp_tool::McpToolWrapper};

const GUIDE: &str = include_str!("baizhi_mcp_guide.md");
const SYNTHETIC: &str = "Bearer fixture-only-not-a-real-key";

fn config(url: &str) -> Config {
    let snippet = GUIDE.split("```toml\n").nth(1).unwrap().split("```").next().unwrap();
    let mut config: Config = toml::from_str(snippet).expect("published TOML parses as real Config");
    assert_eq!(config.mcp.servers.len(), 1, "fixture rewrites exactly one server; refusing additional network targets");
    config.mcp.servers[0].url = Some(url.to_owned());
    config.mcp.servers[0].headers.insert("Authorization".into(), SYNTHETIC.into());
    config
}

async fn server() -> MockServer {
    let server = MockServer::start().await;
    // A real rejecting auth edge: all requests without the exact fixture token fail.
    Mock::given(method("POST")).and(path("/mcp"))
        .respond_with(ResponseTemplate::new(401)).with_priority(10).mount(&server).await;
    for (rpc, result) in [
        ("initialize", json!({"protocolVersion":"2024-11-05","capabilities":{"tools":{}},"serverInfo":{"name":"loopback-fixture","version":"1"}})),
        ("tools/list", json!({"tools":[{"name":"websearch_search","description":"Synthetic search","inputSchema":{"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}}]})),
        ("tools/call", json!({"content":[{"type":"text","text":"fixture source: https://example.org/evidence"}],"isError":false})),
    ] {
        Mock::given(method("POST")).and(path("/mcp")).and(header("Authorization", SYNTHETIC))
            .and(body_partial_json(json!({"method":rpc})))
            .respond_with(move |r: &wiremock::Request| {
                let request: serde_json::Value = serde_json::from_slice(&r.body).unwrap();
                ResponseTemplate::new(200).set_body_json(json!({"jsonrpc":"2.0","id":request["id"],"result":result}))
            }).with_priority(1).mount(&server).await;
    }
    Mock::given(method("POST")).and(path("/mcp")).and(header("Authorization", SYNTHETIC))
        .and(body_partial_json(json!({"method":"notifications/initialized"})))
        .respond_with(ResponseTemplate::new(202)).with_priority(1).mount(&server).await;
    server
}

#[test]
fn guide_parses_and_preserves_existing_grants_when_appended() {
    let mut c = config("http://127.0.0.1:1/mcp");
    assert_eq!(c.mcp.servers[0].name, "baizhi");
    assert_eq!(c.mcp_servers_for_agent("assistant").len(), 1);
    assert!(c.mcp_servers_for_agent("unknown").is_empty());
    let existing = zeroclaw_config::schema::McpServerConfig { name:"existing".into(), ..Default::default() };
    c.mcp.servers.push(existing);
    c.mcp_bundles.insert("existing".into(), zeroclaw_config::schema::McpBundleConfig { servers:vec!["existing".into()], exclude:vec![] });
    c.agents.get_mut("assistant").unwrap().mcp_bundles.insert(0,"existing".into());
    assert_eq!(c.mcp_servers_for_agent("assistant").iter().map(|s|s.name.as_str()).collect::<Vec<_>>(), vec!["existing","baizhi"]);
    c.mcp_bundles.get_mut("baizhi_web").unwrap().exclude.push("baizhi".into());
    assert_eq!(c.mcp_servers_for_agent("assistant").iter().map(|s|s.name.as_str()).collect::<Vec<_>>(), vec!["existing"]);
}

#[tokio::test]
async fn ungranted_or_misspelled_bundle_never_connects() {
    let s=server().await;
    for grants in [vec![],vec!["typo".to_string()]] {
        let mut c=config(&format!("{}/mcp",s.uri()));
        c.agents.get_mut("assistant").unwrap().mcp_bundles=grants;
        let registry=McpRegistry::connect_all(&c.mcp_servers_for_agent("assistant")).await.unwrap();
        assert!(registry.is_empty());
    }
    assert!(s.received_requests().await.unwrap().is_empty());
}

#[tokio::test]
async fn real_registry_discovers_and_wrapper_dispatches_authenticated_http() {
    let s=server().await;
    let c=config(&format!("{}/mcp",s.uri()));
    let registry=Arc::new(McpRegistry::connect_all(&c.mcp_servers_for_agent("assistant")).await.unwrap());
    assert_eq!(registry.server_count(),1);
    assert_eq!(registry.tool_names(),vec!["baizhi__websearch_search"]);
    let def=registry.get_tool_def("baizhi__websearch_search").await.unwrap();
    let tool=McpToolWrapper::new("baizhi__websearch_search".into(),def,registry,Arc::new(SecurityPolicy::default()));
    assert_eq!(tool.parameters_schema()["required"],json!(["query"]));
    let result=tool.execute(json!({"query":"synthetic public documentation", "approved":true})).await.unwrap();
    assert!(result.success);
    let output=serde_json::to_string(&result).unwrap();
    assert!(output.contains("example.org/evidence"));
    assert!(!output.contains(SYNTHETIC));
    let requests=s.received_requests().await.unwrap();
    let call=requests.iter().map(|r|serde_json::from_slice::<serde_json::Value>(&r.body).unwrap()).find(|r|r["method"]=="tools/call").unwrap();
    assert_eq!(call["params"],json!({"name":"websearch_search","arguments":{"query":"synthetic public documentation"}}));
    assert!(requests.iter().all(|r|r.url.path()=="/mcp" && r.url.query().is_none()));
}

#[tokio::test]
async fn missing_or_wrong_bearer_never_registers_tools() {
    let s=server().await;
    for auth in [None,Some("Bearer wrong-fixture")] {
        let mut c=config(&format!("{}/mcp",s.uri()));
        c.mcp.servers[0].headers.clear();
        if let Some(token)=auth { c.mcp.servers[0].headers.insert("Authorization".into(),token.into()); }
        let registry=McpRegistry::connect_all(&c.mcp_servers_for_agent("assistant")).await.unwrap();
        assert!(registry.is_empty());
        assert!(registry.call_tool("baizhi__websearch_search",json!({"query":"never sent"})).await.is_err());
    }
    let requests=s.received_requests().await.unwrap();
    assert!(!requests.is_empty());
    assert!(requests.iter().all(|r|serde_json::from_slice::<serde_json::Value>(&r.body).unwrap()["method"]=="initialize"));
}

#[tokio::test]
async fn removing_grant_applies_to_new_registry_not_already_connected_registry() {
    let s=server().await;
    let mut c=config(&format!("{}/mcp",s.uri()));
    let old=McpRegistry::connect_all(&c.mcp_servers_for_agent("assistant")).await.unwrap();
    assert_eq!(old.tool_count(),1);
    c.agents.get_mut("assistant").unwrap().mcp_bundles.clear();
    let fresh=McpRegistry::connect_all(&c.mcp_servers_for_agent("assistant")).await.unwrap();
    assert!(fresh.is_empty());
    // Configuration editing does not mutate a live registry: restart is necessary.
    assert_eq!(old.tool_count(),1);
    assert!(old.call_tool("baizhi__websearch_search",json!({"query":"fixture"})).await.is_ok());
}

#[tokio::test]
async fn documented_secret_field_is_masked_and_saved_encrypted() {
    let tmp=tempfile::tempdir().unwrap();
    let mut c=config("http://127.0.0.1:1/mcp");
    c.config_path=tmp.path().join("config.toml");
    let key_path="mcp.servers.baizhi.headers.Authorization";
    assert!(Config::prop_is_secret(key_path));
    c.set_prop_persistent(key_path,SYNTHETIC).unwrap();
    let field=c.prop_fields().into_iter().find(|p|p.name==key_path).unwrap();
    assert!(field.is_secret);
    assert!(!field.display_value.contains(SYNTHETIC));
    c.save().await.unwrap();
    let disk=std::fs::read_to_string(&c.config_path).unwrap();
    assert!(!disk.contains(SYNTHETIC));
    let stored: Config=toml::from_str(&disk).unwrap();
    let encrypted=&stored.mcp.servers[0].headers["Authorization"];
    assert!(zeroclaw_config::secrets::SecretStore::is_encrypted(encrypted));
    let store=zeroclaw_config::secrets::SecretStore::new(tmp.path(),true);
    assert_eq!(store.decrypt(encrypted).unwrap(),SYNTHETIC);
}
