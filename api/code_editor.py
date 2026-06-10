import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException
from sse_starlette import EventSourceResponse

from core.logger import logger
from schemas.request import CodeEditorQueryParams
from workflow.code_editor.graph import code_editor_app

code_editor_router = APIRouter()


@code_editor_router.api_route("/code-editor", methods=["GET"])
async def edit_code(
    params: CodeEditorQueryParams = Depends(),
):
    """
    Invokes the multi-mode Autonomous Code Editor Agent.
    Streams real-time execution status updates and tool execution logs via SSE.
    """

    prompt_raw = params.user_prompt.strip() if params.user_prompt else ""
    mode_lower = params.mode.strip().lower() if params.mode else "ask"

    valid_modes = {"plan", "agent", "ask"}

    if mode_lower not in valid_modes:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid mode value '{params.mode}'. Supported options are: {list(valid_modes)}",
        )
    
    file_path = params.file_path.strip().replace("\\", "/") if params.file_path else None

    if not params.file_path:
        raise HTTPException(
            status_code=400,
            detail="Missing required input: 'file_path' must be supplied.",
        )
 
    logger.info(f"file_path : {file_path}")        

    stream_queue: asyncio.Queue = asyncio.Queue()

    initial_state = {
        "mode": mode_lower,
        "user_prompt": prompt_raw,
        "file_path": file_path,
        "current_plan": None,
        "tool_outputs": [],
        "final_response": {},
        "stream_queue": stream_queue,
    }

    async def editor_event_generator():
        logger.info(f"Opening live SSE stream channel for Code Editor [Mode: {mode_lower}]...")
        final_state_holder: dict = {}

        async def run_editor_workflow() -> None:
            try:
                async for event in code_editor_app.astream_events(initial_state, version="v2"):
                    kind = event.get("event")
                    node_name = event.get("name")

                    if kind == "on_node_start":
                        if node_name == "ask_node":
                            await stream_queue.put(
                                {
                                    "event": "status",
                                    "data": "Routing the prompt through the ask node...",
                                }
                            )
                        elif node_name == "plan_node":
                            await stream_queue.put(
                                {
                                    "event": "status",
                                    "data": "Compiling the execution plan...",
                                }
                            )
                        elif node_name == "agent_node":
                            await stream_queue.put(
                                {
                                    "event": "status",
                                    "data": "Launching the agent workflow...",
                                }
                            )

                    elif kind == "on_node_end":
                        node_data = event.get("data", {})
                        node_output = node_data.get("output", {})

                        if (
                            isinstance(node_output, dict)
                            and node_output.get("final_response")
                        ):
                            final_state_holder["value"] = node_output["final_response"]

                    elif kind == "on_chain_end":
                        chain_output = event.get("data", {}).get("output", {})
                        if isinstance(chain_output, dict):
                            final_response = chain_output.get("final_response")
                            if final_response:
                                final_state_holder["value"] = final_response
                            elif chain_output:
                                final_state_holder["value"] = chain_output

                if "value" not in final_state_holder:
                    final_state_holder["value"] = {}

            except Exception as err:
                logger.error(f"Editor pipeline streaming failure: {str(err)}", exc_info=True)
                final_state_holder["error"] = str(err)
                await stream_queue.put(
                    {
                        "event": "error",
                        "data": json.dumps(
                            {"detail": f"Internal editor crash: {str(err)} "}
                        ),
                    }
                )
            finally:
                await stream_queue.put(None)

        asyncio.create_task(run_editor_workflow())

        yield {"event": "status", "data": "Connected. Streaming live output..."}

        while True:
            event = await stream_queue.get()
            if event is None:
                break
            yield event

        if final_state_holder.get("error"):
            return

        final_output = final_state_holder.get("value", {})

        if not final_output:
            final_output = {
                "status": "failure",
                "summary": "Execution finished but no valid structural final response was found in the graph state matrix.",
            }

        yield {
            "event": "result",
            "data": json.dumps(final_output),
        }

    return EventSourceResponse(editor_event_generator())
