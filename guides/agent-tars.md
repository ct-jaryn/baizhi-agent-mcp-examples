# Baizhi Cloud with Agent TARS

This is an independent community example for Agent TARS, the CLI/agent stack in
[UI-TARS-desktop](https://github.com/bytedance/UI-TARS-desktop). It is not an
upstream endorsement or a compatibility claim for every UI-TARS Desktop mode.
The author is contributing as part of the Baizhi integration effort.

The configuration follows source snapshot
[`c2ad42e3`](https://github.com/bytedance/UI-TARS-desktop/tree/c2ad42e3eb9b27830db41a3e6f51ca7179d9b168).
Use Node.js 22 or newer. Follow the project's installation and model-provider
setup before adding this MCP configuration. The complete CLI, browser UI and real
model workflow have not been tested by this guide.

## Configure the connection

Obtain your own key from [Baizhi Cloud Agent Toolkit](https://baizhi.cloud/landing/agent-toolkit).
Service access may require credits or payment. The public integration code does
not open-source the hosted backend. Queries, tool arguments and selected document
or page contents can be sent to Baizhi; model providers have their own data and
billing policies.

Set `BAIZHI_API_KEY` in the environment of the process that starts Agent TARS.
Use your normal secret-management method; do not place the key in a prompt, URL,
committed file or shared terminal transcript. The environment variable is read
explicitly by the TypeScript code below. A literal `${BAIZHI_API_KEY}` in JSON
is not equivalent to reading it.

Merge the following into your existing `agent-tars.config.ts`, preserving your
model settings and other `mcpServers`. A ready-to-copy file is available at
[examples/agent-tars.config.ts](../examples/agent-tars.config.ts).

```ts
import type { AgentTARSAppConfig } from '@agent-tars/interface';

const apiKey = process.env.BAIZHI_API_KEY?.trim();
if (!apiKey) {
  throw new Error('Set BAIZHI_API_KEY before starting Agent TARS');
}

export default {
  // Keep your existing model and other settings.
  mcpServers: {
    // Keep your existing MCP servers here.
    baizhi: {
      type: 'streamable-http',
      url: 'https://agent-toolkit.app.baizhi.cloud/mcp',
      headers: { Authorization: `Bearer ${apiKey}` },
    },
  },
} satisfies AgentTARSAppConfig;
```

The `@agent-tars/interface` package provides the configuration type. At the
referenced snapshot its root entry does not export `defineConfig`, despite an
older upstream example using that import. A type-only import and `satisfies`
avoid that runtime import failure.

Start a new session and inspect the discovered tool list. Use only tools that
are actually available to your key. A task can combine searching documentation
and reading selected public pages, but tool names and schemas should come from
the current server catalog. This guide does not promise fixed tool availability,
a read-only account, or a server-side spending limit.

A suitable first task after deciding your own call budget is: “Find the official
MCP transport documentation, read the relevant pages, and summarize the
Streamable HTTP requirements with citations.” Prompt instructions about a call
budget are not an enforced billing limit.

## Troubleshooting and boundaries

- Keep `type: 'streamable-http'`. The older `sse` transport is different.
- An invalid or absent key can produce a running Agent TARS session with no MCP
  tools at this snapshot. Verify discovery; session startup alone is insufficient.
  Related upstream work is tracked in [#1834](https://github.com/bytedance/UI-TARS-desktop/pull/1834)
  and [#1960](https://github.com/bytedance/UI-TARS-desktop/pull/1960).
- The host registers tools under their advertised names. Check for collisions
  with tools from other servers; a server label does not automatically namespace
  every tool name.
- After changing credentials or removing a server, start a fresh agent/session.
  The tested cleanup closes SDK clients, but this guide does not claim that it
  revokes remote sessions, unregisters old bound tools or hot-reloads credentials.
- Do not enable MCP debug logging with production secrets until its output has
  been independently reviewed for your configuration. The checks below used the
  normal logging path and a fixture that never echoed credentials in error text.

## What was verified

The [portable harness](../validation/agent-tars/README.md) runs eight focused cases
in each of two profiles: the real source `MCPAgent` and `ToolProcessor` with its
declared `@agent-infra/mcp-client@1.2.20`, then with the repository's current MCP
client source (package version 1.2.29). Both use MCP SDK 1.15.1. Node.js 22.22.2 on
macOS arm64 was tested.

The path is configuration → native MCPAgent registration → MCPClientV2 → SDK
HTTP transport → native ToolProcessor dispatch → bound tool function → tools/call
→ real SDK Client.close. The public configuration itself is loaded with synthetic
keys and rewritten to a loopback fixture URL before any request. The fixture
implements a minimal synthetic MCP JSON-RPC endpoint; it is not the Baizhi backend.
The model-selection step and UI are not exercised. Production calls: **zero**.
