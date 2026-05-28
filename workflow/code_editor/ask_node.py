import json
import re
import os
from core.logger import logger
from models.ollama_client import ollama_client
from dto.code_editor_dto import EditorState, AskNodeResponse

# Observability and context tracking imports
from context.token_counter import token_counter
from observability.metrics import metrics_collector
from observability.tracing import trace_manager

# MCP Client Core Utilities
from mcp.client.stdio import stdio_client
from mcp import ClientSession
from mcp_tools.mcp_starter import MCP_SERVER_PARAMS

from core.config import settings

MODEL_NAME = settings.OLLAMA_DEFAULT_MODEL

MAX_CONTEXT_CHARS = 12000

POISON_PATTERNS = [
    "Traceback (most recent call last)",
    "ExceptionGroup",
    "TaskGroup",
    "RuntimeError:",
    "SyntaxError:",
    "ModuleNotFoundError",
    "ImportError",
    "ConnectionError",
]


def sanitize_context(text: str) -> str:
    """
    Clean noisy or dangerous context before sending to the LLM.
    """

    if not text:
        return ""

    # Remove ANSI escape characters
    text = re.sub(r'\x1B[@-_][0-?]*[ -/]*[@-~]', '', text)

    # Remove null/control characters
    text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)

    # Remove traceback blocks
    text = re.sub(
        r"Traceback \(most recent call last\):.*",
        "",
        text,
        flags=re.DOTALL
    )

    # Collapse excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def contains_poison_patterns(text: str) -> bool:
    """
    Detect dangerous error context contamination.
    """

    if not text:
        return False

    for pattern in POISON_PATTERNS:
        if pattern.lower() in text.lower():
            return True

    return False


def build_system_prompt() -> str:
    """
    Strong stateless instruction hierarchy.
    """

    return """
You are a stateless senior software engineering assistant.

RULES:
- Treat every request as fully isolated.
- Ignore previous conversations.
- Never continue old reasoning chains.
- Never hallucinate APIs, functions, classes, or libraries.
- Never invent code behavior.
- If context is incomplete, explicitly say so.
- Prefer correctness over completeness.
- Provide production-grade technical responses.
- Be concise and direct.
- Do not explain infrastructure/internal failures unless explicitly requested.
- Never generate markdown code fences.
- Return ONLY valid JSON.

OUTPUT SCHEMA:
{
  "answer": "string",
  "key_points": ["string"]
}
""".strip()


def build_user_prompt(
    workspace: str,
    target_file: str,
    file_context: str,
    user_request: str
) -> str:
    """
    Structured prompt boundaries to avoid context blending.
    """

    return f"""
<TASK>
{user_request}
</TASK>

<WORKSPACE>
{workspace}
</WORKSPACE>

<TARGET_FILE>
{target_file if target_file else "NOT_PROVIDED"}
</TARGET_FILE>

<FILE_CONTEXT>
{file_context if file_context else "NO_FILE_CONTEXT_AVAILABLE"}
</FILE_CONTEXT>

IMPORTANT:
- Use ONLY the provided context.
- Do not assume hidden files exist.
- Do not invent missing implementations.
- Return valid JSON only.
""".strip()


async def fetch_file_context(workspace: str, target_file: str) -> str:
    """
    Retrieve file contents safely via MCP.
    """

    if not workspace or not target_file:
        logger.warning("[Ask Node] Missing workspace or target_file")
        return ""

    try:
        clean_workspace = (
            str(workspace)
            .replace("\\", "/")
            .rstrip("/")
            .strip()
        )

        clean_file = (
            str(target_file)
            .replace("\\", "/")
            .lstrip("/")
            .strip()
        )

        logger.info(
            f"[Ask Node] MCP read request | "
            f"workspace={clean_workspace} | "
            f"file={clean_file}"
        )

        async with stdio_client(MCP_SERVER_PARAMS) as (
            read_stream,
            write_stream
        ):

            async with ClientSession(
                read_stream,
                write_stream
            ) as session:

                await session.initialize()

                logger.info(
                    "[Ask Node] MCP session initialized"
                )

                mcp_response = await session.call_tool(
                    name="read_file",
                    arguments={
                        "repository_path": clean_workspace,
                        "file_path": clean_file
                    }
                )

                logger.info(
                    f"[Ask Node] Raw MCP response type: "
                    f"{type(mcp_response)}"
                )

                if not mcp_response:
                    logger.warning(
                        "[Ask Node] Empty MCP response"
                    )
                    return ""

                logger.info(
                    f"[Ask Node] MCP response: {repr(mcp_response)}"
                )

                extracted_text = ""
                if hasattr(mcp_response, "content"):

                    content_items = mcp_response.content

                    if content_items:

                        for item in content_items:

                            # TextContent object
                            if hasattr(item, "text"):

                                extracted_text += (
                                    item.text + "\n"
                                )

                            # dict response
                            elif isinstance(item, dict):

                                if "text" in item:
                                    extracted_text += (
                                        str(item["text"]) + "\n"
                                    )

                                elif "content" in item:
                                    extracted_text += (
                                        str(item["content"]) + "\n"
                                    )

                            else:
                                extracted_text += (
                                    str(item) + "\n"
                                )

                # CASE 2:
                # Direct string response
                elif isinstance(mcp_response, str):

                    extracted_text = mcp_response

                # CASE 3:
                # Dict response
                elif isinstance(mcp_response, dict):

                    extracted_text = (
                        mcp_response.get("text")
                        or mcp_response.get("content")
                        or json.dumps(mcp_response)
                    )


                extracted_text = extracted_text.strip()

                logger.info(
                    f"[Ask Node] Extracted "
                    f"{len(extracted_text)} chars"
                )

                if not extracted_text:
                    logger.warning(
                        "[Ask Node] No extractable text found"
                    )
                    return ""

                return extracted_text

    except Exception as e:

        logger.exception(
            "[Ask Node] MCP file read failed"
        )

        return ""


