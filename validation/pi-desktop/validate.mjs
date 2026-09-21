#!/usr/bin/env node
// Native PI catalog/aggregator and Rust host persistence checks. No MCP calls.
import assert from "node:assert/strict";
import { spawn, execFileSync } from "node:child_process";
import { createHash, randomUUID } from "node:crypto";
import { EventEmitter } from "node:events";
import { readFile, mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { createRequire } from "node:module";
import { pathToFileURL, fileURLToPath } from "node:url";
import vm from "node:vm";

const [sourceArg, hostArg, expectedHead, catalogArg] = process.argv.slice(2);
if (!sourceArg || !hostArg || !/^[a-f0-9]{40}$/.test(expectedHead ?? "")) {
  throw new Error("Usage: node --experimental-vm-modules validate.mjs SOURCE_CHECKOUT HOST_BINARY EXPECTED_SHA [CATALOG_JSON]");
}
const source = resolve(sourceArg);
const hostBinary = resolve(hostArg);
const head = execFileSync("git", ["rev-parse", "HEAD"], { cwd: source, encoding: "utf8" }).trim();
assert.equal(head, expectedHead, "source commit must match the declared tested revision");
assert.equal(execFileSync("git", ["diff", "--name-only", "HEAD"], { cwd: source, encoding: "utf8" }).trim(), "", "tracked source must be unchanged");
const here = dirname(fileURLToPath(import.meta.url));
const catalogText = await readFile(catalogArg ? resolve(catalogArg) : resolve(here, "../../catalogs/pi-desktop-baizhi.json"), "utf8");
const catalogJson = JSON.parse(catalogText);
const shared = await import(pathToFileURL(join(source, "packages/shared/dist/index.js")));
const localRequire = createRequire(join(source, "packages/shared/package.json"));
const ts = localRequire("typescript");
const catalogUrl = "https://catalog.example.test/pi-baizhi-catalog.json";
const sourceSpec = { id: "baizhi-community", name: "Baizhi community catalog", kind: "catalog", url: catalogUrl };
const results = [];
async function check(name, fn) {
  await fn();
  results.push({ name, passed: true });
  console.log(`PASS ${name}`);
}
const { catalog, warnings } = shared.validateMcpCatalogFile(catalogJson);
const entry = catalog.servers[0];
const syntheticKey = "synthetic-catalog-only-not-a-real-key";
let input;
await check("native catalog schema and one required key", () => {
  assert.deepEqual(warnings, []);
  assert.equal(catalog.servers.length, 1);
  assert.equal(entry.name, "Baizhi Cloud Agent Toolkit");
  assert.equal(shared.catalogEntryError(entry), null);
  assert.deepEqual(shared.collectCatalogPlaceholders(entry), ["BAIZHI_API_KEY"]);
  assert.equal(entry.requiredEnv[0].optional, false);
  assert.equal(entry.requiredEnv[0].defaultValue, undefined);
  assert.equal(entry.verified, false);
});
await check("missing and empty key rejected by native resolver", () => {
  for (const values of [{}, { BAIZHI_API_KEY: "" }]) {
    assert.throws(() => shared.resolveCatalogEntry(entry, values), /missing value for BAIZHI_API_KEY/);
  }
});
await check("native resolution keeps key in one header and fixed HTTPS URL", () => {
  input = shared.resolveCatalogEntry(entry, { BAIZHI_API_KEY: syntheticKey });
  assert.equal(input.url, "https://agent-toolkit.app.baizhi.cloud/mcp");
  assert.deepEqual(input.headers, { Authorization: `Bearer ${syntheticKey}` });
  assert.equal(input.enabled, true);
  const withoutHeaders = { ...input, headers: undefined };
  assert.ok(!JSON.stringify(withoutHeaders).includes(syntheticKey));
  // A literal token-shaped value must not be substituted a second time.
  const literal = shared.resolveCatalogEntry(entry, { BAIZHI_API_KEY: "synthetic-${UNRELATED}" });
  assert.equal(literal.headers.Authorization, "Bearer synthetic-${UNRELATED}");
  assert.equal(literal.url, input.url);
});
await check("native HTTPS source guard and catalog endpoint guard", () => {
  assert.equal(shared.isSafeMarketSourceUrl(catalogUrl), true);
  for (const url of ["http://catalog.example.test/file.json", "https://127.0.0.1/file.json", "https://user:pass@catalog.example.test/file.json"]) {
    assert.equal(shared.isSafeMarketSourceUrl(url), false);
  }
  assert.match(shared.catalogEntryError({ ...entry, url: "http://example.test/mcp" }), /https/);
  assert.match(shared.catalogEntryError({ ...entry, url: "https://127.0.0.1/mcp" }), /public https/);
});

// Execute the real Electron-main aggregator with only external transport,
// DNS, Electron session and proxy settings replaced. No search/filter logic
// is replaced. Network calls cannot escape these mocks.
const requests = [];
const context = vm.createContext({ URL, URLSearchParams, Buffer, setTimeout, clearTimeout, AbortController, Response, console });
function moduleFrom(exports) {
  return new vm.SyntheticModule(Object.keys(exports), function () {
    for (const [key, value] of Object.entries(exports)) this.setExport(key, value);
  }, { context });
}
function request(options, receive) {
  const req = new EventEmitter();
  req.setTimeout = () => req;
  req.destroy = (error) => { if (error) queueMicrotask(() => req.emit("error", error)); return req; };
  req.end = () => queueMicrotask(() => {
    const host = options.headers.Host;
    requests.push({ host, path: options.path, method: options.method, pinned: options.hostname });
    if (host !== "catalog.example.test" || options.path !== "/pi-baizhi-catalog.json") {
      req.emit("error", new Error("synthetic registry failure"));
      return;
    }
    assert.equal(options.hostname, "93.184.216.34");
    const res = new EventEmitter();
    res.statusCode = 200;
    res.headers = { "content-type": "application/json" };
    res.resume = () => {};
    receive(res);
    res.emit("data", Buffer.from(catalogText));
    res.emit("end");
  });
  return req;
}
const original = await readFile(join(source, "apps/desktop/electron/main/mcp-registry-catalog.ts"), "utf8");
const code = ts.transpileModule(original, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 } }).outputText;
const aggregatorModule = new vm.SourceTextModule(code, { context });
await aggregatorModule.link(async (specifier) => {
  if (specifier === "@pi-desktop/shared") return moduleFrom(shared);
  if (specifier === "electron") return moduleFrom({ net: { fetch: async () => { throw new Error("unexpected proxied transport"); } }, session: { defaultSession: { resolveProxy: async () => "DIRECT" } } });
  if (specifier === "node:dns/promises") return moduleFrom({ lookup: async () => [{ address: "93.184.216.34", family: 4 }] });
  if (specifier === "node:https") return moduleFrom({ request });
  if (specifier === "./network-proxy") return moduleFrom({ currentNetworkProxy: () => ({ allowFakeIp: false }) });
  if (specifier === "node:net") return moduleFrom(await import("node:net"));
  throw new Error(`Unexpected native import: ${specifier}`);
});
await aggregatorModule.evaluate();
await check("real aggregator loads static JSON and filters locally", async () => {
  const api = aggregatorModule.namespace.createMcpMarketAggregator();
  const found = await api.search("baizhi", [sourceSpec]);
  assert.equal(found.entries.length, 1);
  assert.equal(found.entries[0].id, entry.id);
  assert.equal(found.entries[0].sourceId, sourceSpec.id);
  assert.equal(found.entries[0].requiredEnv[0].name, "BAIZHI_API_KEY");
  assert.deepEqual(Array.from(found.failedSources), [shared.DEFAULT_MARKET_SOURCE.name]);
  assert.equal(found.exhausted, true);
  const miss = await api.search("definitely-not-matching", [sourceSpec]);
  assert.equal(miss.entries.length, 0);
  const catalogRequests = requests.filter((request) => request.host === "catalog.example.test");
  assert.equal(catalogRequests.length, 1, "catalog cache reused; no server-side search query");
  assert.equal(catalogRequests[0].path, "/pi-baizhi-catalog.json");
});
await check("real aggregator retains custom result when Registry fails", async () => {
  const api = aggregatorModule.namespace.createMcpMarketAggregator();
  const registry = { id: "synthetic-registry", name: "Unavailable registry", kind: "registry", url: "https://registry.example.test/v0/servers" };
  const found = await api.search("baizhi", [registry, sourceSpec]);
  assert.equal(found.entries.length, 1);
  assert.equal(found.entries[0].id, entry.id);
  assert.deepEqual(Array.from(found.failedSources), [shared.DEFAULT_MARKET_SOURCE.name, registry.name]);
});
await check("renderer contract uses password field and existing install path (source assertion)", async () => {
  const panel = await readFile(join(source, "apps/desktop/src/components/settings/McpMarketPanel.tsx"), "utf8");
  assert.match(panel, /installFor\.requiredEnv\.map\(/);
  assert.match(panel, /type="password"/);
  assert.match(panel, /autoComplete="off"/);
  assert.match(panel, /resolveCatalogEntry\(installFor, values\)/);
  assert.match(panel, /api\.upsertMcpServer\(\{ \.\.\.input, level: "global", scope: GLOBAL_SCOPE \}\)/);
  assert.match(panel, /\["registry", "catalog"\]/);
});

// Rust host-core owns config persistence. It does not run the separate Node
// MCP runtime; upsert/list here makes no MCP initialize/list/call request.
const temp = await mkdtemp(join(tmpdir(), "pi-baizhi-catalog-validation-"));
let child;
const pending = new Map();
let stdout = "";
let stderr = "";
async function call(method, params = {}) {
  const id = randomUUID();
  return new Promise((resolveCall, reject) => {
    const timer = setTimeout(() => { pending.delete(id); reject(new Error(`host RPC timeout: ${method}`)); }, 10000);
    pending.set(id, { resolve: resolveCall, reject, timer });
    child.stdin.write(JSON.stringify({ jsonrpc: "2.0", id, method, params }) + "\n");
  });
}
try {
  child = spawn(hostBinary, [], { stdio: ["pipe", "pipe", "pipe"], env: { PATH: process.env.PATH ?? "", HOME: join(temp, "home"), PI_DESKTOP_DATA_DIR: join(temp, "data") } });
  child.on("error", (error) => { for (const p of pending.values()) { clearTimeout(p.timer); p.reject(error); } pending.clear(); });
  child.on("exit", () => { for (const p of pending.values()) { clearTimeout(p.timer); p.reject(new Error("host exited")); } pending.clear(); });
  child.stderr.on("data", (data) => { stderr += data.toString(); });
  child.stdout.on("data", (data) => {
    stdout += data.toString();
    let index;
    while ((index = stdout.indexOf("\n")) >= 0) {
      const line = stdout.slice(0, index); stdout = stdout.slice(index + 1);
      if (!line) continue;
      const response = JSON.parse(line);
      const p = pending.get(String(response.id));
      if (!p) continue;
      pending.delete(String(response.id)); clearTimeout(p.timer);
      if (response.error) p.reject(new Error("host returned an RPC error")); else p.resolve(response.result);
    }
  });
  await call("app.handshake", { protocolVersion: shared.PROTOCOL_VERSION });
  await check("real host upsert/list/disk preserve resolved endpoint and header", async () => {
    await call("mcp.upsert", { server: { ...input, level: "global", scope: shared.GLOBAL_SCOPE } });
    const list = await call("mcp.list", { level: "global" });
    const row = list.servers.find((server) => server.id === entry.id);
    assert.ok(row);
    const disk = JSON.parse(await readFile(join(temp, "home/.agents/servers", `${entry.id}.json`), "utf8"));
    for (const server of [row, disk]) {
      assert.equal(server.url, input.url);
      assert.equal(server.headers.Authorization, `Bearer ${syntheticKey}`);
      assert.ok(!server.url.includes(syntheticKey));
    }
    assert.equal(row.enabled, true);
    assert.equal(disk.enabled, undefined, "activation belongs to app-local state, not the config file");
    assert.ok(!stderr.includes(syntheticKey), "host stderr must not contain the synthetic key");
  });
  await check("real host rejects invalid transport endpoint without damaging saved entry", async () => {
    await assert.rejects(call("mcp.upsert", { server: { ...input, url: "not-a-url", level: "global", scope: shared.GLOBAL_SCOPE } }), /RPC error/);
    const list = await call("mcp.list", { level: "global" });
    assert.equal(list.servers.find((server) => server.id === entry.id).url, input.url);
  });
} finally {
  if (child && child.exitCode === null) {
    const exited = new Promise((resolveExit) => child.once("exit", resolveExit));
    child.kill("SIGTERM");
    await exited;
  }
  await rm(temp, { recursive: true, force: true });
}
console.log(JSON.stringify({ head, node: process.version, typescript: ts.version, catalogSha256: createHash("sha256").update(catalogText).digest("hex"), hostBinarySha256: createHash("sha256").update(await readFile(hostBinary)).digest("hex"), checksPassed: results.length, productionCalls: 0, actualElectronUi: false, mcpNetworkCalls: 0, results }, null, 2));
