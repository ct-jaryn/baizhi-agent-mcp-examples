import test, { after } from "node:test";
import assert from "node:assert/strict";
import { createServer } from "node:http";
import { createRequire } from "node:module";
import { inspect } from "node:util";
const require = createRequire(import.meta.url);
const { MCPAgent } = require(
  `./.build/host-${process.env.TEST_PROFILE ?? "declared"}.cjs`,
);
const Client = require("@modelcontextprotocol/sdk/client/index.js").Client;
let sdkCloseCalls = 0;
const actualClose = Client.prototype.close;
Client.prototype.close = async function (...args) {
  sdkCloseCalls++;
  return actualClose.apply(this, args);
};
const secret = "synthetic-mcp-only-credential";
const originalFetch = globalThis.fetch;
globalThis.fetch = (input, options) => {
  const u = new URL(
    typeof input === "string" || input instanceof URL ? input : input.url,
  );
  assert.equal(u.hostname, "127.0.0.1", "Only loopback requests allowed");
  return originalFetch(input, options);
};
const output = [];
for (const method of ["log", "info", "warn", "error", "debug"])
  console[method] = (...args) =>
    output.push(args.map((x) => inspect(x)).join(" "));
function loadConfig(key) {
  if (key === undefined) delete process.env.BAIZHI_API_KEY;
  else process.env.BAIZHI_API_KEY = key;
  const configPath = require.resolve("./.build/config.cjs");
  delete require.cache[configPath];
  try {
    return require(configPath).default;
  } finally {
    delete process.env.BAIZHI_API_KEY;
  }
}
function readKey(key) {
  return loadConfig(key).mcpServers.baizhi.headers.Authorization.slice(7);
}
function config(url, key = secret) {
  return { ...loadConfig(key).mcpServers.baizhi, url };
}
async function fixture(name = "fixture_echo") {
  const requests = [];
  let rejectCalls = false;
  const server = createServer(async (req, res) => {
    let data = "";
    for await (const part of req) data += part;
    let body = data ? JSON.parse(data) : undefined;
    requests.push({
      method: req.method,
      url: req.url,
      authorization: req.headers.authorization,
      rpc: body?.method,
      params: body?.params,
    });
    if (
      req.headers.authorization !== `Bearer ${secret}` ||
      (rejectCalls && body?.method === "tools/call")
    ) {
      res
        .writeHead(401, { "Content-Type": "application/json" })
        .end('{"error":"Unauthorized"}');
      return;
    }
    if (req.method === "GET") {
      res.writeHead(405).end();
      return;
    }
    if (req.method === "DELETE") {
      res.writeHead(200).end();
      return;
    }
    if (body?.id === undefined) {
      res.writeHead(202).end();
      return;
    }
    const results = {
      initialize: {
        protocolVersion: "2025-03-26",
        capabilities: { tools: {} },
        serverInfo: { name: "synthetic-server", version: "1.0.0" },
      },
      "tools/list": {
        tools: [
          {
            name,
            description: "Synthetic Unicode echo",
            inputSchema: {
              type: "object",
              properties: { query: { type: "string" } },
              required: ["query"],
            },
          },
        ],
      },
      "tools/call": {
        content: [
          {
            type: "text",
            text: JSON.stringify({
              source: "synthetic",
              ...body.params?.arguments,
            }),
          },
        ],
      },
      ping: {},
    };
    res
      .writeHead(200, {
        "Content-Type": "application/json",
        "Mcp-Session-Id": "synthetic-session",
      })
      .end(
        JSON.stringify({
          jsonrpc: "2.0",
          id: body.id,
          result: results[body.method] ?? {},
        }),
      );
  });
  await new Promise((r) => server.listen(0, "127.0.0.1", r));
  return {
    url: `http://127.0.0.1:${server.address().port}/mcp`,
    requests,
    reject() {
      rejectCalls = true;
    },
    close: () =>
      new Promise((r) => {
        server.closeAllConnections();
        server.close(r);
      }),
  };
}
function agent(mcpServers) {
  return new MCPAgent({
    name: "loopback-validation",
    model: {
      provider: "openai",
      id: "gpt-4o",
      apiKey: "synthetic-model-never-called",
    },
    mcpServers,
    defaultConnectionTimeout: 2,
  });
}
async function dispatch(
  a,
  name = "fixture_echo",
  args = { query: "中文 café" },
) {
  return a.runner.toolProcessor.processToolCalls(
    [
      {
        id: "synthetic-call",
        type: "function",
        function: { name, arguments: JSON.stringify(args) },
      },
    ],
    "synthetic-session",
  );
}
test("native registration and ToolProcessor dispatch preserve arguments and headers; cleanup closes clients", async () => {
  const f = await fixture();
  const a = agent({ research: config(f.url) });
  try {
    await a.initialize();
    assert.deepEqual(
      a.getTools().map((t) => t.name),
      ["fixture_echo"],
    );
    const result = await dispatch(a);
    assert.match(JSON.stringify(result), /中文 café/);
    assert(f.requests.some((x) => x.rpc === "initialize"));
    assert(f.requests.some((x) => x.rpc === "tools/list"));
    assert(f.requests.some((x) => x.rpc === "tools/call"));
    assert(f.requests.every((x) => x.authorization === `Bearer ${secret}`));
    assert(f.requests.every((x) => !x.url.includes(secret)));
    const closesBefore = sdkCloseCalls;
    await a.cleanup();
    assert(sdkCloseCalls > closesBefore);
    assert.equal(a.mcpClients.size, 0);
    assert(!output.join("\n").includes(secret));
  } finally {
    await a.cleanup();
    await f.close();
  }
});
for (const [name, header] of [
  ["missing", undefined],
  ["wrong", "Bearer wrong-synthetic"],
  ["literal", "Bearer ${REMOTE_MCP_API_KEY}"],
])
  test(`${name} authorization does not discover or dispatch remote tools`, async () => {
    const f = await fixture();
    const a = agent({
      research: {
        type: "streamable-http",
        url: f.url,
        headers: header ? { Authorization: header } : {},
      },
    });
    try {
      await a.initialize();
      assert.equal(a.getTools().length, 0);
      await dispatch(a);
      assert.equal(f.requests.filter((x) => x.rpc === "tools/call").length, 0);
    } finally {
      await a.cleanup();
      await f.close();
    }
  });
