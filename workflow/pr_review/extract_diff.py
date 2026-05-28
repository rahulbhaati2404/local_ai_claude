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
    provided to fetch it via HTTP; otherwise, falls back to local git commands over MCP.
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

        repo_path = state.get("repository_path")
        source = state.get("source_branch")
        target = state.get("target_branch")

        logger.info(f"[Context Node] Missing PR Link. Falling back to local repo extraction: {repo_path}")

        if not repo_path or not os.path.exists(repo_path):
            error_msg = f"Repository directory path invalid or missing: {repo_path}"
            logger.error(error_msg)
            state["raw_git_diff"] = ""
            state["error_message"] = error_msg
            return state

        with trace_manager.trace("mcp_client_git_diff_tool"):
            try:
                branches_args = f"{target}...{source}"
                diff_output = ""
                
                logger.info(f"[Context Node] Requesting local branch diff via MCP git_diff for: {branches_args}")
                async with stdio_client(MCP_SERVER_PARAMS) as (read_stream, write_stream):
                    async with ClientSession(read_stream, write_stream) as session:
                        await session.initialize()
                        
                        mcp_response = await session.call_tool(
                            name="git_diff",
                            arguments={
                                "repository_path": repo_path,
                                "branches": branches_args
                            }
                        )
                        if mcp_response.content:
                            diff_output = mcp_response.content[0].text
                
                if "Error" in diff_output:
                    state["raw_git_diff"] = ""
                    state["error_message"] = diff_output
                elif "No local modifications" in diff_output or not diff_output.strip():
                    state["raw_git_diff"] = f"No code modifications found between branches {target} and {source}."
                    state["error_message"] = None
                else:
                    logger.info(f"Successfully extracted git diff ({len(diff_output)} characters) using MCP git_diff tool.")
                    state["raw_git_diff"] = diff_output
                    state["error_message"] = None

                local_diff_tokens = token_counter.estimate_tokens(state["raw_git_diff"])
                metrics_collector.record("local_diff_tokens", local_diff_tokens)
                logger.info(f"[Context Node] Extracted context payload size: {local_diff_tokens} tokens.")

            except Exception as e:
                error_msg = f"Unexpected system or protocol error during context extraction: {str(e)}"
                logger.error(f"Critical failure: {error_msg}", exc_info=True)
                state["raw_git_diff"] = ""
                state["error_message"] = error_msg

        return state