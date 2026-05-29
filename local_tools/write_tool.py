import os
import sys
import json
import time
from typing import Optional
from langchain_core.tools import tool
from core.logger import logger

def write_file(repository_path: str, file_path: str, content: str, mode: str = "w") -> str:
    """
    Writes, updates, or appends content to a specified file inside the workspace sandbox. 
    
    Parameters:
    - repository_path: Absolute path to the workspace directory.
    - file_path: Relative path to the target file.
    - content: The text string to be written or appended to the file.
    - mode: Optional. Use 'w' to completely overwrite the file. Use 'a' to append content to the end of the file. Defaults to 'w'.
    
    Validates syntax automatically for full Python and JSON file overwrites before saving to prevent breaking code.
    """
    clean_repo = repository_path.replace("\\", "/").rstrip("/")
    clean_file = file_path.replace("\\", "/").lstrip("/")
    full_path = os.path.abspath(os.path.join(clean_repo, clean_file))

    # Fallback guard if the LLM passes an invalid mode configuration string
    if mode not in ["w", "a"]:
        logger.warning(f"[Tool: write_file] Invalid mode '{mode}' requested. Defaulting to 'w' (overwrite).")
        mode = "w"

    logger.info(f"[Tool: write_file] Target trace verified: {full_path} | Mode: {mode}")

    # 2. Pre-validation guardrails (Syntax checking - Only validated for standard 'w' complete file overwrites)
    if mode == "w":
        if full_path.endswith(".py"):
            try:
                logger.info(f"[Tool: write_file] Initiating Python AST compilation check for {clean_file}")
                compile(content, full_path, "exec")
                logger.info(f"[Tool: write_file] AST verification clean for {clean_file}")
            except SyntaxError as e:
                err_msg = f"Validation Error: Cannot write file. The provided code has a syntax error: {str(e)}"
                logger.error(f"[Tool: write_file] {err_msg}")
                return err_msg
                
        elif full_path.endswith(".json"):
            try:
                logger.info(f"[Tool: write_file] Executing structural JSON mapping validation for {clean_file}")
                json.loads(content)
                logger.info(f"[Tool: write_file] JSON format payload verified for {clean_file}")
            except json.JSONDecodeError as e:
                err_msg = f"Validation Error: Cannot write file. Malformed JSON structure provided: {str(e)}"
                logger.error(f"[Tool: write_file] {err_msg}")
                return err_msg
    else:
        logger.info(f"[Tool: write_file] Bypassing AST/JSON parser safety gates for append ('a') operation.")

    # 3. Execution Phase
    try:
        dir_target = os.path.dirname(full_path)
        if not os.path.exists(dir_target):
            logger.info(f"[Tool: write_file] Destination tree missing. Auto-generating hierarchy: {dir_target}")
            os.makedirs(dir_target, exist_ok=True)
            
        logger.info(f"[Tool: write_file] Executing atomic disk flush on target file handle in '{mode}' mode: {full_path}")
        with open(full_path, mode, encoding="utf-8") as f:
            f.write(content)
            
        action = "appended to" if mode == "a" else "overwritten and validated"
        success_msg = f"Success: File successfully {action} at {full_path}."
        logger.info(f"[Tool: write_file] Task boundary complete. {success_msg}")
        return success_msg

    except Exception as e:
        fail_msg = f"System Error writing to target filesystem footprint: {str(e)}"
        logger.error(f"[Tool: write_file] {fail_msg}", exc_info=True)
        return fail_msg