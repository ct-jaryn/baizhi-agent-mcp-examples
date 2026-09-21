# CowAgent synthetic host validation

These ten focused checks exercise real CowAgent components against a synthetic MCP server on `127.0.0.1`. They do not require a Baizhi key or model key, and make no production or model requests. The three fixture tools are not declarations of the hosted service's tool names or schemas.

## Reproduce

Use Python 3.12 and a fresh CowAgent checkout at commit `e2a97497abbda2abf023cd5fec99b4613e94e5af`. The recorded run used Python 3.12.14 on macOS. Other operating systems are not certified by that result.

From this examples repository's root, a Unix setup is:

```sh
cow_validation_dir=$(mktemp -d)
git clone https://github.com/zhayujie/CowAgent.git "$cow_validation_dir/CowAgent"
git -C "$cow_validation_dir/CowAgent" checkout e2a97497abbda2abf023cd5fec99b4613e94e5af
python3.12 -m venv "$cow_validation_dir/venv"
"$cow_validation_dir/venv/bin/python" -m pip install -r validation/cowagent/requirements.lock.txt
"$cow_validation_dir/venv/bin/python" validation/cowagent/run.py --repo "$cow_validation_dir/CowAgent"
```

`--repo` accepts an absolute or relative checkout path. You can instead set the non-secret `COWAGENT_REPO` environment variable. Do not point it at your active CowAgent workspace or edit its configuration for this test. The runner verifies the pinned commit and rejects modifications to the tested host sources.

Dependency installation and Git cloning use the network. The actual test run permits only loopback socket connections. A sandbox may need permission to bind a local socket; `EPERM` at `socket.bind` is an environment restriction, not an authentication failure.

The runner creates an isolated temporary data/workspace directory and a minimal child environment. It does not inherit API keys, proxy settings, pytest plugins, or `HOME`, and does not change your environment or usual CowAgent configuration. Temporary state and caches are removed when it exits. The new checkout and virtual environment in `cow_validation_dir` remain for your own cleanup.

## What the ten cases cover

| Cases | Actual assertion |
| --- | --- |
| 2 | JSON and SSE response bodies: real initialization, discovery, schemas, three tools, nested/Unicode arguments, local prefixes versus remote names, Agent context/callback cleanup, and session DELETE. |
| 3 | Wrong key, empty Authorization, and literal environment-placeholder value are rejected during initialization and do not register tools. |
| 1 | Lowercase `authorization` and an independent fixed Header reach the server. |
| 1 | A remote URL without `type` selects legacy SSE; explicit `streamable-http` selects the intended transport. |
| 1 | Adding, rotating, and removing one server preserves another; teardown closes the old session and a fresh executor uses the replacement client. |
| 1 | A call-time 401 currently returns `Error:` content while CowAgent's wrapper status still says `success`. |
| 1 | At the pinned commit, the loader does not enforce `disabled: true`; a configured server still initializes and executes. |

The last two are **observations of existing behavior, not fixes**. They intentionally pass when reproducing these limitations in the pinned source. Pending [CowAgent PR #3155](https://github.com/zhayujie/CowAgent/pull/3155), checked during preparation on September 21, 2026, proposes disabled-server support; this suite does not validate that PR. The [guide](../../guides/cowagent.md) accounts for the pinned behavior rather than claiming those boundaries are solved.

The real path is `ToolManager.load_tools` → background initialization → native `McpClient` → `tools/list` → `McpTool` instances → `Agent` binding and `AgentStreamExecutor._execute_tool` → HTTP `tools/call` → `DELETE`. Unrelated built-in tools are omitted by supplying an empty built-in directory. Permission/dispatch/wrapper code runs; a base model that raises if called ensures no model generation occurs.

## Versions and limits

- CowAgent uses its native JSON-RPC client, not a replacement MCP client.
- The synthetic server uses official Python MCP SDK 1.26.0; pytest is 9.1.1. `requirements.lock.txt` pins the complete installed dependency set.
- Expected recorded result: **10 passed**, with one non-failing `pydantic-settings` forward-reference warning for FastMCP's `lifespan` annotation.
- This does not run the full application, UI or model reasoning loop. It does not validate production TLS/connectivity, Baizhi's current schemas, pagination, cancellation, rate limits, other runtimes/platforms, or replacement of tool instances in already-running conversations after key rotation.

Only synthetic scripts, dependency versions and these instructions are published here. Local logs, machine-specific source snapshots and private configuration are not included.
