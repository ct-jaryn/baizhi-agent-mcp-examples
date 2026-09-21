# PI Desktop catalog validation

This is an offline compatibility check for
[`catalogs/pi-desktop-baizhi.json`](../../catalogs/pi-desktop-baizhi.json).
It does not contact Baizhi Cloud or validate a real API key.

## Prerequisites and tested revisions

Use a clean PI Desktop checkout, Node **24.21.0** (the project's declared
minimum is 22.19.0), TypeScript **5.9.3**, and a Rust toolchain capable of the
locked dependency tree (tested with **rustc/cargo 1.98.1** on macOS arm64).
Node's `--experimental-vm-modules` option is required. Native build tools and
network access to GitHub/package registries are needed for initial setup.

| Snapshot | Fixed commit | Result |
| --- | --- | --- |
| main snapshot, package 0.15.2-beta.2 | `b71fcf05a67dce5bb91c5fbd1f96f3a15fc8fe9a` | 9/9 |
| v0.15.1 source | `515620a4b7f6ce90df256e28d10d95957df16792` | 9/9 |

The same catalog works on both because it uses the original uppercase
`${BAIZHI_API_KEY}` template syntax and a fixed URL. It does not depend on the
newer Registry header-variable mapping fix. These are source-snapshot results,
not a test of a downloaded desktop release executable.

## Reproduce

From a clone of this examples repository, choose one commit from the table.
Use a new PI checkout and target directory, not your daily PI configuration.
No real service credentials are needed.

```sh
EXAMPLES_ROOT="$PWD"
PI_TEST_ROOT="$(mktemp -d)"
PI_TEST_SHA=b71fcf05a67dce5bb91c5fbd1f96f3a15fc8fe9a

git clone https://github.com/vastsa/PI-Desktop.git "$PI_TEST_ROOT/source"
git -C "$PI_TEST_ROOT/source" switch --detach "$PI_TEST_SHA"
cd "$PI_TEST_ROOT/source"

# Use the checkout's packageManager pin via Corepack (pnpm 11.18.0 here).
corepack pnpm --filter @pi-desktop/shared install --frozen-lockfile --ignore-scripts
corepack pnpm --filter @pi-desktop/shared build

# This builds the actual Rust RPC host from the same checkout.
CARGO_TARGET_DIR="$PI_TEST_ROOT/target" cargo build -p host-core --locked

node --experimental-vm-modules \
  "$EXAMPLES_ROOT/validation/pi-desktop/validate.mjs" \
  "$PI_TEST_ROOT/source" \
  "$PI_TEST_ROOT/target/debug/pi-desktop-host-core" \
  "$PI_TEST_SHA" \
  "$EXAMPLES_ROOT/catalogs/pi-desktop-baizhi.json"
```

On Windows use the corresponding `.exe` host path and shell syntax. That OS
combination was not tested here. To check v0.15.1, repeat with a separate clean
checkout and the second SHA. Do not point the runner at a host built from a
different revision: it verifies the checkout's HEAD and prints the host binary's
SHA-256, but the caller must build the matching binary as shown above.

The runner deletes its own temporary HOME and data directory after the host
exits. It does not delete the checkout/build directory above; retain or remove
that isolated directory yourself after reviewing the result. It does not read
your daily PI settings or inherited service credentials; the child host gets
only PATH plus its isolated HOME and data directory.

## What the nine checks establish

1. Native schema accepts one entry and discovers exactly one mandatory field.
2. Native resolution rejects a missing or empty key.
3. The fixed URL remains unchanged; only Authorization receives the synthetic
   value, and token-looking input is not expanded twice.
4. Native source/endpoint guards reject insecure or private example URLs.
5. The real aggregator loads the catalog JSON and performs local filtering and
   caching, without sending the search text to the catalog URL.
6. The real aggregator preserves the catalog result when Registry sources fail.
7. Source assertions confirm the renderer's password input and existing install
   route. This is **not** a browser interaction test.
8. The real Rust host accepts the resolved server via JSON-RPC, lists it, and
   persists the endpoint/Header in temporary storage. Enabled state is checked
   through the host response, not incorrectly expected inside the config JSON.
9. An invalid endpoint upsert is rejected without damaging the saved entry.

Only external Electron session/proxy configuration, DNS, and HTTPS I/O are
simulated for the aggregator. Its validation, source sanitization, catalog load,
filter, cache and failure aggregation code are the actual unmodified source.
The mandatory default Registry remains present and fails in the fixture; a
custom catalog does not suppress that request or eliminate its timeout delay.

The Rust host is real; it is the configuration owner, not the separate Node MCP
runtime. No MCP SDK connection is needed to prove this configuration path, and
none is claimed: MCP initialize/discovery/calls, wrong-key server rejection,
model execution, production billing, Electron UI, live GitHub raw fetch through
Electron, and non-macOS execution remain unverified by this test.
