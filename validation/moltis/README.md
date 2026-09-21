# Reproduce the seven Moltis checks

These checks use unmodified Moltis production crates at commit [`9d3238c322708e9d57fe235ce1c2b43ccc33af62`](https://github.com/moltis-org/moltis/tree/9d3238c322708e9d57fe235ce1c2b43ccc33af62). The runner adds two integration-test files and one TOML fixture to an isolated upstream checkout. This directory is self-contained: no original machine paths, logs, credentials, binaries or dependency caches are needed from the author.

The recorded result is **seven passing checks: six native MCP/agent-bridge tests plus one configuration test**, executed on macOS arm64 using **Rust/Cargo 1.98.1 stable** and the unchanged upstream `Cargo.lock`. Upstream declares **nightly-2026-06-20** in `rust-toolchain.toml`; that pinned nightly was not tested. These results are not a full-suite, minimum-Rust-version, `just lint`, pinned-nightly formatting, mdBook or `just release-preflight` pass.

## Requirements and setup

Use a POSIX host, Git, Python 3, a native Rust toolchain with its platform C compiler/linker, a writable temporary directory and sufficient disk space. This run was on macOS; Linux is a reproducibility target but was not executed. Windows is not supported by this runner. Public dependency download and loopback socket access are needed. Upstream workspace resolution can fetch large pinned Git repositories/submodules even for these targeted crates.

Install the tested compiler if needed, then obtain the fixed source revision:

```sh
rustup toolchain install 1.98.1 --profile minimal
git clone https://github.com/moltis-org/moltis.git /tmp/moltis-fixture-source
git -C /tmp/moltis-fixture-source checkout 9d3238c322708e9d57fe235ce1c2b43ccc33af62
```

Use the actual compiler's Cargo binary rather than a rustup shim. From this examples repository root:

```sh
MOLTIS_FIXTURE_CARGO="$(rustup which --toolchain 1.98.1 cargo)"
python3 validation/moltis/run_validation.py \
  --checkout /tmp/moltis-fixture-source \
  --cargo "$MOLTIS_FIXTURE_CARGO" \
  --cargo-home /tmp/moltis-fixture-cargo-cache \
  --target-dir /tmp/moltis-fixture-target \
  --output /tmp/moltis-fixture-results \
  --fetch-dependencies
```

Choose unused paths or reuse your own fixture checkout/cache. The runner does not delete the checkout, cache or output directory. It refuses tracked changes under `crates/`, `Cargo.toml` or `Cargo.lock`, and refuses to overwrite different files at its three test-fixture destinations. A fresh checkout is the simplest way to avoid conflicts.

`--fetch-dependencies` first builds the native bridge test without executing it, allowing public Cargo/Git downloads. The two test commands then run with `--locked --offline`. Omit that flag when the required cache is populated. `--cargo-home` should be a dedicated fixture dependency cache, not your normal credential-bearing Cargo configuration. `--scratch-dir` optionally selects the parent for a fresh temporary Moltis config/data directory; it need not be `/tmp`. Results and compiler/lock hashes are written under your `--output` directory; keep those machine-specific logs outside this public repository.

The runner constructs a fresh process environment. It does not inherit the user's provider keys, proxy variables, OAuth store, Baizhi key or Moltis configuration. A deliberately wrong *synthetic* process environment value also confirms that the tested remote Header path uses managed overrides. All service requests are made to the fixture bound on `127.0.0.1`; neither the TOML's production URL nor any real credential is used for a network request.

## Checks and boundaries

| Check | Executed path |
| --- | --- |
| Native registration, calls and cleanup | `parse_server_config` → persisted `McpRegistry` → `McpManager` → initialize/list → `sync_mcp_tools` → real `ToolRegistry` lookup → native adapter → search/read calls → stop/unregister/authenticated DELETE. Also checks Unicode, metadata/null cleanup, fixed URL/independent Header and status redaction. |
| Wrong key | The fixture rejects it; the manager does not register tools. |
| Missing managed variable | A connection attempt occurs, but the fixture rejects its unresolved credential; no tools register. |
| Invalid Header | Fails for invalid Header syntax before any network request. |
| Tool error | An MCP tool error propagates through the real agent adapter. |
| Request timeout | The client's timeout occurs, and authenticated session cleanup remains available. |
| Guide configuration | Native `MoltisConfig` parses `moltis-baizhi.toml`; the entry stays disabled by default with the intended transport/Header fields. No connection is made. |

The HTTP server, tool catalog, credentials and service output are synthetic. No model, full gateway, web UI, real account or production service is invoked. Production calls are **0**. Session DELETE proves an authenticated cleanup request, not remote billing cancellation.

The small fixture uses the client's current `2024-11-05` protocol token. It does not establish compliance with the newest MCP version, catalog pagination, OAuth, reconnect/rotation, cancellation, rate limits or TLS. A successful synthetic call does not certify Baizhi's live schema or availability. See the [user guide](../../guides/moltis.md) before intentionally enabling a real connection.
