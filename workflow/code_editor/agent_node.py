import json
import re
from typing import Dict, Any, List

from core.logger import logger
from models.ollama_client import ollama_client

from dto.code_editor_dto import (
    EditorState,
    AgentNodeResponse
)

from context.token_counter import token_counter

from observability.metrics import metrics_collector
from observability.tracing import trace_manager

from mcp.client.stdio import stdio_client
from mcp import ClientSession

from mcp_tools.mcp_starter import MCP_SERVER_PARAMS

from core.config import settings

MODEL_NAME = settings.OLLAMA_DEFAULT_MODEL

MAX_AGENT_ITERATIONS = 50
MAX_REPEAT_THRESHOLD = 10


async def discover_tools(
    session: ClientSession
) -> str:

    try:

        discovered = await session.list_tools()

        return "\n".join([
            f"- {t.name}: {t.description}"
            for t in discovered.tools
        ])

    except Exception:

        logger.exception(
            "[Agent Node] Tool discovery failed"
        )

    return "No tools available."


def clean_json_response(
    response: str
) -> Dict[str, Any]:

    raw_text = response.strip()

    if raw_text.startswith("```"):
        raw_text = "\n".join(
            raw_text.split("\n")[1:]
        )

    if raw_text.endswith("```"):
        raw_text = raw_text.rsplit(
            "```",
            1
        )[0]

    raw_text = raw_text.strip()

    raw_text = re.sub(
        r'[\x00-\x1F\x7F]',
        ' ',
        raw_text
    )

    raw_text = re.sub(
        r'\\(?!["\\\/bfnrtu])',
        r'\\\\',
        raw_text
    )

    final_data = {
        "status": "failure",
        "summary": "",
        "modified_files": [],
        "execution_logs": "",
        "tool_calls": []
    }

    parsed = False

    try:

        loaded = json.loads(raw_text)

        if isinstance(loaded, dict):
            final_data.update(loaded)
            parsed = True

    except Exception:
        pass

    if not parsed:

        try:

            match = re.search(
                r'\{.*\}',
                raw_text,
                re.DOTALL
            )

            if match:

                loaded = json.loads(
                    match.group(0)
                )

                if isinstance(loaded, dict):
                    final_data.update(loaded)

        except Exception:
            pass

    if not final_data["summary"]:
        final_data["summary"] = raw_text

    return final_data


async def execute_tool_calls(
    session: ClientSession,
    tool_calls: List[Dict[str, Any]]
) -> str:

    logs = []

    for tool_call in tool_calls:

        try:

            tool_name = tool_call.get("tool")
            arguments = tool_call.get(
                "arguments",
                {}
            )

            logger.info(
                f"[Agent Node] Calling tool: "
                f"{tool_name}"
            )

            logger.info(
                f"[Agent Node] Tool arguments: "
                f"{arguments}"
            )

            result = await session.call_tool(
                tool_name,
                arguments=arguments
            )

            tool_output = ""

            if hasattr(result, "content"):

                tool_output = "\n".join([
                    getattr(c, "text", str(c))
                    for c in result.content
                ])

            else:
                tool_output = str(result)

            log_entry = f"""
TOOL: {tool_name}

ARGUMENTS:
{json.dumps(arguments, indent=2)}

RESULT:
{tool_output}
"""

            logs.append(log_entry)

            logger.info(
                f"[Agent Node] Tool executed: "
                f"{tool_name}"
            )

        except Exception as e:

            logger.exception(
                f"[Agent Node] Tool execution failed: "
                f"{tool_call}"
            )

            logs.append(
                f"""
TOOL ERROR:
{tool_call}

ERROR:
{str(e)}
"""
            )

    return "\n".join(logs)


async def run_single_iteration(
    state: EditorState,
    tool_manifest: str,
    session: ClientSession,
    iteration: int
) -> Dict[str, Any]:

    history = "\n".join(
        state.get("agent_history", [])
    )

    tool_results = "\n".join(
        state.get("tool_results", [])
    )

    system_prompt = f"""
Ignore all previous instructions.

You are an autonomous software engineering agent.

AVAILABLE TOOLS:
{tool_manifest}

Rules:
- do not hallucinate tool results
- do not fake file modifications
- do not assume execution succeeded
- use deterministic reasoning
- use tools whenever needed
- if more information is needed use tool_calls
- if task is incomplete return status=pending
- if task is complete return status=success
- if task cannot continue return status=failure

You may call tools using this schema:

{{
  "status": "pending",
  "summary": "need file contents",
  "modified_files": [],
  "execution_logs": "",
  "tool_calls": [
    {{
      "tool": "read_file",
      "arguments": {{
        "repository_path": "...",
        "file_path": "..."
      }}
    }}
  ]
}}

Final response schema:

{{
  "status": "success" | "failure" | "pending",
  "summary": "execution overview",
  "modified_files": ["path/file.py"],
  "execution_logs": "detailed logs",
  "tool_calls": []
}}

Return ONLY valid JSON.
"""

    user_prompt = f"""
WORKSPACE:
{state.get("workspace_path")}

TARGET FILE:
{state.get("file_path")}

TASK:
{state.get("user_prompt")}

CURRENT ITERATION:
{iteration}

PREVIOUS EXECUTION HISTORY:
{history}

PREVIOUS TOOL RESULTS:
{tool_results}
"""

    total_tokens = (
        token_counter.estimate_tokens(system_prompt)
        + token_counter.estimate_tokens(user_prompt)
    )

    metrics_collector.record(
        "agent_node_input_tokens",
        total_tokens
    )

    with trace_manager.trace(
        f"ollama_agent_iteration_{iteration}"
    ):

        response = await ollama_client.agenerate(
            prompt=f"{system_prompt}\n\n{user_prompt}",
            model=MODEL_NAME
        )

    metrics_collector.record(
        "agent_node_output_tokens",
        token_counter.estimate_tokens(response)
    )

    logger.info(
        f"[Agent Node] Raw model response:\n{response}"
    )

    cleaned = clean_json_response(response)

    tool_calls = cleaned.get(
        "tool_calls",
        []
    )

    if tool_calls:

        logger.info(
            f"[Agent Node] Executing "
            f"{len(tool_calls)} tool calls"
        )

        tool_logs = await execute_tool_calls(
            session=session,
            tool_calls=tool_calls
        )

        state.setdefault(
            "tool_results",
            []
        )

        state["tool_results"].append(
            tool_logs
        )

        cleaned["execution_logs"] += (
            f"\n\nTOOL EXECUTION LOGS:\n"
            f"{tool_logs}"
        )

        cleaned["status"] = "pending"

    validated = (
        AgentNodeResponse
        .model_validate_json(
            json.dumps(cleaned)
        )
    )

    return validated.model_dump()


