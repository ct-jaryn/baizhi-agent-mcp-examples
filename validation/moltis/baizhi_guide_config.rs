use moltis_config::schema::{McpServerId, McpTransport, MoltisConfig};

#[test]
fn guide_toml_parses_with_native_config_types_and_stays_disabled() {
    let config: MoltisConfig =
        toml::from_str(include_str!("fixtures/baizhi-guide.toml")).expect("guide TOML must parse");
    let server = config
        .mcp
        .servers
        .get(&McpServerId::from("baizhi"))
        .expect("guide must define baizhi server");
    assert_eq!(server.transport_type(), McpTransport::StreamableHttp);
    assert_eq!(
        server.url.as_deref(),
        Some("https://agent-toolkit.app.baizhi.cloud/mcp")
    );
    assert_eq!(
        server.headers.get("Authorization").map(String::as_str),
        Some("Bearer ${BAIZHI_API_KEY}")
    );
    assert!(!server.enabled);
    assert_eq!(server.request_timeout_secs, Some(60));
    assert!(server.command.is_empty());
    assert!(server.env.is_empty());
    assert!(server.oauth.is_none());
}
