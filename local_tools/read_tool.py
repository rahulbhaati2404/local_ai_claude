import os
from langchain_core.tools import tool
from core.logger import logger
import mcp

def read_file(repository_path: str, file_path: str) -> str:
    """Reads the full text content of a file."""
    # Build the absolute path safely
    full_path = os.path.join(repository_path, file_path)
    logger.info(
            f"[MCP read_file] repository_path={repository_path}"
        )

    logger.info(
        f"[MCP read_file] file_path={file_path}"
    )

    logger.info(
        f"[MCP read_file] full_path={full_path}"
    )
    
    try:
        with open(full_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        logger.error(f"Read failed: {e}")
        return f"Error: Could not read {full_path}. {str(e)}"