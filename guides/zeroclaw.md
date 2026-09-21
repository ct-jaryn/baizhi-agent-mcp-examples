# Baizhi Cloud Agent Toolkit with ZeroClaw

Community integration guide for ZeroClaw operators. Checked against upstream commit `fba46e349b6bd084d43b721c7645525d2f5c597d` (2026-09-21), not every release.

[Baizhi Cloud Agent Toolkit](https://baizhi.cloud/landing/agent-toolkit) is a
hosted service for web search, scraping, and structured extraction. It requires
your own Baizhi API key; account availability, quotas, and charges are managed
by Baizhi separately from your model provider. The public integration code does
not make the hosted backend open source.

This example adds an authenticated remote server without granting it to every
agent. Merge these entries into your existing `config.toml`:

```toml
[[mcp.servers]]
name = "baizhi"
transport = "http"
url = "https://agent-toolkit.app.baizhi.cloud/mcp"

[mcp_bundles.baizhi_web]
servers = ["baizhi"]

[agents.assistant]
mcp_bundles = ["baizhi_web"]
```

Use the alias of an existing agent in place of `assistant`. Append
`"baizhi_web"` to its existing `mcp_bundles` list; do not replace its other
grants or duplicate the agent table. If that bundle already exists, append
`"baizhi"` to its `servers` list. A server definition alone grants nothing.
Keep `mcp.enabled = true`.

Set the authentication header through the masked secret prompt:

```sh
zeroclaw config set mcp.servers.baizhi.headers.Authorization
```

At the prompt, enter the complete header value: `Bearer`, one space, then your
Baizhi API key. The header uses static Bearer authentication, not an OAuth
login. Keep the key out of the command line, URLs, shared TOML examples, and
agent messages. Use ZeroClaw's secret-managed editor; do not add a plaintext
`headers` value to the snippet above. Keep `secrets.encrypt = true` (the
default) for encrypted storage. Restart the affected session after changing
the header or grants.

Known integration examples use `baizhi__websearch_search`,
`baizhi__web_scrape`, and `baizhi__web_extract`. Check the tools actually
discovered for your key; availability and schemas may differ. Calls remain
subject to the agent's normal tool and approval policy. For a first check, ask
the selected agent to search for a public documentation page and return the source URL, then approve only the
intended call. That check contacts Baizhi and can consume your quota; discovering
tools alone does not verify a successful search. Do not enable blanket
`auto_approve` just to diagnose a connection.

Queries, requested URLs, extraction instructions, and any other supplied tool
arguments leave the host for Baizhi. Results can enter the model context and
session history. Send only material you intend to share with those services,
and treat fetched web content as untrusted. This configuration does not itself
set a spending limit.

If tools are absent, check the agent alias, bundle names, `mcp.enabled`, and
that the session was restarted. An authentication failure requires checking
the stored header and account access, not widening grants. Tool policy or
approval can still deny a call after a connection succeeds; see
[ZeroClaw security and approval](https://github.com/zeroclaw-labs/zeroclaw/blob/fba46e349b6bd084d43b721c7645525d2f5c597d/docs/book/src/tools/mcp.md#security-and-approval).

To revoke this agent's access, remove `"baizhi"` from every bundle it receives,
or add it to a granted bundle's `exclude` list, then restart that session.
Removing only `"baizhi_web"` is insufficient if another granted bundle includes
the same server. Preserve grants for unrelated servers.

## Validation scope

The configuration and transport path were checked against a local, synthetic MCP service using the real ZeroClaw configuration resolver, MCP registry, and tool wrapper. No Baizhi production call or complete model conversation was run. The static bearer setup instructions are based on the current CLI source; interactive terminal input was not automated.

See the [reproducible offline checks](../validation/zeroclaw/README.md) for dependencies, exact source revisions, and the six covered cases.
