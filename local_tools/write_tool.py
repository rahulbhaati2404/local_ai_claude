import os
import subprocess
import time
from typing import Optional
from langchain_core.tools import tool
from core.logger import logger
import mcp



def write_file(file_path: str, content: str) -> str:
    """
    Writes or updates content to a specified file. 
    Validates syntax automatically for Python and JSON files before saving to prevent breaking code.
    """
    # 1. Pre-validation guardrails
    if file_path.endswith(".py"):
        try:
            compile(content, file_path, "exec")
        except SyntaxError as e:
            logger.error(f"[Tool: write_file] Python Syntax validation failed: {str(e)}")
            return f"Validation Error: Cannot write file. The provided code has a syntax error: {str(e)}"
            
    elif file_path.endswith(".json"):
        import json
        try:
            json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"[Tool: write_file] JSON validation failed: {str(e)}")
            return f"Validation Error: Cannot write file. Malformed JSON structure provided: {str(e)}"

    try:
        # Auto-create directories if they don't exist
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Success: File successfully updated and validated at {file_path}."
    except Exception as e:
        return f"Error writing to file path: {str(e)}"