test("empty or absent environment value fails before connecting; valid value is trimmed", () => {
  for (const v of [undefined, "", "  "])
    assert.throws(() => readKey(v), /Set BAIZHI_API_KEY/);
  assert.equal(
    config("http://127.0.0.1/mcp", ` ${secret} `).headers.Authorization,
    `Bearer ${secret}`,
  );
});
test("adding a server preserves an existing independently bound server", async () => {
  const f = await fixture("fixture_echo");
  const other = await fixture("existing_echo");
  const existing = { existing: config(other.url) };
  const a = agent({ ...existing, research: config(f.url) });
  try {
    await a.initialize();
    assert.equal(a.getTools().length, 2);
    await dispatch(a, "existing_echo", { query: "existing" });
    await dispatch(a, "fixture_echo", { query: "added" });
    assert.equal(
      other.requests.find((x) => x.rpc === "tools/call").params.arguments.query,
      "existing",
    );
    assert.equal(
      f.requests.find((x) => x.rpc === "tools/call").params.arguments.query,
      "added",
    );
  } finally {
    await a.cleanup();
    await f.close();
    await other.close();
  }
});
test("call-time authorization failure reaches host tool-result error without credential logging", async () => {
  const f = await fixture();
  const a = agent({ research: config(f.url) });
  try {
    await a.initialize();
    f.reject();
    const result = await dispatch(a);
    assert.match(JSON.stringify(result), /401|Unauthorized/);
    assert(!output.join("\n").includes(secret));
  } finally {
    await a.cleanup();
    await f.close();
  }
});
test("SSE type does not use Streamable HTTP discovery", async () => {
  const f = await fixture();
  const a = agent({ research: { ...config(f.url), type: "sse" } });
  try {
    await a.initialize();
    assert.equal(a.getTools().length, 0);
    assert(!f.requests.some((x) => x.rpc === "initialize"));
  } finally {
    await a.cleanup();
    await f.close();
  }
});

after(() => {
  for (const value of [
    secret,
    "wrong-synthetic",
    "Bearer ${REMOTE_MCP_API_KEY}",
  ])
    assert(
      !output.join("\n").includes(value),
      "Synthetic auth value must not appear in captured logs",
    );
});
