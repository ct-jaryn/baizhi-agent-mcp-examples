"""Real CowAgent host path against a synthetic, loopback-only MCP server.

No Baizhi endpoint, production credential, LLM, UI, or external tool is used.
Use run.py --repo /path/to/CowAgent for pinned, isolated execution.
"""

import json
import os
import socket
import sys
import threading
import time
from contextlib import contextmanager

import pytest
import uvicorn
from mcp.server.fastmcp import FastMCP


def _loopback_only(event, args):
    if event in {"socket.connect", "socket.bind"}:
        address = args[1]
        if isinstance(address, tuple) and address[0] not in {"127.0.0.1", "::1"}:
            raise RuntimeError("This validation permits loopback networking only")


sys.addaudithook(_loopback_only)
assert os.environ.get("COW_DATA_DIR"), "Use an isolated COW_DATA_DIR"

from agent.permission import FULL_ACCESS
from agent.protocol.agent import Agent
from agent.protocol.agent_stream import AgentStreamExecutor
from agent.protocol.models import LLMModel
from agent.registry import AgentProfile, AgentRegistry, set_agent_registry
from agent.tools.mcp.mcp_client import McpClientRegistry
from agent.tools.tool_manager import ToolManager, _normalize_mcp_configs
from config import conf


SYNTHETIC_KEY = "cowagent-fixture-only-not-a-real-key"


def wait_for(predicate, timeout=8):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("Host/server did not reach the expected state in time")


class AuditAuth:
    def __init__(self, app):
        self.app = app
        self.expected = "Bearer " + SYNTHETIC_KEY
        self.requests = []

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = {k.decode().lower(): v.decode() for k, v in scope["headers"]}
        record = {
            "verb": scope["method"],
            "auth_matches": headers.get("authorization") == self.expected,
            "marker": headers.get("x-fixture-marker"),
            "has_session": bool(headers.get("mcp-session-id")),
            "rpc": None,
        }
        self.requests.append(record)
        if not record["auth_matches"]:
            record["status"] = 401
            await send({"type": "http.response.start", "status": 401,
                        "headers": [(b"content-type", b"application/json")]})
            await send({"type": "http.response.body", "body": b'{"error":"unauthorized"}'})
            return
        chunks = []

        async def audited_receive():
            message = await receive()
            if message["type"] == "http.request":
                chunks.append(message.get("body", b""))
                if not message.get("more_body", False) and b"".join(chunks):
                    record["rpc"] = json.loads(b"".join(chunks))
            return message

        async def audited_send(message):
            if message["type"] == "http.response.start":
                record["status"] = message["status"]
            await send(message)

        await self.app(scope, audited_receive, audited_send)


@contextmanager
def synthetic_server(json_response=True):
    mcp = FastMCP("CowAgent loopback fixture", json_response=json_response)

    @mcp.tool()
    def fixture_search(query: str, options: dict) -> str:
        """Return a synthetic research result. No external requests."""
        return json.dumps({"query": query, "options": options, "synthetic": True}, ensure_ascii=False)

    @mcp.tool()
    def fixture_read(url: str) -> str:
        """Echo a synthetic document URL without fetching it."""
        return "synthetic document: " + url

    @mcp.tool()
    def fixture_extract(text: str) -> str:
        """Echo synthetic supplied content without an external model."""
        return "synthetic extraction: " + text

    auth = AuditAuth(mcp.streamable_http_app())
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    server = uvicorn.Server(uvicorn.Config(auth, log_level="error", lifespan="on"))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    try:
        wait_for(lambda: server.started)
        yield "http://127.0.0.1:%s/mcp" % sock.getsockname()[1], auth
    finally:
        server.should_exit = True
        thread.join(timeout=8)
        sock.close()
        assert not thread.is_alive(), "Synthetic MCP server failed to stop"


@pytest.fixture
def host(tmp_path):
    settings = conf()
    original = dict(settings)
    settings.clear()
    settings["agent_workspace"] = str(tmp_path)
    set_agent_registry(AgentRegistry([AgentProfile("default", "Fixture", str(tmp_path))], "default"))
    ToolManager.reset_instances()
    McpClientRegistry._instance = None
    manager = ToolManager()
    empty_tools = tmp_path / "empty-builtins"
    empty_tools.mkdir()

    def load(entries):
        (tmp_path / "mcp.json").write_text(json.dumps({"mcpServers": entries}), encoding="utf-8")
        manager.load_tools(str(empty_tools))
        wait_for(lambda: all(s != "pending" for s in manager.list_mcp_status().values()))
        return manager

    yield manager, load, tmp_path
    manager.shutdown_mcp()
    ToolManager.reset_instances()
    McpClientRegistry._instance = None
    set_agent_registry(None)
    settings.clear()
    settings.update(original)


