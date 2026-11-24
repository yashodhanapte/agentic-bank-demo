"""Use MCP servers from the (synchronous) Agent.

MCP's Python client is async, and our Agent is a plain synchronous loop. The bridge:
each server connection lives on its own background thread that runs an event loop, and
Tool.func simply hands a coroutine to that loop and waits for the answer (with a timeout).

Each MCP server runs as a separate subprocess speaking MCP over stdio. By default the SDK
passes the subprocess only a small safe set of environment variables, so servers do NOT
receive your ANTHROPIC_API_KEY. Keep it that way: a tool server never needs the model key.
"""

import asyncio
import functools
import sys
import threading
from concurrent.futures import TimeoutError as FutureTimeout
from pathlib import Path

from mcp import Client, StdioServerParameters

from .config import Settings
from .errors import ToolServerError
from .tools import Tool

PROJECT_ROOT = Path(__file__).resolve().parents[1]

SERVERS = {
    "accounts": "bank_agents.servers.accounts",
    "transactions": "bank_agents.servers.transactions",
    "service": "bank_agents.servers.service",
}


class MCPConnection:
    """One MCP server subprocess, connected and ready to take tool calls."""

    def __init__(self, server: str, settings: Settings | None = None):
        if server not in SERVERS:
            raise ValueError(f"unknown server '{server}', choose from {sorted(SERVERS)}")
        self.server = server
        self.settings = settings or Settings.from_env()
        self._thread = None
        self._loop = None
        self._stop = None
        self._client = None
        self._error = None
        self._ready = threading.Event()

    # ------------------------------------------------------------- life cycle
    def start(self) -> "MCPConnection":
        self._thread = threading.Thread(
            target=lambda: asyncio.run(self._main()),
            name=f"mcp-{self.server}",
            daemon=True,
        )
        self._thread.start()
        if not self._ready.wait(self.settings.mcp_start_timeout):
            self.stop()
            raise ConnectionError(f"MCP server '{self.server}' did not start in time")
        if self._error is not None:
            raise ConnectionError(
                f"MCP server '{self.server}' could not be started"
            ) from self._error
        return self

    async def _main(self):
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", SERVERS[self.server]],
            cwd=str(PROJECT_ROOT),
        )
        try:
            # The connection must be opened and closed by the same task, which is why
            # the whole life of the connection sits inside this one coroutine.
            async with Client(params) as client:
                self._client = client
                self._loop = asyncio.get_running_loop()
                self._stop = asyncio.Event()
                self._ready.set()
                await self._stop.wait()
        except Exception as e:  # startup or connection failure
            self._error = e
            self._ready.set()

    def stop(self) -> None:
        if self._loop is not None and self._stop is not None:
            try:
                self._loop.call_soon_threadsafe(self._stop.set)
            except RuntimeError:  # loop already closed
                pass
        if self._thread is not None:
            self._thread.join(timeout=10)

    def __enter__(self) -> "MCPConnection":
        return self.start()

    def __exit__(self, *exc_info) -> None:
        self.stop()

    # ------------------------------------------------------------------- calls
    def _run(self, coroutine):
        future = asyncio.run_coroutine_threadsafe(coroutine, self._loop)
        try:
            return future.result(timeout=self.settings.mcp_call_timeout)
        except FutureTimeout:
            future.cancel()
            raise TimeoutError(f"MCP server '{self.server}' timed out") from None

    def tools(self) -> list[Tool]:
        """The server's tools as Tool objects, ready to give to an Agent.

        The input schema comes from the server, so our own validator checks exactly the
        rules the server publishes, before anything is sent.
        """
        listing = self._run(self._client.list_tools())
        return [
            Tool(
                name=t.name,
                description=t.description or "",
                input_schema=t.input_schema,
                func=functools.partial(self.call, t.name),
            )
            for t in listing.tools
        ]

    def call(self, tool_name: str, /, **arguments) -> str:
        result = self._run(self._client.call_tool(tool_name, arguments))
        if result.is_error:
            # Never forward the server's error text (it can echo input values).
            raise ToolServerError(f"{self.server}.{tool_name} reported an error")
        return "\n".join(
            part.text for part in result.content if getattr(part, "type", None) == "text"
        )


class MCPToolbox:
    """Several MCP servers at once:  with MCPToolbox("accounts", "service") as box: ..."""

    def __init__(self, *servers: str, settings: Settings | None = None):
        self._connections = [MCPConnection(s, settings) for s in servers]

    def __enter__(self) -> "MCPToolbox":
        started = []
        try:
            for connection in self._connections:
                started.append(connection.start())
        except Exception:
            for connection in started:
                connection.stop()
            raise
        return self

    def __exit__(self, *exc_info) -> None:
        for connection in self._connections:
            connection.stop()

    def tools(self) -> list[Tool]:
        return [tool for c in self._connections for tool in c.tools()]
