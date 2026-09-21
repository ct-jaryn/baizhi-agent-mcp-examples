# Use BaizhiCloud Agent Toolkit with Moltis

This optional community guide connects [Moltis](https://github.com/moltis-org/moltis) to the hosted [BaizhiCloud Agent Toolkit](https://baizhi.cloud/landing/agent-toolkit) through Moltis's existing Streamable HTTP MCP client. No extra plugin or MCP-to-stdio bridge is needed.

This guide is part of integration and promotion work for BaizhiCloud Agent Toolkit. It is an independent community example, not an official Moltis integration or a replacement for either project's maintenance channel. Moltis is MIT-licensed; that does not make the hosted BaizhiCloud backend open source.

## Before connecting

Use your own BaizhiCloud Agent Toolkit account and API key from the service's account console, reached through the [official product page](https://baizhi.cloud/landing/agent-toolkit). Check your account's access and current pricing before calling tools. Tool arguments, such as queries and URLs, are sent to BaizhiCloud and may incur charges. Do not put a key in a URL, Git, screenshots, or shared logs.

The configuration and native runtime checks below are tied to Moltis source commit [`9d3238c322708e9d57fe235ce1c2b43ccc33af62`](https://github.com/moltis-org/moltis/tree/9d3238c322708e9d57fe235ce1c2b43ccc33af62), inspected on 2026-09-21. They are not a claim that every published Moltis release supports the same behavior. Check the [upstream MCP guide](https://github.com/moltis-org/moltis/blob/9d3238c322708e9d57fe235ce1c2b43ccc33af62/docs/src/mcp.md) against your installed version.

## Configure your own key and server

1. In Moltis, open **Settings → Environment Variables** and set `BAIZHI_API_KEY` to your own key. This is Moltis-managed configuration. Merely exporting a variable in your shell is not the setup verified by this guide.
2. Open the MCP settings page and **Add Custom MCP Server**. Choose **Streamable HTTP**, enter `https://agent-toolkit.app.baizhi.cloud/mcp`, and enter `Authorization=Bearer ${BAIZHI_API_KEY}` in **Request headers (KEY=VALUE per line)**. The form derives the server ID from the URL; an optional display name is only a label. Add the server after your managed key is ready.
3. Inspect the connected server's discovered tools before approving a task. The runtime namespaces them as `mcp__<server-id>__<remote-tool-name>`; their actual names and schemas come from the server. This guide does not restrict the catalog to search/read or promise that every offered operation is read-only.

Use one configuration route rather than adding the same endpoint twice. The TOML route below explicitly names the server `baizhi`.

If you maintain `moltis.toml`, merge the following section into your existing configuration instead of replacing the file. Keep the entry disabled until the managed key and account access are ready, then change `enabled` to `true` and restart Moltis to use the updated configuration.

```toml
[mcp.servers.baizhi]
transport = "streamable-http"
url = "https://agent-toolkit.app.baizhi.cloud/mcp"
headers = { Authorization = "Bearer ${BAIZHI_API_KEY}" }
enabled = false
request_timeout_secs = 60
```

An alternative to the Settings value is a local `[env]` entry in `moltis.toml`, as described upstream. A key saved there is a credential-bearing local configuration file: keep it private and out of version control. Do not put this remote server's key in `[mcp.servers.baizhi.env]`; that field is for the stdio process configuration, not remote Header substitution.

Missing managed variables are left as literal placeholders. Moltis does **not** automatically disable the remote server when a key is absent; connecting can still send a request that the service rejects. Set the managed value before enabling the server. Authentication here is a static API-key Bearer header, not an OAuth login.

## First use and troubleshooting

A small first task is: **Find the official Model Context Protocol transport documentation, read the relevant page, and summarize it with source links.** Review the actual tool calls and their arguments. A connected status or catalog alone does not prove useful production results; the returned content and cited sources must support the answer.

- **Authentication fails:** Check the Moltis-managed variable name and your service key/access. A 401 may enter Moltis's generic OAuth discovery path; that does not make this static-key integration OAuth. Correct the configured key rather than expecting an OAuth registration to fix it.
- **No tools appear:** Confirm that the server is enabled and the configuration was loaded. Review the service's actual tool list. This snapshot's MCP client reads a single `tools/list` response; this guide does not promise discovery of a paginated catalog.
- **A request times out:** The example allows 60 seconds per request. Inspect the failure before retrying; a client timeout does not prove the remote operation stopped or that no service usage was charged.
- **Rotate or remove access:** Update the managed key and reconnect/restart, or disable/remove the MCP server and restart. Removing a local server does not revoke the key; revoke it in your BaizhiCloud account when appropriate.

Current Moltis status projections hide Header values, but stored configuration remains credential-bearing. Review logs and exported configuration before sharing them; this guide makes no claim about encrypted storage.

## What was actually validated

[Reproduction scripts, native tests and configuration](../validation/moltis/README.md) are included in this repository.

Seven checks passed on macOS arm64 with Rust 1.98.1 and the upstream `Cargo.lock`, without changing Moltis production code:

- A real `McpManager` connected to a loopback HTTP fixture, performed initialize/tool discovery, and used `sync_mcp_tools` to register tools in Moltis's real `ToolRegistry`.
- Calls through the registered native agent adapter reached the fixture with the expected Bearer Header, preserved Unicode arguments, and removed Moltis's internal metadata/null arguments. Status omitted the synthetic token. Stop removed the registered tools and sent authenticated session DELETE; retained tools could no longer call the stopped server.
- Incorrect or missing managed keys were rejected; an invalid Header failed before network I/O. Tool errors and request timeouts propagated, with cleanup still available.
- The TOML example parsed with Moltis's native configuration types and stayed disabled by default.

The HTTP server, credentials, catalog and tool results were synthetic. Production calls were **0**. No model conversation, web UI, gateway authentication, real account, billing, Windows/Linux runtime, OAuth, reconnect/rotation, paginated discovery or newest MCP-version conformance was exercised. The fixture used this client's `2024-11-05` protocol token. The repository pins a different nightly toolchain; the tests above used the stated stable compiler, so they are not an upstream full-suite or pinned-nightly result.