def entry(url, header=None, prefix="baizhi_"):
    return {"type": "streamable-http", "url": url, "tool_name_prefix": prefix,
            "headers": {"Authorization": header if header is not None else "Bearer " + SYNTHETIC_KEY,
                        "X-Fixture-Marker": "fixed-value"}}


def executor(manager, workspace):
    model = LLMModel("synthetic-no-model-calls")
    agent = Agent("Synthetic test only", model=model, enable_skills=False,
                  workspace_dir=str(workspace), skip_context_files=True)
    agent.permission_mode = FULL_ACCESS
    manager.sync_mcp_into_agent(agent)
    return AgentStreamExecutor(agent, model, "Synthetic test only", agent.tools)


def call(ex, name="baizhi_fixture_search", arguments=None):
    return ex._execute_tool({"id": "fixture-call", "name": name, "arguments": arguments or {
        "query": "公开资料研究", "options": {"limit": 2, "tags": ["unicode", "合成"]}}})


@pytest.mark.parametrize("json_response", [True, False], ids=["json", "sse"])
def test_actual_initialize_discovery_binding_dispatch_and_delete(host, json_response):
    manager, load, workspace = host
    with synthetic_server(json_response) as (url, auth):
        load({"baizhi": entry(url)})
        assert manager.list_mcp_status() == {"baizhi": "ready"}
        assert set(manager._mcp_tool_instances) == {
            "baizhi_fixture_search", "baizhi_fixture_read", "baizhi_fixture_extract"}
        tool = manager.create_tool("baizhi_fixture_search")
        assert tool.params["required"] == ["query", "options"]
        assert tool.params["properties"]["options"]["type"] == "object"
        ex = executor(manager, workspace)
        result = call(ex)
        assert result["status"] == "success"
        assert json.loads(result["result"])["query"] == "公开资料研究"
        assert tool.context is ex.agent
        assert tool.progress_callback is None and tool.tool_call_id is None
        assert call(ex, "baizhi_fixture_read", {"url": "https://example.invalid/fixture"})["result"].startswith("synthetic document:")
        assert call(ex, "baizhi_fixture_extract", {"text": "synthetic only"})["result"].startswith("synthetic extraction:")
        methods = [r["rpc"]["method"] for r in auth.requests if r["rpc"]]
        assert methods == ["initialize", "notifications/initialized", "tools/list", "tools/call", "tools/call", "tools/call"]
        rpc = next(r["rpc"] for r in auth.requests if r["rpc"] and r["rpc"]["method"] == "tools/call")
        assert rpc["params"]["name"] == "fixture_search"
        assert rpc["params"]["arguments"]["options"]["tags"] == ["unicode", "合成"]
        client = tool.client
        manager.shutdown_mcp()
        assert not client._initialized and client._http_session_id is None
        assert auth.requests[-1]["verb"] == "DELETE" and auth.requests[-1]["status"] == 200
        assert all(r["auth_matches"] and r["marker"] == "fixed-value" for r in auth.requests)
        assert all(r["has_session"] for r in auth.requests[1:])


@pytest.mark.parametrize("header", ["Bearer wrong-synthetic-key", "", "Bearer ${COW_FIXTURE_KEY}"],
                         ids=["wrong-key", "empty-header", "literal-env-placeholder"])
def test_invalid_static_header_never_registers_tools(host, monkeypatch, header):
    manager, load, workspace = host
    monkeypatch.setenv("COW_FIXTURE_KEY", SYNTHETIC_KEY)
    with synthetic_server() as (url, auth):
        load({"baizhi": entry(url, header)})
        assert manager.list_mcp_status() == {"baizhi": "failed"}
        assert not manager._mcp_tool_instances
        assert len(auth.requests) == 1 and auth.requests[0]["status"] == 401
        assert not auth.requests[0]["auth_matches"]
        assert call(executor(manager, workspace))["status"] == "error"
        assert len(auth.requests) == 1


