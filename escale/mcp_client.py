"""Turn the tools of a remote MCP server into tools of the agent.

The agent loop is synchronous and the MCP SDK is asynchronous. To stay simple, each operation
opens its own short connection. A long-lived agent would keep one connection open instead.
"""

import asyncio
import json
import os

from mcp import Client

from escale.toolbox import Tool, ToolError

DEFAULT_MCP_URL = "http://127.0.0.1:8765/mcp"


def mcp_url() -> str:
    return os.environ.get("ESCALE_MCP_URL", DEFAULT_MCP_URL)


class McpUnavailableError(ToolError):
    """The MCP server could not be reached."""


def _reason(error: Exception) -> str:
    """Return the readable cause: the SDK wraps network failures in exception groups."""
    while isinstance(error, ExceptionGroup):
        error = error.exceptions[0]
    return str(error)


def _result_text(result) -> str:
    """Convert an MCP tool result into the text sent back to Claude."""
    if result.structured_content is not None:
        return json.dumps(result.structured_content, ensure_ascii=False)
    return "\n".join(block.text for block in result.content if block.type == "text")


async def _list_tools(server):
    async with Client(server) as client:
        return (await client.list_tools()).tools


async def _call_tool(server, name: str, arguments: dict):
    async with Client(server) as client:
        return await client.call_tool(name, arguments)


def mcp_deferred() -> bool:
    """`ESCALE_MCP_DIFFERE=1` keeps the MCP definitions out of the context until Claude needs them."""
    return os.environ.get("ESCALE_MCP_DIFFERE") == "1"


def load_mcp_tools(server, deferred: bool = False) -> list[Tool]:
    """Discover the tools of a server. `server` is a URL, or a server object in tests.

    The MCP description and schema are passed to Claude as they are: this is what lets
    the agent use a tool that its own code has never heard of.

    With `deferred`, each definition carries `defer_loading`: the API does not put it in
    the context, Claude finds it through the tool search tool when it needs it.
    """
    try:
        remote_tools = asyncio.run(_list_tools(server))
    except Exception as error:
        raise McpUnavailableError(_reason(error)) from error

    tools = []
    for remote in remote_tools:

        def handler(tool_input: dict, name: str = remote.name) -> str:
            try:
                result = asyncio.run(_call_tool(server, name, tool_input))
            except Exception as error:
                raise McpUnavailableError(f"Serveur MCP injoignable : {_reason(error)}") from error
            text = _result_text(result)
            if result.is_error:
                raise ToolError(text or f"Le tool MCP {name} a échoué.")
            return text

        definition = {
            "name": remote.name,
            "description": remote.description or remote.name,
            "input_schema": remote.input_schema,
        }
        if deferred:
            definition["defer_loading"] = True
        tools.append(Tool(definition=definition, handler=handler, source="mcp"))
    return tools
