import os
import sys

from mcp import StdioServerParameters


MCP_SERVER_PARAMS = StdioServerParameters(
    command=sys.executable,
    args=[
        "D:/Visual_Studio_Code/local_ai_claude/mcp_tools/mcp_server.py"
    ],
    env={
        **os.environ,
        "PYTHONPATH": "D:/Visual_Studio_Code/local_ai_claude"
    }
)