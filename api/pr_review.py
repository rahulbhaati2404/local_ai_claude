import asyncio
import json

from fastapi import APIRouter, HTTPException
from sse_starlette import EventSourceResponse

from core.logger import logger
from dto.review_dto import PRReviewState
from workflow.pr_review.graph import pr_review_app

pr_review_router = APIRouter()


@pr_review_router.api_route("/review-pr", methods=["GET"])
async def review_pr(pr_url: str):
    """
    Invokes the local AI DevOps Agent workflow and streams intermediate execution
    progress and final structured review notes back to the client in real-time (SSE).
    """
    has_url = pr_url and pr_url.strip()

    logger.info(f"pr_url: {pr_url}")
    
    if not has_url :
        raise HTTPException(
            status_code=400,
            detail="Invalid request. Provide either 'pr_url' OR local repository configurations.",
        )
    
    extracted_pr_id = None

    if has_url:
        try:
            url_parts = pr_url.strip().rstrip("/").split("/")
            if url_parts[-1].isdigit():
                extracted_pr_id = f"pr_{url_parts[-1]}"
        except Exception:
            pass

    logger.info(f"Extracted PR ID: {extracted_pr_id}")

    initial_state: PRReviewState = {
        "pr_url": pr_url.strip() if pr_url else None,
        "pr_id": extracted_pr_id,
        "raw_git_diff": "",
        "error_message": None,
        "output": {},
    }

    logger.info(f"Initial PR Review State: {initial_state}")

    stream_queue: asyncio.Queue = asyncio.Queue()
    initial_state["stream_queue"] = stream_queue

    final_state_holder: dict = {}

    async def run_review_workflow() -> None:
        try:
            final_state_holder["value"] = await pr_review_app.ainvoke(initial_state)
        except Exception as err:
            logger.error(f"[PR Review] Workflow failure: {str(err)}", exc_info=True)
            final_state_holder["error"] = str(err)
            await stream_queue.put(
                {
                    "event": "error",
                    "data": json.dumps(
                        {"detail": f"Internal review crash: {str(err)}"}
                    ),
                }
            )
        finally:
            await stream_queue.put(None)

    asyncio.create_task(run_review_workflow())

    async def review_event_generator():
        yield {"event": "status", "data": "Connected. Streaming live output..."}

        while True:
            event = await stream_queue.get()
            if event is None:
                break
            yield event

        if final_state_holder.get("error"):
            return

        final_state = final_state_holder.get("value", {})
        output = final_state.get("output", {}) if isinstance(final_state, dict) else {}

        if not output:
            output = {
                "status": "failure",
                "summary": "Execution finished but no valid structural final response was found in the graph state matrix.",
            }

        yield {
            "event": "result",
            "data": json.dumps(output),
        }

    return EventSourceResponse(review_event_generator())
