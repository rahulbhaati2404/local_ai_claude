import os
import httpx
import json
from core.logger import logger
from dto.review_dto import PRReviewState

from context.token_counter import token_counter
from observability.metrics import metrics_collector
from observability.tracing import trace_manager  

from mcp.client.stdio import stdio_client
from mcp import ClientSession
from mcp_tools.mcp_starter import MCP_SERVER_PARAMS

async def extract_context_node(state: PRReviewState) -> PRReviewState:
    """
    Extracts the git diff. Automatically checks if a GitHub PR URL is 
    provided to fetch it via HTTP;
    """
    
    with trace_manager.trace("extract_context_total_execution"):
        pr_url = state.get("pr_url")

        if pr_url and pr_url.strip():
            logger.info(f"[Context Node] GitHub PR link provided: {pr_url}. Fetching remote diff...")
        
            target_url = pr_url.strip()
            if not target_url.endswith(".diff"):
                target_url += ".diff"

            with trace_manager.trace("http_remote_diff_fetch"):
                try:
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        response = await client.get(target_url, follow_redirects=True)                
                        if response.status_code != 200:
                            error_msg = f"Failed to fetch PR diff from GitHub. HTTP Status: {response.status_code}"
                            logger.error(error_msg)
                            state["raw_git_diff"] = ""
                            state["error_message"] = error_msg
                            return state
                        
                        diff_output = response.text
                        if not diff_output.strip():
                            state["raw_git_diff"] = "The remote GitHub PR diff is empty."
                        else:
                            logger.info(f"Successfully downloaded remote diff ({len(diff_output)} characters).")
                            state["raw_git_diff"] = diff_output
                        
                        diff_tokens = token_counter.estimate_tokens(state["raw_git_diff"])
                        metrics_collector.record("remote_diff_tokens", diff_tokens)
                        
                        state["error_message"] = None
                        return state

                except Exception as e:
                    error_msg = f"Network error fetching remote PR: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    state["raw_git_diff"] = ""
                    state["error_message"] = error_msg
                    return state

        return state