async def agent_node(
    state: EditorState
) -> EditorState:

    with trace_manager.trace(
        "agent_node_total_execution"
    ):

        logger.info(
            "[Agent Node] Starting execution agent..."
        )

        state.setdefault(
            "agent_history",
            []
        )

        state.setdefault(
            "tool_results",
            []
        )

        state.setdefault(
            "iteration_count",
            0
        )

        final_response = {
            "status": "failure",
            "summary": "Agent execution failed",
            "modified_files": [],
            "execution_logs": "",
            "tool_calls": []
        }

        async with stdio_client(
            MCP_SERVER_PARAMS
        ) as (read_stream, write_stream):

            async with ClientSession(
                read_stream,
                write_stream
            ) as session:

                await session.initialize()

                logger.info(
                    "[Agent Node] MCP session initialized"
                )

                tool_manifest = await discover_tools(
                    session
                )

                logger.info(
                    f"[Agent Node] Available tools:\n"
                    f"{tool_manifest}"
                )

                previous_summary = ""
                repeat_counter = 0

                for iteration in range(
                    1,
                    MAX_AGENT_ITERATIONS + 1
                ):

                    logger.info(
                        f"[Agent Node] Iteration "
                        f"{iteration}"
                    )

                    state["iteration_count"] = iteration

                    try:

                        response = (
                            await run_single_iteration(
                                state=state,
                                tool_manifest=tool_manifest,
                                session=session,
                                iteration=iteration
                            )
                        )

                        current_summary = (
                            response.get("summary", "")
                            .strip()
                        )

                        state["agent_history"].append(
                            f"""
Iteration: {iteration}

Status:
{response.get("status")}

Summary:
{current_summary}

Execution Logs:
{response.get("execution_logs")}
"""
                        )

                        logger.info(
                            f"[Agent Node] Status: "
                            f"{response.get('status')}"
                        )

                        if (
                            current_summary
                            and current_summary
                            == previous_summary
                        ):

                            repeat_counter += 1

                            logger.warning(
                                "[Agent Node] Repeated "
                                f"response detected "
                                f"({repeat_counter})"
                            )

                        else:
                            repeat_counter = 0

                        previous_summary = current_summary

                        if (
                            repeat_counter
                            >= MAX_REPEAT_THRESHOLD
                        ):

                            logger.error(
                                "[Agent Node] Agent "
                                "stuck in loop"
                            )

                            final_response = {
                                "status": "failure",
                                "summary": (
                                    "Agent stuck in "
                                    "repeated loop"
                                ),
                                "modified_files": [],
                                "execution_logs": (
                                    "Repeated responses "
                                    "detected"
                                ),
                                "tool_calls": []
                            }

                            break

                        status = response.get("status")

                        final_response = response

                        if status == "success":

                            logger.info(
                                "[Agent Node] "
                                "Task completed"
                            )

                            break

                        if status == "failure":

                            logger.error(
                                "[Agent Node] "
                                "Task failed"
                            )

                            break

                        if status == "pending":

                            logger.info(
                                "[Agent Node] "
                                "Continuing execution..."
                            )

                            continue

                        logger.warning(
                            "[Agent Node] Unknown "
                            "status received"
                        )

                        break

                    except Exception:

                        logger.exception(
                            "[Agent Node] "
                            "Iteration failed"
                        )

                        final_response = {
                            "status": "failure",
                            "summary": (
                                f"Iteration {iteration} "
                                "failed"
                            ),
                            "modified_files": [],
                            "execution_logs": (
                                "Internal agent "
                                "execution error"
                            ),
                            "tool_calls": []
                        }

                        break

                else:

                    logger.warning(
                        "[Agent Node] Max "
                        "iterations reached"
                    )

                    final_response = {
                        "status": "failure",
                        "summary": (
                            "Max agent iterations "
                            "reached"
                        ),
                        "modified_files": [],
                        "execution_logs": (
                            "Agent could not "
                            "complete task"
                        ),
                        "tool_calls": []
                    }

        state["final_response"] = final_response

        logger.info(
            "[Agent Node] Execution completed"
        )

    return state