def clean_json_response(raw_response: str) -> str:
    """
    Clean model output before validation.
    """

    if not raw_response:
        return ""

    raw_response = raw_response.strip()

    # Remove markdown fences
    raw_response = re.sub(r"^```(?:json)?", "", raw_response)
    raw_response = re.sub(r"```$", "", raw_response)

    raw_response = raw_response.strip()
    logger.info(
        f"[Ask Node] Cleaned response length: {raw_response}"
    )
    return raw_response



async def ask_node(state: EditorState) -> EditorState:

    """
    Stateless Ask Node with:
    - Context sanitization
    - Poison detection
    - Deterministic prompting
    - Strict schema validation
    """

    with trace_manager.trace("ask_node_total_execution"):

        logger.info("[Ask Node] Processing technical request")

        workspace = state.get("workspace_path", "")
        target_file = state.get("file_path", "")
        user_request = state.get("user_prompt", "")


        file_context = ""

        if target_file:

            with trace_manager.trace("mcp_fetch_file_context"):

                file_context = await fetch_file_context(
                    workspace=workspace,
                    target_file=target_file
                )


        file_context = sanitize_context(file_context)

        if contains_poison_patterns(file_context):

            logger.warning(
                "[Ask Node] Poison patterns detected in context. "
                "Dropping file context."
            )

            file_context = ""


        if len(file_context) > MAX_CONTEXT_CHARS:

            logger.warning(
                f"[Ask Node] Truncating oversized context "
                f"from {len(file_context)} chars "
                f"to {MAX_CONTEXT_CHARS}"
            )

            file_context = file_context[:MAX_CONTEXT_CHARS]

        system_prompt = build_system_prompt()

        user_prompt = build_user_prompt(
            workspace=workspace,
            target_file=target_file,
            file_context=file_context,
            user_request=user_request
        )

        system_tokens = token_counter.estimate_tokens(system_prompt)
        user_tokens = token_counter.estimate_tokens(user_prompt)

        total_input_tokens = system_tokens + user_tokens

        metrics_collector.record(
            "ask_node_input_tokens",
            total_input_tokens
        )

        logger.info(
            f"[Ask Node] "
            f"system_tokens={system_tokens}, "
            f"user_tokens={user_tokens}, "
            f"total={total_input_tokens}"
        )


        with trace_manager.trace("ollama_llm_inference"):

            response = await ollama_client.agenerate(
                model=MODEL_NAME,
                prompt=f"""
<SYSTEM>
{system_prompt}
</SYSTEM>

<USER>
{user_prompt}
</USER>
""",
                
            )

        response_tokens = token_counter.estimate_tokens(response)

        metrics_collector.record(
            "ask_node_output_tokens",
            response_tokens
        )

        logger.info(
            f"[Ask Node] output_tokens={response_tokens}"
        )

        cleaned_response = clean_json_response(response)

        try:

            validated_response = (
                AskNodeResponse.model_validate_json(cleaned_response)
            )

            state["final_response"] = (
                validated_response.model_dump()
            )

            logger.info(
                "[Ask Node] Response validation successful"
            )

        except Exception as validation_error:

            logger.error(
                f"[Ask Node] Response validation failed: "
                f"{str(validation_error)}"
            )

            fallback_answer = cleaned_response

            # Attempt fallback extraction
            try:

                parsed = json.loads(cleaned_response)

                if isinstance(parsed, dict):

                    fallback_answer = parsed.get(
                        "answer",
                        cleaned_response
                    )

            except Exception:
                pass

            state["final_response"] = {
                "answer": fallback_answer,
                "key_points": [
                    "Model response failed strict schema validation."
                ],
                "parsing_error_trace": str(validation_error)
            }

    return state

