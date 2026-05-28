import os
import sys
import asyncio
from typing import List
from mcp.server.models import InitializationOptions
from mcp.server import Server
from mcp.types import Notification
import mcp.types as types
from mcp.server.stdio import stdio_server

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from local_tools import read_tool, write_tool, exe_cmd, git_diff

server = Server("ai-devops-code-editor")

@server.list_tools()
async def handle_list_tools() -> List[types.Tool]:
    """Exposes tools with hardcoded, reliable descriptions."""
    
    # Define descriptions locally here to avoid dependency on module attributes
    tool_metadata = {
        "read_file": "Reads the contents of a file from the workspace safety sandbox.",
        "write_file": "Writes or edits text content in a file with validation protections.",
        "exec_cmd": "Executes a bounded system shell command inside the workspace terminal sandbox.",
        "git_diff": "Retrieves workspace modifications or compares two active branch deltas."
    }

    return [
        types.Tool(
            name="read_file",
            description=tool_metadata["read_file"],
            inputSchema={
                "type": "object",
                "properties": {
                    "repository_path": {"type": "string", "description": "Absolute path to the workspace directory"},
                    "file_path": {"type": "string", "description": "Relative path to the target file"}
                },
                "required": ["repository_path", "file_path"]
            }
        ),
        types.Tool(
            name="write_file",
            description=tool_metadata["write_file"],
            inputSchema={
                "type": "object",
                "properties": {
                    "repository_path": {
                        "type": "string"
                    },
                    "file_path": {
                        "type": "string"
                    }
                },
                "required": [
                    "repository_path",
                    "file_path"
                ]
            } # (keep your existing schema)
        ),
        types.Tool(
            name="exec_cmd",
            description=tool_metadata["exec_cmd"],
            inputSchema={
                "type": "object",
                "properties": {
                    "repository_path": {
                        "type": "string"
                    },
                    "file_path": {
                        "type": "string"
                    }
                },
                "required": [
                    "repository_path",
                    "file_path"
                ]
            } # (keep your existing schema)
        ),
        types.Tool(
            name="git_diff",
            description=tool_metadata["git_diff"],
            inputSchema={
                "type": "object",
                "properties": {
                    "repository_path": {
                        "type": "string"
                    },
                    "file_path": {
                        "type": "string"
                    }
                },
                "required": [
                    "repository_path",
                    "file_path"
                ]
            } # (keep your existing schema)
        )
    ]


@server.call_tool()
async def handle_call_tool(
    name: str, 
    arguments: dict | None
) -> List[types.TextContent]:
    """
    Intercepts incoming JSON-RPC tool calls from the client, routes arguments 
    to the corresponding python function, and formats the output text back safely.
    """
    if not arguments:
        arguments = {}
        
    try:
        if name == "read_file":

            result = read_tool.read_file(**arguments)

        elif name == "write_file":

            result = write_tool.write_file(**arguments)

        elif name == "exec_cmd":

            result = exe_cmd.exec_cmd(**arguments)

        elif name == "git_diff":

            result = git_diff.git_diff(**arguments)

            
        else:
            raise ValueError(f"Unknown or unsupported MCP tool reference requested: {name}")

        return [types.TextContent(type="text", text=str(result))]

    except Exception as e:
        return [types.TextContent(type="text", text=f"Tool Execution Error [{name}]: {str(e)}")]

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="local-ai-server",
                server_version="1.0.0",
                # Pass capabilities as a direct dictionary to bypass SDK version method discrepancies
                capabilities={
                    "tools": {
                        "listChanged": True
                    }
                }
            )
        )

async def run_server():
    async with stdio_server() as (read_stream, write_stream):

        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="local-ai-server",
                server_version="1.0.0",
                capabilities={
                    "tools": {
                        "listChanged": True
                    }
                }
            )
        )


if __name__ == "__main__":
    asyncio.run(run_server())