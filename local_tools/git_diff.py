import os
import subprocess
import time
from typing import Optional
from langchain_core.tools import tool
from core.logger import logger
import mcp


def git_diff(repository_path: str, branches: Optional[str] = None) -> str:
    """
    Retrieves a git diff for the workspace.
    If branches are provided (e.g. 'main...feature'), compares branches.
    Otherwise, retrieves uncommitted local changes in the current workspace.
    """
    try:
        if branches:
            cmd = f"git -C {repository_path} diff {branches}"
        else:
            cmd = f"git -C {repository_path} diff"
            
        result = subprocess.run(cmd, shell=True, text=True, capture_output=True)
        
        if result.returncode != 0:
            return f"Error running git diff: {result.stderr.strip()}"
        if not result.stdout.strip():
            return "No modifications or changes detected."
            
        return result.stdout
    except Exception as e:
        return f"Error pulling workspace git delta profiles: {str(e)}"