import os
import subprocess
import time
from typing import Optional
from langchain_core.tools import tool
import mcp
from core.logger import logger


def exec_cmd(command: str, timeout: int = 30) -> str:
    """
    Executes an arbitrary terminal/shell command safely with a specified execution timeout.
    Use this to run test suites, install packages, or lint files.
    """
    
    try:
        logger.info(f"[Tool: exec_cmd] Running command with {timeout}s timeout: {command}")
        result = subprocess.run(
            command,
            shell=True,
            text=True,
            capture_output=True,
            timeout=timeout
        )
        output = f"--- STDOUT ---\n{result.stdout}\n"
        if result.stderr:
            output += f"--- STDERR ---\n{result.stderr}\n"
        return output if output.strip() else "Command executed successfully with no output."
    except subprocess.TimeoutExpired:
        logger.error(f"[Tool: exec_cmd] Command timed out after {timeout} seconds.")
        return f"Error: Command timed out after exceeding its {timeout} second allocation limit."
    except Exception as e:
        return f"Error executing terminal command: {str(e)}"
