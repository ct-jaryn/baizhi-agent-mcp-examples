# Agent TARS focused native-host validation

Requirements: Node.js >=22, npm, Git, and permission to bind a local TCP listener.
All fixtures and credentials are synthetic. The test child receives an allowlisted
environment and its `fetch` rejects every host except `127.0.0.1`. No model call,
production service call or user configuration write is performed.

From this directory:

```sh
npm ci --ignore-scripts --no-audit --no-fund
git clone https://github.com/bytedance/UI-TARS-desktop.git /tmp/tars-validation-source
git -C /tmp/tars-validation-source checkout c2ad42e3eb9b27830db41a3e6f51ca7179d9b168
node run-validation.mjs /tmp/tars-validation-source
```

Choose a fresh checkout path. The runner checks the exact source commit and
records hashes of the source modules it bundles, the example and package lock.
It uses esbuild only to bundle unchanged native source, not to replace host
classes with mocks. It executes both profiles and writes local logs plus
`validation-result.json`; generated output is ignored by Git.

The eight cases cover authorized discovery and native ToolProcessor dispatch,
missing/wrong/literal-placeholder authentication, explicit environment loading
and blank-key rejection in the actual published example, coexistence with an
existing independently bound server, a call-time 401, and the wrong SSE transport.
The SDK `Client.close` is transparently instrumented to confirm the real method
runs; the original implementation is called. This client cleanup does **not**
send an HTTP DELETE at the tested snapshot, so no remote-session termination is
claimed. The fixture closes its own listener during test teardown.

The two profiles differ only in the native MCP client:

| Profile | MCP client | Native host | SDK |
|---|---|---|---|
| `declared` | published 1.2.20, as pinned by the MCPAgent manifest | repository MCPAgent, MCPClientV2, Agent, ToolProcessor and related source | 1.15.1 |
| `source` | repository source, manifest version 1.2.29 | same source host | 1.15.1 |

Model selection and the full `Agent.run` loop are not exercised: the test feeds
synthetic tool-call requests into the actual `agent.runner.toolProcessor`.
The MCP server is a minimal loopback HTTP fixture. It tests client/host plumbing,
not actual Baizhi catalog schemas, billing, backend permissions, CLI config
loading, UI, browser use, cancellation, or pagination. Authentication failure can
be swallowed into an empty tool list by the current client; that known behavior
is checked and documented rather than described as a successful connection.

Recorded run: macOS arm64, Node 22.22.2; 8/8 in each profile. Package versions and
transitive dependencies are locked in `package-lock.json`. Existing upstream
package-exports ordering warnings appear while bundling; they are not failures.
