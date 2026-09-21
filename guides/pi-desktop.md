# Use Baizhi Cloud Agent Toolkit with PI-Desktop

PI-Desktop can connect to the hosted Baizhi Cloud Agent Toolkit through its user-configured HTTP MCP connection. Choose either the manual setup or the optional community catalog below; you do not need both.

This guide and catalog were prepared by a contributor affiliated with the Baizhi Cloud integration effort. They are community examples, not an official PI integration, built-in listing, endorsement, or second official maintenance line for the toolkit. [Baizhi Cloud Agent Toolkit](https://baizhi.cloud/landing/agent-toolkit) is a hosted service; these public examples do not make its backend open source.

## Before you start

- Use your own account and API key from the [Baizhi Cloud console](https://agent-toolkit.app.baizhi.cloud/). Check the service's current access, quota, pricing, and data terms. This guide does not promise free calls.
- Enter the key only in PI's local credential field. Do not put it in a conversation, terminal command, URL, screenshot, issue, or shared configuration.
- Tool arguments, such as searches, URLs, or supplied text, go to Baizhi Cloud. Tool results can become part of the Agent conversation and be sent to your selected model provider. Start with public, non-sensitive material.
- The connection uses a static `Authorization` header with a Bearer token. It does not require PI's OAuth authorization flow.
- The English UI labels and configuration behavior below were inspected in source at [`b71fcf05`](https://github.com/vastsa/PI-Desktop/tree/b71fcf05a67dce5bb91c5fbd1f96f3a15fc8fe9a) and the [`v0.15.1` source tag](https://github.com/vastsa/PI-Desktop/tree/515620a4b7f6ce90df256e28d10d95957df16792). This is not a claim of manual GUI or production testing. Later builds can differ.

## Option A: add one server manually

1. Open **Settings** from the sidebar, then **Agent → MCP**. The page title is **MCP servers**.
2. Select **Global** for use across projects. For one project, select the **Project** filter and select that project before adding the server. The **All** filter creates new servers at the global level.
3. Check for an existing `baizhi-agent-toolkit` entry and edit it if present. Otherwise select **Add**, then choose **HTTP endpoint** under **How it connects**.
4. Set **Name** to `Baizhi Cloud Agent Toolkit` and **Identifier** to `baizhi-agent-toolkit`. PI locks the identifier after creation; it also prefixes the local tool names.
5. Set **Endpoint URL** to exactly:

   ```text
   https://agent-toolkit.app.baizhi.cloud/mcp
   ```

6. Under **Headers**, select **Add header**. Set the header name to `Authorization`. In its masked value field, enter `Bearer ` followed by your own key, with one space after `Bearer`. Keep only one Authorization row.
7. Review the **Scope** row and its enable switch. New manual entries are enabled by default. If you want to save without the automatic connection attempt, turn that switch off before selecting **Save**.

Header values in the manual editor are literal strings. Typing `Bearer ${BAIZHI_API_KEY}` here does not read an environment variable. Add or edit just this entry; keep your other MCP servers and their settings.

Saving an enabled entry causes PI to attempt a connection and tool discovery. It does not itself perform a research tool call or prove that the Agent has used the server. Enabling a server makes it eligible for the Agent in its scope; it is not an instruction to run a task.

## Option B: add the community catalog to Market

The [native PI catalog](../catalogs/pi-desktop-baizhi.json) contains the fixed endpoint and a key placeholder, not a key. Its format is PI's **Catalog JSON** format, distinct from the official MCP Registry API format.

1. Open **Settings → Agent → MCP → Market → Sources**.
2. Enter a descriptive **Source name**, such as `Baizhi community examples`.
3. For the source URL, enter this public raw JSON URL:

   ```text
   https://raw.githubusercontent.com/ct-jaryn/baizhi-agent-mcp-examples/main/catalogs/pi-desktop-baizhi.json
   ```

4. Select **Catalog JSON**, then **Add source** and **Close**. Keep your existing sources. The source URL must be public HTTPS; do not enter a GitHub HTML page, local file path, service endpoint, or key-bearing URL.
5. Wait for the source query to finish, then use **Search servers** to find `Baizhi Cloud Agent Toolkit`. Other sources, including the default official Registry, are queried too; an unavailable source can delay the result. Adding a source does not install or enable its servers.
6. Select **Install** on the entry from the community source. Confirm that **Will be saved as** shows the exact endpoint above, and read the prerequisites and notes.
7. In **Required values → BAIZHI_API_KEY**, enter only your own key, **without** `Bearer `. This catalog supplies the prefix. The input is masked; the placeholder is resolved from this form, not your shell environment.
8. Select **Install** to save the server. In these source versions, Market installs at **Global** scope with enablement on and starts a connection attempt. For a project-only or initially disabled entry, use Option A instead.

If PI already has this identifier, review the existing connection rather than creating a second one. A source badge identifies where a card came from; it does not certify the service. The catalog intentionally does not request a verified badge.

This raw URL tracks this example repository's `main` branch. To keep discovery metadata fixed, you can use a reviewed commit permalink for the same JSON file. Adding a source is distinct from updating an already saved server: review connection changes through **Edit**.

## Check discovery before tool execution

Return to **My servers**. Open the server's row action menu and choose **Test connection**. A successful result reads **Connected · N tools** and lists discovered names. This explicitly makes network requests, even when the entry's enable switch is off. Save edits before testing: the test uses the saved configuration, not unsaved fields in an open editor.

There are three separate outcomes:

| Outcome | What it establishes |
| --- | --- |
| Catalog card appears | PI fetched discovery metadata. No service authentication is established. |
| **Connected · N tools** | The MCP handshake and tool-list request succeeded. No research tool result has been established. |
| An actual tool call returns useful content | That call executed; inspect its content and any authentication, quota, or service error. This does not validate every available tool. |

Initialization and discovery contact the service before research calls. Once enabled, the server's discovered tools can be made available to the Agent in the selected scope. With the identifier above, PI prefixes local tool names with `mcp_baizhi_agent_toolkit_`. The remote names and schemas come from the live server; do not copy synthetic test-tool names as service APIs.

When you are ready to incur service and model usage, a first task can be:

> Use the available tools from my Baizhi MCP connection to research a public technical topic. Inspect the available schemas first, use at most three research tool calls, return source URLs, and stop on authentication or quota errors. Do not send private files or credentials.

This is a request to the Agent, not a host-enforced spending limit. Check the actual tool calls and returned content. Do not assume all advertised tools are read-only or suitable for your data.

## Local storage and diagnostics

PI masks header values in the editor and required-value fields. After saving, however, the resolved header is stored in a plain JSON configuration file:

- Global: `~/.agents/servers/baizhi-agent-toolkit.json` by default.
- Project: `<project-root>/.agents/servers/baizhi-agent-toolkit.json`.

A custom `PI_DESKTOP_AGENTS_DIR` changes the global `.agents` root. Enablement (including per-project overrides) is stored in PI's app-local capability state; Global or Project ownership follows the configuration's location. Turning a server off does not remove its key.

Treat the configuration and any backup as sensitive. Restrict access to them and keep them out of version control or shared project archives. Masked input does not mean the header is encrypted in the operating system's keychain. Other software with access to these files can read them.

The inspected MCP audit path records connection/call metadata and error messages; its normal audit object does not include the full header map. This is not a guarantee that every diagnostic is secret-free: server-supplied error text can enter logs, and tool content can enter conversation history. Review and redact diagnostics before sharing them.

## Disable, reconnect, rotate, or remove

- **Disable:** stop the active Agent task, then turn off the server's enable switch in **MCP servers**. This removes its normal availability in that scope. An explicit **Test connection** still contacts it, and disabling does not undo a request already accepted by the remote service.
- **Reconnect:** use **Test connection** to close and recreate the saved server's client connection. There is no separate MCP **Restart** action in the inspected row menu. Restarting PI also recreates the runtime later, using the saved configuration; it does not erase the key.
- **Rotate a key:** stop the active task and disable the entry. Use **Edit** to replace only the Authorization value, keeping `Bearer ` and the fixed endpoint; **Save**. Enable and test when ready. Revoke the old key through your service account as appropriate. Saving a header change invalidates the old client; no GUI or already-running model-session rotation is claimed as tested here.
- **Remove the server:** stop the task, open the row action menu, select **Remove**, then select **Click again to delete**. PI removes that server's local configuration and refreshes its runtime. This does not revoke the remote account key, securely erase backups, or delete prior conversation content.
- **Remove only a catalog source:** use **Market → Sources → Remove** beside the custom source. This changes discovery sources; it does not uninstall the saved MCP connection. To remove the connection, use the server action above.

## Troubleshooting and version limits

| Symptom | Check |
| --- | --- |
| Catalog cannot be added or fetched | Use the raw public HTTPS JSON URL and **Catalog JSON**. A failure of another source is separate from the Baizhi service connection. |
| Card missing while loading | Wait for the current source query; review the source named in any failure. Use manual configuration if catalog discovery remains unavailable. |
| `401` or **Failed** | Correct the saved local key, prefix and endpoint, then save and test. Do not switch to OAuth to repair this static-header example. |
| Connected but no tool used | Check enablement, project scope, actual discovered schemas and the Agent's selected tools. Discovery alone is not tool execution. |
| Duplicate or unexpectedly different entry | Review both Global and Project entries; project records can shadow a global entry with the same identifier or name. Keep one intended configuration. |
| Quota, service error, or unexpected result | Stop automatic retries, inspect the result and current service account limits, and share only redacted diagnostics. |

The native catalog and manual HTTP configuration paths exist in both inspected versions. That does **not** mean v0.15.1 contains every later MCP fix. In particular, the inspected main snapshot includes the generic Registry/header-isolation work from [PI #706](https://github.com/vastsa/PI-Desktop/pull/706), and handles plain-text `202 Accepted` notification acknowledgements differently from v0.15.1. The native catalog here does not establish how the production service responds or prove a specific release will succeed or fail. A merged generic fix is also not a built-in Baizhi listing.

This guide is source-inspected, not GUI-tested. No real key, production MCP request, or paid model call was used to prepare it. The accompanying [reproducible validation](../validation/pi-desktop/) documents its own exact source versions, synthetic checks and limits; configuration checks are separate from a complete Agent or production acceptance test.

Source references: [MCP settings](https://github.com/vastsa/PI-Desktop/blob/b71fcf05a67dce5bb91c5fbd1f96f3a15fc8fe9a/apps/desktop/src/components/settings/AgentMcpPage.tsx), [editor](https://github.com/vastsa/PI-Desktop/blob/b71fcf05a67dce5bb91c5fbd1f96f3a15fc8fe9a/apps/desktop/src/components/extensions/McpEditorSheet.tsx), [Market and Sources](https://github.com/vastsa/PI-Desktop/blob/b71fcf05a67dce5bb91c5fbd1f96f3a15fc8fe9a/apps/desktop/src/components/settings/McpMarketPanel.tsx), [save/test IPC](https://github.com/vastsa/PI-Desktop/blob/b71fcf05a67dce5bb91c5fbd1f96f3a15fc8fe9a/apps/desktop/electron/main/ipc/mcp-ipc.ts), [runtime](https://github.com/vastsa/PI-Desktop/blob/b71fcf05a67dce5bb91c5fbd1f96f3a15fc8fe9a/apps/desktop/electron/main/user-mcp.ts), [configuration storage](https://github.com/vastsa/PI-Desktop/blob/b71fcf05a67dce5bb91c5fbd1f96f3a15fc8fe9a/crates/host-core/src/mcp_servers.rs), and [PI privacy policy](https://github.com/vastsa/PI-Desktop/blob/b71fcf05a67dce5bb91c5fbd1f96f3a15fc8fe9a/docs/privacy-policy.md).
