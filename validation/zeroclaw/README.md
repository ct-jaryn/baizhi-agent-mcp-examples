# ZeroClaw: six offline integration checks

These checks read the TOML example from the [community guide](../../guides/zeroclaw.md),
parse it with real ZeroClaw configuration code, and exercise its actual MCP
registry, HTTP transport, and tool wrapper. The MCP service is a local wiremock
fixture. No Baizhi key or model-provider key is needed.

## Requirements and source pin

- Python 3.9+ (tested with 3.9.6), Git, Rust/Cargo, and the native compiler/linker required by Rust
  dependencies (for example, Command Line Tools on macOS).
- Tested with Rust/Cargo **1.98.1** on **macOS aarch64**. Other platforms and
  the project's minimum Rust version were not verified by this harness.
- A clean, dedicated checkout of
  [ZeroClaw at `fba46e349b6bd084d43b721c7645525d2f5c597d`](https://github.com/zeroclaw-labs/zeroclaw/tree/fba46e349b6bd084d43b721c7645525d2f5c597d).
  This source declares version 0.8.5; do not substitute a different 0.8.5 tree.
- The existing upstream `Cargo.lock` pins dependencies, including wiremock
  0.6.5. The runner verifies its SHA-256 before using `cargo test --locked`.
- Initial Git/dependency downloads require network access. The six tests use
  loopback HTTP only, plus temporary local files. With dependencies already
  cached, `--offline` also prevents Cargo registry downloads.
- Allow several minutes for a cold build and several GiB of disk. Builds use
  two jobs, no debug information, and a separate target directory; they do not
  build the desktop or full agent runtime.

## Run

From the root of this examples repository:

```sh
git clone --no-checkout https://github.com/zeroclaw-labs/zeroclaw.git ../zeroclaw-validation
git -C ../zeroclaw-validation checkout --detach fba46e349b6bd084d43b721c7645525d2f5c597d
python3 validation/zeroclaw/run-validation.py --checkout ../zeroclaw-validation
```

Install/select Rust 1.98.1 beforehand if needed. To select a specific Cargo
binary or reuse dedicated caches:

```sh
python3 validation/zeroclaw/run-validation.py \
  --checkout ../zeroclaw-validation \
  --cargo /path/to/rust-toolchain/bin/cargo \
  --cargo-home ../zeroclaw-validation-cache/cargo \
  --target-dir ../zeroclaw-validation-cache/target
```

Add `--offline` after the first successful dependency download. The defaults
create temporary caches and remove them on exit; explicit cache directories
are retained for repeat runs. Do not use a Cargo cache containing private
registry credentials if that isolation matters for your environment.

The runner refuses an unexpected head, dirty checkout, changed lockfile, or
existing validation files. It does not check out branches, rewrite tracked
source, install toolchains, or change the user's ZeroClaw instance. It copies
only the harness and this repository's guide into the dedicated checkout's
test directory, then removes those two files in `finally`. It forwards only
PATH, selected toolchain/locale settings, and its own Cargo settings, so
service keys and ZeroClaw environment overrides are not inherited.

Expected test summary:

```text
running 6 tests
test result: ok. 6 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out
```

## Covered cases

| Check | Observation at the real implementation boundary |
|---|---|
| Guide parsing and grant merge | The TOML parses as `Config`; appending the new bundle preserves an existing server grant; an exclude removes only the denied server. |
| No grant or unknown bundle | Resolving that agent grants no servers; constructing the real registry causes no HTTP requests. |
| Authenticated discovery and call | The registry initializes and discovers over HTTP, exposes the prefixed name/schema, and `McpToolWrapper` routes exact arguments to `tools/call`. The token does not enter the URL or successful model-facing result. |
| Wrong or missing Bearer | The fixture returns HTTP 401. No tools are registered and no `tools/call` is sent. |
| Grant removal and new registry | The new registry has no tools; an already connected registry still works. This checks construction-time scoping, not a full CLI restart. |
| Secret field and storage | The documented field is marked secret, display metadata masks its value, and a save produces encrypted data that decrypts correctly in an isolated temporary store. |

The fixture's accepting edge requires the exact synthetic token. It does not
accept every request and merely assume authentication worked. Its search
schema/result are deliberately synthetic; no real search or extraction runs.

## Revision and evidence boundaries

The runtime base above is public and sufficient to reproduce these checks.
The original six checks ran on local documentation candidate
`0d068563166b97976dcedc44fc07f5a316166fca`, whose only change from the base was
the guide inside `docs/book/src/tools/mcp.md`. Final local documentation head
`e873b962b7e9879e9dfb0cd12b3f7a6b5b22da57` only qualified the prose about tool
availability; the TOML, commands, runtime source, and checks were unchanged.
Those two local heads are provenance, **not public upstream commits to fetch**.
The runner accepts them only for local reproduction and verifies that their
only tracked difference from the base is the MCP documentation page.

For public reproduction the harness reads the copied standalone guide instead
of relying on a private documentation commit. This packaging adaptation was rerun on 2026-09-21 against the final local
documentation head `e873b962b7e9879e9dfb0cd12b3f7a6b5b22da57`: all six
checks passed. It preserves the same six behavior checks.

This is not proof of a complete CLI session, model loop, approval front door,
interactive masked-terminal input, UI, cancellation, TLS behavior, or
cross-platform support. The CLI masked-input instruction was checked against
source; the secret field and encrypted save are tested directly. MCP tools and
schemas currently available for a particular Baizhi account still require
that account's discovery. No production MCP operation was performed.

A partial Rust installation can warn that `rust-objcopy` cannot load
`libLLVM.dylib` while stripping debug information. The original local setup
hit that environment issue, although the binaries built and all checks ran.
Use a complete matching Rust toolchain; this warning is not a ZeroClaw source
failure or evidence that all build output was warning-free.