def test_case_insensitive_auth_header_and_fixed_extra_header(host):
    manager, load, workspace = host
    with synthetic_server() as (url, auth):
        cfg = entry(url)
        cfg["headers"]["authorization"] = cfg["headers"].pop("Authorization")
        load({"baizhi": cfg})
        assert manager.list_mcp_status() == {"baizhi": "ready"}
        assert call(executor(manager, workspace))["status"] == "success"
        manager.shutdown_mcp()
        assert all(r["auth_matches"] and r["marker"] == "fixed-value" for r in auth.requests)


def test_remote_url_requires_explicit_streamable_http_type():
    assert _normalize_mcp_configs({"baizhi": {"url": "http://127.0.0.1/mcp"}})[0]["type"] == "sse"
    assert _normalize_mcp_configs({"baizhi": entry("http://127.0.0.1/mcp")})[0]["type"] == "streamable-http"


def test_call_time_401_is_error_text_despite_host_success_status(host):
    """Document the current host boundary; never treat its success flag alone as acceptance."""
    manager, load, workspace = host
    with synthetic_server() as (url, auth):
        load({"baizhi": entry(url)})
        assert manager.list_mcp_status() == {"baizhi": "ready"}
        auth.expected = "Bearer different-synthetic-key"
        result = call(executor(manager, workspace))
        assert auth.requests[-1]["status"] == 401
        assert result["status"] == "success"  # Existing McpClient/McpTool behavior.
        assert result["result"].startswith("Error:") and "401" in result["result"]
        auth.expected = "Bearer " + SYNTHETIC_KEY
        manager.shutdown_mcp()


def test_disabled_flag_is_currently_not_enforced_by_loader(host):
    """Source-backed documentation correction, not a claimed disable mechanism."""
    manager, load, workspace = host
    with synthetic_server() as (url, auth):
        cfg = entry(url)
        cfg["disabled"] = True
        load({"baizhi": cfg})
        assert manager.list_mcp_status() == {"baizhi": "ready"}
        assert call(executor(manager, workspace))["status"] == "success"
        manager.shutdown_mcp()


def test_add_rotate_remove_preserves_existing_server_and_closes_old_session(host):
    manager, load, workspace = host
    with synthetic_server() as (url_a, auth_a), synthetic_server() as (url_b, auth_b):
        entries = {"existing": entry(url_a, prefix="existing_")}
        load(entries)
        existing_client = manager.create_tool("existing_fixture_search").client
        # Merge one key into the existing mcpServers object, preserving its entry.
        document = json.loads((workspace / "mcp.json").read_text())
        original_existing = document["mcpServers"]["existing"].copy()
        document["mcpServers"]["baizhi"] = entry(url_b)
        (workspace / "mcp.json").write_text(json.dumps(document))
        manager.refresh_mcp_if_changed()
        wait_for(lambda: manager.list_mcp_status().get("baizhi") == "ready")
        assert document["mcpServers"]["existing"] == original_existing
        assert manager.create_tool("existing_fixture_search").client is existing_client
        old_client = manager.create_tool("baizhi_fixture_search").client
        assert call(executor(manager, workspace))["status"] == "success"
        # A fresh executor is intentional: this is not a live-session rotation claim.
        rotated = "Bearer rotated-synthetic-key"
        document["mcpServers"]["baizhi"]["headers"]["Authorization"] = rotated
        (workspace / "mcp.json").write_text(json.dumps(document))
        manager.refresh_mcp_if_changed()
        # Teardown used the old accepted key; switch fixture policy before retrying failed initialization.
        wait_for(lambda: manager.list_mcp_status().get("baizhi") != "pending")
        auth_b.expected = rotated
        if manager.list_mcp_status().get("baizhi") != "ready":
            manager.reload_mcp_server("baizhi")
        wait_for(lambda: manager.list_mcp_status().get("baizhi") == "ready")
        assert not old_client._initialized and old_client._http_session_id is None
        assert any(r["verb"] == "DELETE" and r["status"] == 200 for r in auth_b.requests)
        assert manager.create_tool("baizhi_fixture_search").client is not old_client
        assert call(executor(manager, workspace))["status"] == "success"
        del document["mcpServers"]["baizhi"]
        (workspace / "mcp.json").write_text(json.dumps(document))
        manager.refresh_mcp_if_changed()
        assert manager.create_tool("baizhi_fixture_search") is None
        assert manager.create_tool("existing_fixture_search").client is existing_client
        assert call(executor(manager, workspace), "existing_fixture_search")["status"] == "success"
        manager.shutdown_mcp()
        assert not existing_client._initialized
