import { build } from "esbuild";
import { readFile, writeFile, mkdir } from "node:fs/promises";
import { createHash } from "node:crypto";
import { spawnSync } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
const here = dirname(fileURLToPath(import.meta.url));
const repo = resolve(process.argv[2] ?? "");
if (!process.argv[2])
  throw Error("Usage: node run-validation.mjs /path/to/UI-TARS-desktop");
if (Number(process.versions.node.split(".")[0]) < 22)
  throw Error("Node >=22 required");
const head = spawnSync("git", ["-C", repo, "rev-parse", "HEAD"], {
  encoding: "utf8",
}).stdout.trim();
const expected = "c2ad42e3eb9b27830db41a3e6f51ca7179d9b168";
if (head !== expected)
  throw Error(
    `Expected source ${expected}; got ${head}. Review changes before adapting this harness.`,
  );
await mkdir(resolve(here, ".build"), { recursive: true });
const configFile = resolve(here, "../../examples/agent-tars.config.ts");
await build({
  entryPoints: [configFile],
  bundle: true,
  platform: "node",
  format: "cjs",
  outfile: resolve(here, ".build/config.cjs"),
  tsconfigRaw: { compilerOptions: { target: "ES2022" } },
});
const sourceHashes = {};
const results = [];
for (const profile of ["declared", "source"]) {
  const alias = {
    "@tarko/model-provider/types": `${repo}/multimodal/tarko/model-provider/src/types.ts`,
  };
  for (const pkg of [
    "agent",
    "agent-interface",
    "shared-utils",
    "model-provider",
    "llm-client",
    "mcp-agent-interface",
  ])
    alias[`@tarko/${pkg}`] = `${repo}/multimodal/tarko/${pkg}/src/index.ts`;
  if (profile === "source")
    alias["@agent-infra/mcp-client"] =
      `${repo}/packages/agent-infra/mcp-client/src/index.ts`;
  const result = await build({
    stdin: {
      contents: `export {MCPAgent} from ${JSON.stringify(`${repo}/multimodal/tarko/mcp-agent/src/mcp-agent.ts`)};`,
      resolveDir: here,
      loader: "ts",
    },
    bundle: true,
    platform: "node",
    format: "cjs",
    packages: "external",
    alias,
    nodePaths: [resolve(here, "node_modules")],
    outfile: resolve(here, `.build/host-${profile}.cjs`),
    tsconfigRaw: { compilerOptions: { target: "ES2022" } },
    metafile: true,
  });
  for (const file of Object.keys(result.metafile.inputs)) {
    if (file === "<stdin>") continue;
    const abs = resolve(file);
    sourceHashes[
      abs.startsWith(repo + "/") ? abs.slice(repo.length + 1) : file
    ] = createHash("sha256")
      .update(await readFile(abs))
      .digest("hex");
  }
  const child = spawnSync(process.execPath, ["--test", "host.test.mjs"], {
    cwd: here,
    env: { PATH: process.env.PATH, TEST_PROFILE: profile },
    encoding: "utf8",
    timeout: 60000,
  });
  await writeFile(resolve(here, `${profile}.log`), child.stdout + child.stderr);
  process.stdout.write(child.stdout);
  process.stderr.write(child.stderr);
  results.push({
    profile,
    status: child.status,
    signal: child.signal,
    error: child.error?.message,
  });
}
const report = {
  tested_at: new Date().toISOString(),
  head,
  node: process.version,
  platform: process.platform,
  arch: process.arch,
  profiles: results,
  config_sha256: createHash("sha256")
    .update(await readFile(configFile))
    .digest("hex"),
  lock_sha256: createHash("sha256")
    .update(await readFile(resolve(here, "package-lock.json")))
    .digest("hex"),
  sourceHashes,
};
await writeFile(
  resolve(here, "validation-result.json"),
  JSON.stringify(report, null, 2) + "\n",
);
if (results.some((x) => x.status !== 0)) process.exitCode = 1;
