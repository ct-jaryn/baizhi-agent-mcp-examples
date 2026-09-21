"""Loopback-only validation of the real GPT Researcher MCP retriever.

The model's selection/tool-call decisions and service data are synthetic.
MCPRetriever, selection parsing, ResearchSkill, adapters and HTTP are real.
"""
import asyncio
import json
import socket
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import uvicorn
from langchain_core.messages import AIMessage
from mcp.server.fastmcp import FastMCP
from starlette.responses import JSONResponse

from gpt_researcher.llm_provider.generic.base import GenericLLMProvider
from gpt_researcher.mcp.client import MCPClientManager
from gpt_researcher.mcp.tool_selector import MCPToolSelector
from gpt_researcher.retrievers.mcp.retriever import MCPRetriever

TOKEN = "synthetic-only-gptr-credential"


@pytest.fixture(autouse=True)
def network_boundary(monkeypatch):
    original = socket.socket.connect

    def connect(sock, address):
        if isinstance(address, tuple) and address[0] not in {"127.0.0.1", "::1"}:
            raise AssertionError("Non-loopback network is disabled for this validation")
        return original(sock, address)

    monkeypatch.setattr(socket.socket, "connect", connect)


@asynccontextmanager
async def synthetic_server(expected=TOKEN, label="fixture"):
    calls, requests = [], []
    mcp = FastMCP(label, json_response=True)

    @mcp.tool()
    async def synthetic_search(topic: str) -> dict:
        """Return synthetic research evidence for a topic."""
        calls.append(topic)
        return {"results": [{"title": label, "url": "https://example.invalid/source",
                             "content": f"SYNTHETIC EVIDENCE: {topic}"}]}

    app = mcp.streamable_http_app()

    async def guarded_app(scope, receive, send):
        if scope["type"] != "http":
            return await app(scope, receive, send)
        headers = dict(scope["headers"])
        authorized = headers.get(b"authorization") == f"Bearer {expected}".encode()
        # Store no credential values, even though every value here is synthetic.
        requests.append({"method": scope["method"], "authorized": authorized,
                         "query_empty": not scope["query_string"]})
        if not authorized:
            return await JSONResponse({"error": "unauthorized"}, status_code=401)(scope, receive, send)
        return await app(scope, receive, send)

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(guarded_app, log_level="error", lifespan="on"))
    task = asyncio.create_task(server.serve(sockets=[sock]))
    try:
        for _ in range(300):
            if server.started:
                break
            if task.done():
                await task
                raise RuntimeError("Fixture exited before startup")
            await asyncio.sleep(0.01)
        assert server.started
        yield SimpleNamespace(url=f"http://127.0.0.1:{port}/mcp", calls=calls, requests=requests)
    finally:
        server.should_exit = True
        await asyncio.wait_for(task, timeout=10)
        sock.close()


def config(url, token=TOKEN, name="fixture"):
    entry = {"name": name, "connection_url": url}
    if token is not None:
        entry["connection_headers"] = {"Authorization": f"Bearer {token}"}
    return entry


def install_model_decisions(monkeypatch):
    state = SimpleNamespace(bound=[], invoked=0)

    class Model:
        def bind_tools(self, tools):
            state.bound = [tool.name for tool in tools]
            return self

        async def ainvoke(self, messages):
            state.invoked += 1
            assert TOKEN not in str(messages)
            return AIMessage(content="", tool_calls=[{
                "id": "synthetic-call", "name": state.bound[0],
                "args": {"topic": "MCP transport authentication"}, "type": "tool_call",
            }])

    monkeypatch.setattr(GenericLLMProvider, "from_provider", lambda *a, **kw: SimpleNamespace(llm=Model()))
    monkeypatch.setattr(MCPToolSelector, "_call_llm_for_tool_selection", AsyncMock(return_value=json.dumps({
        "selected_tools": [{"index": 0, "name": "synthetic_search", "reason": "fixture", "relevance_score": 1}],
    })))
    return state


def retriever(server_config):
    researcher = SimpleNamespace(
        mcp_configs=[server_config],
        cfg=SimpleNamespace(strategic_llm_model="synthetic", strategic_llm_provider="synthetic", llm_kwargs={}),
    )
    return MCPRetriever("MCP transport authentication", researcher=researcher)


@pytest.mark.asyncio
async def test_real_retriever_selects_and_calls_remote_tool(monkeypatch, caplog):
    model = install_model_decisions(monkeypatch)
    async with synthetic_server() as service:
        host = retriever(config(service.url))
        results = await host.search_async()
        assert model.bound == ["synthetic_search"]
        assert model.invoked == 1
        assert service.calls == ["MCP transport authentication"]
        assert any("SYNTHETIC EVIDENCE" in row["body"] for row in results)
        assert host.client_manager._client is None
        assert all(r["authorized"] and r["query_empty"] for r in service.requests)
        assert sum(r["method"] == "DELETE" for r in service.requests) >= 2
        assert TOKEN not in caplog.text


@pytest.mark.parametrize("token", ["wrong-synthetic-token", None, "${BAIZHI_API_KEY}"])
@pytest.mark.asyncio
async def test_wrong_missing_or_unexpanded_header_never_calls_tools(token, monkeypatch):
    model = install_model_decisions(monkeypatch)
    async with synthetic_server() as service:
        host = retriever(config(service.url, token=token))
        assert await host.search_async() == []
        assert service.calls == []
        assert service.requests and not any(r["authorized"] for r in service.requests)
        assert model.invoked == 0
        assert host.client_manager._client is None


@pytest.mark.asyncio
async def test_two_server_credentials_remain_separate():
    async with synthetic_server(expected="synthetic-A", label="A") as first:
        async with synthetic_server(expected="synthetic-B", label="B") as second:
            manager = MCPClientManager([
                config(first.url, token="synthetic-A", name="first"),
                config(second.url, token="synthetic-B", name="second"),
            ])
            try:
                tools = await manager.get_all_tools()
                assert len(tools) == 2
                for tool in tools:
                    await tool.ainvoke({"topic": "separate credentials"})
                assert first.calls == second.calls == ["separate credentials"]
                assert all(r["authorized"] and r["query_empty"] for r in first.requests + second.requests)
            finally:
                await manager.close_client()
            assert manager._client is None
