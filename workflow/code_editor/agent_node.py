import json
import re

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


async def discover_tools() -> str:

    try:

        async with stdio_client(
            MCP_SERVER_PARAMS
        ) as (read_stream, write_stream):

            async with ClientSession(
                read_stream,
                write_stream
            ) as session:

                await session.initialize()

                discovered = (
                    await session.list_tools()
                )

                return "\n".join([
                    f"- {t.name}: {t.description}"
                    for t in discovered.tools
                ])

    except Exception:

        logger.exception(
            "[Agent Node] Tool discovery failed"
        )

    return "No tools available."


async def agent_node(
    state: EditorState
) -> EditorState:

    with trace_manager.trace(
        "agent_node_total_execution"
    ):

        logger.info(
            "[Agent Node] Starting execution agent..."
        )

        tool_manifest = await discover_tools()

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

Return ONLY valid JSON.

Schema:

{{
  "status": "success" | "failure",
  "summary": "execution overview",
  "modified_files": ["path/file.py"],
  "execution_logs": "detailed logs"
}}
"""

        user_prompt = f"""
WORKSPACE:
{state.get("workspace_path")}

TARGET FILE:
{state.get("file_path")}

TASK:
{state.get("user_prompt")}
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
            "ollama_agent_inference"
        ):

            response = await ollama_client.agenerate(
                prompt=f"{system_prompt}\n\n{user_prompt}",
                model=MODEL_NAME
            )

        metrics_collector.record(
            "agent_node_output_tokens",
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
                "status": "failure",
                "summary": "",
                "modified_files": [],
                "execution_logs": ""
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

            validated = (
                AgentNodeResponse
                .model_validate_json(
                    json.dumps(final_data)
                )
            )

            state["final_response"] = (
                validated.model_dump()
            )

        except Exception:

            logger.exception(
                "[Agent Node] Validation failed"
            )

            state["final_response"] = {
                "status": "failure",
                "summary": response,
                "modified_files": [],
                "execution_logs": "validation failure"
            }

    return state