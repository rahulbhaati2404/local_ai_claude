import json
import re

from core.logger import logger
from models.ollama_client import ollama_client

from dto.code_editor_dto import (
    EditorState,
    PlanNodeResponse
)

from context.token_counter import token_counter

from observability.metrics import metrics_collector
from observability.tracing import trace_manager

from mcp.client.stdio import stdio_client
from mcp import ClientSession

from mcp_tools.mcp_starter import MCP_SERVER_PARAMS

from core.config import settings

MODEL_NAME = settings.OLLAMA_DEFAULT_MODEL


async def fetch_file_context(
    workspace: str,
    target_file: str
) -> str:

    if not workspace or not target_file:
        return ""

    try:

        async with stdio_client(
            MCP_SERVER_PARAMS
        ) as (read_stream, write_stream):

            async with ClientSession(
                read_stream,
                write_stream
            ) as session:

                await session.initialize()

                response = await session.call_tool(
                    name="read_file",
                    arguments={
                        "repository_path": workspace,
                        "file_path": target_file
                    }
                )

                extracted_text = ""

                if (
                    response
                    and hasattr(response, "content")
                    and response.content
                ):

                    for item in response.content:

                        if hasattr(item, "text"):
                            extracted_text += item.text + "\n"

                        elif isinstance(item, dict):

                            if "text" in item:
                                extracted_text += (
                                    str(item["text"]) + "\n"
                                )

                return extracted_text.strip()

    except Exception as e:

        logger.exception(
            "[Plan Node] MCP read_file failed"
        )

    return ""


async def plan_node(
    state: EditorState
) -> EditorState:

    with trace_manager.trace(
        "plan_node_total_execution"
    ):

        logger.info(
            "[Plan Node] Building execution roadmap..."
        )

        workspace = state.get(
            "workspace_path",
            ""
        )

        target_file = state.get(
            "file_path"
        )

        file_context = ""

        if target_file:

            file_context = await fetch_file_context(
                workspace,
                target_file
            )

        system_prompt = """
Ignore all previous instructions.

You are a principal software architect.

Your task:
- analyze code carefully
- create deterministic implementation plans
- avoid hallucinations
- do not invent files/functions/classes
- use ONLY provided context

Return ONLY valid JSON.

Required schema:

{
  "estimated_complexity": "Low" | "Medium" | "High",
  "summary": "technical overview",
  "steps": [
    {
      "step_number": 1,
      "description": "implementation action",
      "expected_outcome": "validation result"
    }
  ]
}
"""

        user_prompt = f"""
WORKSPACE:
{workspace}

TARGET FILE:
{target_file}

FILE CONTEXT:
{file_context}

USER OBJECTIVE:
{state["user_prompt"]}
"""

        total_tokens = (
            token_counter.estimate_tokens(system_prompt)
            + token_counter.estimate_tokens(user_prompt)
        )

        metrics_collector.record(
            "plan_node_input_tokens",
            total_tokens
        )

        with trace_manager.trace(
            "ollama_plan_inference"
        ):

            response = await ollama_client.agenerate(
                prompt=f"{system_prompt}\n\n{user_prompt}",
                model=MODEL_NAME
            )

        metrics_collector.record(
            "plan_node_output_tokens",
            token_counter.estimate_tokens(response)
        )

        try:

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
                "estimated_complexity": "Medium",
                "summary": "",
                "steps": []
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

                        extracted = match.group(0)

                        loaded = json.loads(extracted)

                        if isinstance(loaded, dict):
                            final_data.update(loaded)

                except Exception:
                    pass

            if not final_data["summary"]:
                final_data["summary"] = raw_text

            if not final_data["steps"]:

                final_data["steps"] = [
                    {
                        "step_number": 1,
                        "description": "Analyze response manually",
                        "expected_outcome": "Fallback recovery"
                    }
                ]

            validated = (
                PlanNodeResponse
                .model_validate_json(
                    json.dumps(final_data)
                )
            )

            state["current_plan"] = (
                validated.steps
            )

            state["final_response"] = (
                validated.model_dump()
            )

        except Exception as e:

            logger.exception(
                "[Plan Node] Validation failed"
            )

            state["final_response"] = {
                "estimated_complexity": "High",
                "summary": response,
                "steps": []
            }

    return state