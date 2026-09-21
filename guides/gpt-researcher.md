# GPT Researcher with Baizhi Cloud Agent Toolkit

This community example connects GPT Researcher's native MCP retriever to the hosted Baizhi service. It is not an official GPT Researcher plugin or marketplace listing. The integration code is open source; the Baizhi backend is a separate hosted service.

## Install the version used for validation

Python 3.12 was used with upstream commit `6f998577d547b1e54ec662dac63583aa11e3b84b`, MCP SDK 1.30.0 and langchain-mcp-adapters 0.3.2. This is a source snapshot, not a claim about every released version.

```sh
python -m pip install 'gpt-researcher @ git+https://github.com/assafelovic/gpt-researcher.git@6f998577d547b1e54ec662dac63583aa11e3b84b' 'langchain-mcp-adapters==0.3.2' 'mcp==1.30.0'
```

Configure a supported model provider separately using the [upstream setup instructions](https://github.com/assafelovic/gpt-researcher). Use your own Baizhi account and a dedicated API key. If your account supports scoped keys, use the minimum permissions required. Configure `BAIZHI_API_KEY` through your secret manager or a masked input mechanism; do not paste it into a command argument, source file, research prompt or issue.

## Run a research task

Review [the example](../examples/gpt_researcher_research.py) before running it. It uses `RETRIEVER=mcp`, the HTTPS endpoint and an explicit Python-built Authorization header. It then conducts research and writes a report. Running it uses your model provider and the hosted MCP service and can incur charges; it is not a connection-only check or a spending limit.

```sh
python examples/gpt_researcher_research.py
```

The relevant configuration is:

```python
{
    "name": "baizhi",
    "connection_url": "https://agent-toolkit.app.baizhi.cloud/mcp",
    "connection_headers": {"Authorization": f"Bearer {api_key}"},
}
```

HTTP(S) URLs select the Streamable HTTP transport. The config converter does not expand a literal `Bearer ${BAIZHI_API_KEY}`; the example explicitly reads `os.environ` and rejects an empty value. Keep authentication out of the URL.

For an existing application, append the entry to your current `mcp_configs` and include `mcp` in its existing retriever selection. The standalone example intentionally uses MCP only; it should not replace your unrelated servers or retrievers. The Agent chooses among discovered tools, so a useful research result is a stronger check than simply seeing a configured server. Model selection is not a service-side permission boundary.

## Data and costs

Tool arguments are sent to Baizhi. Results may reach your model provider and research output. Use public material for an initial task. Retrieved content is untrusted. Check the current tool catalog, key permissions and per-tool credit costs in the [Baizhi console](https://agent-toolkit.app.baizhi.cloud/); model charges are separate. No production call was performed when preparing this guide.

## Verified scope

Nine checks passed: five loopback tests through the native MCP client/retriever and four existing configuration regressions. The local fixture rejects wrong, missing and unexpanded authentication, verifies tool calls and session deletion, and checks that two servers retain distinct credentials. Only the model's decisions and service responses are synthetic; the MCPRetriever, selection parser, research skill, adapters and HTTP transport execute their real code.

This does not verify real model decisions, Baizhi's current tool schema, billing, UI or production compatibility. [Validation instructions](../validation/gpt-researcher/README.md) and the [upstream client source](https://github.com/assafelovic/gpt-researcher/blob/6f998577d547b1e54ec662dac63583aa11e3b84b/gpt_researcher/mcp/client.py) describe the boundary.
