# OpenHuman native MCP validation

This community test package exercises the product's actual MCP config/store and tool execution components against a synthetic authenticated HTTP server. It is not a production compatibility certificate. The [guide](GUIDE.md) explains the optional Baizhi configuration.

## Reproduce on macOS

Requirements: Git, Python 3, the Rust toolchain declared by OpenHuman (`1.96.1`), Xcode Command Line Tools, and enough storage for the native workspace build. The verified runner uses macOS `sandbox-exec` to allow only loopback networking during test execution. It fails closed on other platforms; adapt the isolation before running there.

```sh
git clone https://github.com/tinyhumansai/openhuman.git openhuman-validation
cd openhuman-validation
git checkout eb4fdc0f4f4a036d8ab7c12bd52f16128e4a6b5d
git submodule update --init --recursive
cd ..
python3 /path/to/this/package/run_validation.py \
  --repo /absolute/path/to/openhuman-validation \
  --cargo /absolute/path/to/rust-1.96.1/bin/cargo \
  --cargo-home /absolute/path/to/disposable-cargo-cache \
  --out-dir /absolute/path/to/validation-results \
  --download-deps
```

Use the actual toolchain `cargo` binary beside `rustc`, not an unconfigured rustup shim. With cached dependencies, omit `--download-deps` to build offline. The runner adds a temporary explicit test target in the correct `openhuman-cli` manifest, restores its prior contents, requires a clean root and every recursive submodule (including untracked files), validates all recursive gitlinks, and verifies the lockfile is unchanged. Start from an isolated checkout. It never configures a daily OpenHuman workspace or accepts a real service key.

Compilation can download public dependencies; test execution is a separate process restricted to loopback. The runner's environment is allowlisted, so service/model/proxy credentials are not inherited. Test configurations and MCP stores use fresh temporary directories. No model is registered or invoked.

## What is covered

- The native `mcp_clients_config_set/get` implementation, installed-server store and separate credential table.
- Real Streamable HTTP initialize, tools/list, tools/call, and session DELETE through the vendored tinymcp client.
- Native OpenHuman `all_tools` factory binds the MCP bridge to the test workspace; native TinyAgents `execute_tool_batch` looks it up and schedules the call.
- Correct, missing, wrong and literal-placeholder credentials; no credentials in the URL or config readback.
- Secret-free read/save preserves credentials and server identity; rotation, explicit Header deletion and uninstall behave separately.
- A second server remains callable; updating Authorization preserves another stored Header.
- Unicode arguments/results and cleanup.

The peer's `synthetic_echo` is a fixture tool, not a Baizhi production tool. The scheduled call is supplied directly to the actual tool-batch phase, so this does **not** test model selection, the full OpenHuman session/approval middleware, `use_mcp_server` orchestration handoff, desktop UI, actual registry discovery, paid service calls, or production tool schemas. The minimal `mcp` feature profile is not the full desktop feature set. An upstream build warning is not a passed full upstream test suite.

See `receipt.json` and `tests.log` generated in your output directory for the exact result. This validation package uses GPL-3.0-only; see [NOTICE](NOTICE.md) and [COPYING](COPYING).

The [recorded source-bound result](validation-result.json) is a sanitized receipt of the prepared package. Your reproduction writes its own result into the chosen output directory.
