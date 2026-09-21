# Use Baizhi Agent Toolkit from OpenHuman

This independent community guide connects an optional hosted MCP service to an existing OpenHuman workspace. It is maintained as part of the Baizhi integration effort; it is not an OpenHuman endorsement or a new built-in catalog entry. The hosted Baizhi backend is not made open source by this guide.

Source reference: OpenHuman `0.63.29` at [`eb4fdc0`](https://github.com/tinyhumansai/openhuman/tree/eb4fdc0f4f4a036d8ab7c12bd52f16128e4a6b5d). This snapshot changed the MCP UI and is not a claim that every installed release has the same interface.

## What this adds

For an opt-in web research task, ask your agent to discover the connected service's tools, search for relevant public pages, read selected URLs, and produce a summary with source links. Inspect the tool names and schemas actually available to your account; availability can vary. A search result alone does not establish what a page says.

You need an OpenHuman installation with MCP enabled, a working model/provider of your choice, and your own Baizhi API key. Obtain and manage it through the [Baizhi Agent Toolkit product](https://baizhi.cloud/landing/agent-toolkit). Check your plan, credits, and data handling before use: prompts or tool arguments sent to this hosted service leave your computer, and calls may consume credits. The guide does not enforce a spending limit.

## Add the service

At the referenced snapshot, open **Connections → MCP Servers → mcp.json**. This tab is a view of the workspace's installed-server store; it is not an instruction to create an arbitrary file named `mcp.json` on disk.

1. Preserve every existing entry under `mcpServers`. Saving this editor replaces the installed set: omitted servers are uninstalled.
2. Add a `baizhi` entry using the object below. Replace `REPLACE_WITH_YOUR_KEY` locally; do not put a real key in a chat prompt, source repository, screenshot, issue, or terminal history.
3. Save while `enabled` is `false`. On the **Servers** tab, enable/connect the entry when you are ready to contact the service. Review its status and discovered tools.

```json
{
  "mcpServers": {
    "baizhi": {
      "url": "https://agent-toolkit.app.baizhi.cloud/mcp",
      "headers": {
        "Authorization": "Bearer REPLACE_WITH_YOUR_KEY"
      },
      "enabled": false,
      "description": "Optional Baizhi Agent Toolkit connection"
    }
  }
}
```

The outer document above illustrates a workspace with only this entry. Merge the inner `baizhi` object into your existing document. A URL declaration selects the remote Streamable HTTP transport. The Header value is a literal string at this snapshot: `Bearer ${BAIZHI_API_KEY}` is not an environment-variable setup command.

Credentials are accepted on write and stored separately from the displayed configuration. After saving, a read returns credential names in `envKeys` and a Boolean `authConfigured`, not the Header values. `authConfigured: true` means something is stored; it does not prove the key is valid. Do not infer operating-system keychain encryption from this display behavior.

The **Registry** tab is browse-only in this snapshot. Its entries open the service's own page; finding an entry there is not an install or an authenticated connection.

## Try a bounded task

First inspect the server's connected status and tools. In a conversation whose agent has access to MCP, you can ask:

> Use the connected `baizhi` MCP server. Inspect its available tool schemas, then find official documentation for the Model Context Protocol. Read one relevant public page and give a short summary with its source URL. Ask me before expanding the research.

This is guidance to the agent, not a hard call budget. Check the tool activity and returned content. The current OpenHuman agent architecture delegates installed MCP work through its MCP specialist; a particular model, agent profile, or disabled tool group may affect access. If the agent cannot see the connection, check the workspace, enabled state, discovered tools, and agent tool access before adding another copy of the server.

If authentication fails, verify the endpoint, `Bearer ` prefix, key, and plan. Do not retry by moving the key into the URL. Keep sensitive error details out of public reports.

## Rotate or remove credentials

Disable the server first if you want to stop using the existing connection while editing.

- **Rotate:** preserve the whole displayed document and add `headers.Authorization` containing the new complete `Bearer …` value to this entry, then save and reconnect. Current reconciliation keeps its `server_id` while refreshing a changed credential.
- **Keep:** saving a document without a `headers` block keeps existing credentials. An empty `headers` object also does not clear them.
- **Delete one Header:** write `"headers": {"Authorization": ""}` and save. This removes that stored Header; deleting the JSON field alone does not.
- **Uninstall:** remove only the `baizhi` entry from the complete document and save. Keep all other entries you intend to retain. Revoke the key at the service separately if needed.

## Validation scope

The accompanying synthetic tests target the native OpenHuman MCP configuration/store, dynamic HTTP client, product tool factory, and TinyAgents tool-batch scheduler. They exercise synthetic loopback MCP data and credentials, not Baizhi's production service or current production tool schemas. No model, desktop UI interaction, full agent conversation, registry discovery, or production tool call is covered. See the validation README and receipt for executed commands and final results; source inspection alone is not a successful connection.
