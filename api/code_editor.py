import json

from fastapi import APIRouter, Depends, HTTPException
from sse_starlette import EventSourceResponse

from core.logger import logger
from schemas.request import CodeEditorQueryParams
from workflow.code_editor.graph import code_editor_app

router = APIRouter()


@router.post("/edit-code")
async def edit_code(
    params: CodeEditorQueryParams = Depends(),
):
    """
    Invokes the multi-mode Autonomous Code Editor Agent.
    All inputs are accepted as query parameters.
    Streams real-time execution status updates and tool execution logs via SSE.
    """
    logger.info(f"code-editor endpoint hit")   
    workspace_raw = params.workspace_path.strip() if params.workspace_path else ""
    prompt_raw = params.user_prompt.strip() if params.user_prompt else ""
    mode_lower = params.mode.strip().lower() if params.mode else "ask"

    valid_modes = {"plan", "agent", "ask"}

    if mode_lower not in valid_modes:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid mode value '{params.mode}'. Supported options are: {list(valid_modes)}",
        )

    if not workspace_raw or not prompt_raw:
        raise HTTPException(
            status_code=400,
            detail="Missing required inputs. Both 'workspace_path' and 'user_prompt' must be supplied.",
        )
    
    workspace_raw = params.workspace_path.strip()
    if workspace_raw:
        workspace_raw = workspace_raw.replace("\\", "/")

    file_path = params.file_path.strip().replace("\\", "/") if params.file_path else None

    if file_path:
        if file_path.startswith(workspace_raw):
            file_path = file_path[len(workspace_raw):].lstrip("/")    
    logger.info(f"file_path after normalization: {file_path}")        

    initial_state = {
        "mode": mode_lower,
        "user_prompt": prompt_raw,
        "workspace_path": workspace_raw,
        "file_path": file_path,
        "current_plan": None,
        "tool_outputs": [],
        "final_response": {},
    }

    async def editor_event_generator():
        logger.info(f"Opening live SSE stream channel for Code Editor [Mode: {mode_lower}]...")
        final_output = {}

        try:
            async for event in code_editor_app.astream_events(initial_state, version="v2"):
                kind = event.get("event")
                node_name = event.get("name")

                # 1. Yield streaming node status updates
                if kind == "on_node_start":
                    if node_name == "ask_node":
                        yield {"event": "status", "data": "Routing the prompt through the ask node..."}
                    elif node_name == "plan_node":
                        yield {"event": "status", "data": "Compiling the execution plan..."}
                    elif node_name == "agent_node":
                        yield {"event": "status", "data": "Launching the agent workflow..."}
                
                # 2. Extract state mutations from ANY valid active node termination point
                elif kind == "on_node_end":
                    if "data" in event:
                        node_output = event["data"].get("output", {})
                        if isinstance(node_output, dict) and "final_response" in node_output:
                            # Only overwrite if it actually holds data (prevents subsequent empty nodes from cleaning it out)
                            if node_output["final_response"]:
                                final_output = node_output["final_response"]

            # 3. Last Line of Defense: Catch it on the complete chain resolution block if skipped
            if not final_output and kind == "on_chain_end":
                chain_output = event.get("data", {}).get("output", {})
                if isinstance(chain_output, dict) and "final_response" in chain_output:
                    final_output = chain_output["final_response"]

            # Fallback text if the output is completely blank
            if not final_output:
                final_output = {
                    "status": "failure",
                    "summary": "Execution finished but no valid structural final response was found in the graph state matrix."
                }

            yield {
                "event": "result",
                "data": json.dumps(final_output),
            }

        except Exception as err:
            logger.error(f"Editor pipeline streaming failure: {str(err)}", exc_info=True)
            yield {"event": "error", "data": json.dumps({"detail": f"Internal editor crash: {str(err)} "})}

    return EventSourceResponse(editor_event_generator())
