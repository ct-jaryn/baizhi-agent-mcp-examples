# Use Baizhi Cloud Agent Toolkit with CowAgent

CowAgent can consume Baizhi Cloud Agent Toolkit through its native Streamable HTTP MCP client. This is an optional, user-configured connection; it does not install a CowAgent plugin or add a built-in provider.

This community example was prepared to support the Baizhi Cloud integration effort. It is not an official CowAgent integration, endorsement, or a second official maintenance line for the toolkit. [Baizhi Cloud Agent Toolkit](https://baizhi.cloud/landing/agent-toolkit) is a hosted service. Public integration examples do not make its backend open source.

## Before you configure it

- Have a working CowAgent installation and your own Baizhi Cloud API key. Review the service's current account, quota, pricing, and data-handling terms. This guide does not promise free access.
- Review the tools and arguments before allowing calls. Queries, URLs, supplied text, and any other tool arguments go to the remote service. Use public, non-sensitive research material for your first task.
- This example uses static Bearer authentication. It does not use CowAgent's OAuth login flow.
- The host path was validated at CowAgent [`e2a97497abbda2abf023cd5fec99b4613e94e5af`](https://github.com/zhayujie/CowAgent/tree/e2a97497abbda2abf023cd5fec99b4613e94e5af), on Python 3.12.14. This is a source snapshot, not a claim about every packaged release.

## Add the connection locally

Open the MCP configuration file for the CowAgent workspace you actually use. The standard workspace uses `~/cow/mcp.json`. With the official Docker Compose setup, edit the host's `./cow/mcp.json`, mounted at `/home/agent/cow/mcp.json` in the container. Custom or multiple-agent workspaces can use another file; confirm the active workspace before editing.

If the file exists, keep a local protected backup. Add only the `baizhi-agent-toolkit` member to its existing `mcpServers` object. Preserve all other entries and unrelated fields. If this member already exists, review and update it instead of making a duplicate. The complete object below is suitable for a new file; do not replace an existing multi-server configuration with it.

```json
{
  "mcpServers": {
    "baizhi-agent-toolkit": {
      "type": "streamable-http",
      "url": "https://agent-toolkit.app.baizhi.cloud/mcp",
      "tool_name_prefix": "baizhi_",
      "headers": {
        "Authorization": "Bearer REPLACE_WITH_YOUR_BAIZHI_API_KEY"
      }
    }
  }
}
```

Replace `REPLACE_WITH_YOUR_BAIZHI_API_KEY` in your local editor. Keep the `Bearer ` prefix and its space. Do not paste the key or the completed configuration into an Agent conversation, issue, PR, screenshot, or diagnostic log.

Important CowAgent-specific details:

- Set `type` to `streamable-http`. In this snapshot, a remote URL without a type selects the legacy SSE transport.
- `headers` values are sent literally. `Bearer ${BAIZHI_API_KEY}` does **not** read an environment variable. The `env` field configures a stdio subprocess and is not a substitute for HTTP headers.
- The presence of `Authorization`, including an empty or invalid value, selects static authentication and skips OAuth. A rejected key requires correction; an OAuth prompt is not the expected recovery path.
- `mcp.json` stores the header in plain text. Restrict filesystem access to the file and any backup, and keep both out of version control. For example, on a single-user Unix installation, `chmod 600 ~/cow/mcp.json` limits the standard file to its owner; adapt ownership and permissions for Docker or a shared installation.
- The `baizhi_` prefix changes only CowAgent's local tool names. It avoids unprefixed name collisions, while requests to the server use the original discovered names. Choose another unique prefix if you already use this one.

## Check discovery, then try a bounded research task

Restart CowAgent after the edit. MCP loading is asynchronous; wait for the server to finish loading before expecting its tools. CowAgent also supports configuration refresh on later messages, but restarting is a straightforward way to test the new configuration with a fresh session.

Check the MCP connection's status and discovered schemas in your installation. Look for tool names beginning with `baizhi_`; do not assume this guide's test-fixture names are real service tools. The published tool list, fields, and required arguments can change.

For a first task, set a small call budget and ask the Agent to research a public topic. For example:

> Use the available `baizhi_` research tools to find and read public documentation about the MCP transport used by CowAgent. Use at most three tool calls. Inspect each selected tool's schema first, return source URLs, and stop if authentication or quota is rejected. Do not send private files or credentials.

This prompt is a request to the Agent, not a host-enforced spending cap. Check that an actual tool was selected, the returned content is useful, and the output contains no authentication or quota error. Discovery by itself is not successful tool execution. At the tested CowAgent snapshot, a call that receives HTTP `401` can return an `Error:` string while the wrapper status still says `success`; do not treat that status alone as acceptance.

## Change or remove the connection

For key rotation, stop the active task, replace only the local `Authorization` value, and restart CowAgent with a fresh conversation before testing again. Revoke the old key through the service's account controls as appropriate. The verification below checked client teardown and a fresh executor after rotation; it does not prove that every already-running conversation replaces its existing tool instance.

To remove this integration, stop CowAgent, remove only `baizhi-agent-toolkit` from the relevant MCP configuration, preserve the other servers, and restart. Confirm that `baizhi_` tools are absent. Do not rely on `"disabled": true` at the pinned commit tested here: its loader does not enforce it. As of preparation on September 21, 2026, pending [CowAgent PR #3155](https://github.com/zhayujie/CowAgent/pull/3155) proposes that support; recheck your installed version before relying on this field.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| No `baizhi_` tools | Active workspace/file, valid JSON, explicit `streamable-http`, asynchronous load status, unique prefix. |
| `401` during connection | Correct local key, `Bearer ` prefix, no literal environment-variable placeholder. No tools should be registered for that failed connection. |
| `Error:` result despite a successful wrapper | Inspect the content. Authentication can expire after initial discovery; correct the key and reconnect. |
| Tool is missing or arguments are rejected | Inspect the currently discovered schema rather than copying fixture names or historic arguments. |
| Quota or service error | Stop retrying automatically and check current service limits/account status. Avoid sharing a full key-bearing configuration in support requests. |

## What was validated

Ten focused checks used the unmodified CowAgent host classes, an isolated workspace, and a loopback server from the official Python MCP SDK 1.26.0. The exercised path was configuration-file loading → background initialization → `tools/list` → real `McpTool` binding → the `AgentStreamExecutor` dispatch entry → `tools/call` → session `DELETE`.

The checks covered JSON and SSE response bodies, three synthetic tools, nested and Unicode arguments, local prefixes versus remote names, correct/incorrect/empty/literal-placeholder headers, case-insensitive `Authorization`, an independent fixed header, preservation of an existing server, key rotation with a fresh executor, removal, and cleanup. They also recorded the current call-error status and ignored `disabled` behavior described above.

The synthetic tools do not mirror or certify the hosted Baizhi schemas. No real API key was read, no production request was made, and no paid model was called. UI interaction, the complete model reasoning loop, other operating systems, TLS/production connectivity, pagination, cancellation, and rate-limit behavior were not validated here. See the [reproducible validation instructions and dependency lock](../validation/cowagent/README.md).

Host references: [MCP client](https://github.com/zhayujie/CowAgent/blob/e2a97497abbda2abf023cd5fec99b4613e94e5af/agent/tools/mcp/mcp_client.py), [tool manager](https://github.com/zhayujie/CowAgent/blob/e2a97497abbda2abf023cd5fec99b4613e94e5af/agent/tools/tool_manager.py), [MCP tool wrapper](https://github.com/zhayujie/CowAgent/blob/e2a97497abbda2abf023cd5fec99b4613e94e5af/agent/tools/mcp/mcp_tool.py), and [CowAgent MCP guide](https://docs.cowagent.ai/tools/mcp).
