import httpx
import json
from dto.review_dto import PRReviewState
from core.logger import logger
from models.ollama_client import ollama_client
from core.config import settings
import json
import re
from dto.review_dto import PRReviewState
from core.logger import logger


MODEL_NAME = settings.OLLAMA_DEFAULT_MODEL
MAX_SAFE_DIFF_LENGTH = 8000  # Threshold character count for a "large" PR

def chunk_diff_by_files(raw_diff: str) -> list:
    """Helper utility to segment one massive diff patch into clear individual file strings."""
    chunks = []
    current_chunk = []
    
    for line in raw_diff.splitlines():
        if line.startswith("diff --git") and current_chunk:
            chunks.append("\n".join(current_chunk))
            current_chunk = []
        current_chunk.append(line)
        
    if current_chunk:
        chunks.append("\n".join(current_chunk))
    return chunks

async def planner_agent_node(state: PRReviewState) -> PRReviewState:
    """
    Step 2 Graph Node: High-performance code reviewer.
    Dynamically splits large diff chunks to bypass local context window degradation.
    """
    raw_diff = state.get("raw_git_diff", "")
    
    if not raw_diff.strip() or "No code modifications found" in raw_diff:
        state["output"] = {"summary": "No changes to analyze.", "issues": []}
        return state

    system_prompt = (
        "You are an expert Senior Code Reviewer. Analyze the provided git diff chunk.\n"
        "Identify critical bugs, performance issues, or security flaws.\n"
        "Output your findings strictly as a JSON object matching this schema:\n"
        "{\n"
        '  "summary": "High-level summary of this chunk",\n'
        '  "issues": [\n'
        '    {"file": "filename.py", "line": 10, "severity": "WARNING", "description": "msg", "recommendation": "fix"}\n'
        '  ]\n'
        "}\n"
        "Do not output markdown code fences. Output raw JSON only."
    )

    compiled_issues = []
    summaries = []

    # Check if we need to chunk the files due to massive PR length
    if len(raw_diff) > MAX_SAFE_DIFF_LENGTH:
        logger.warning(f"[Review Agent] Massive PR detected ({len(raw_diff)} chars). Executing dynamic map-reduce processing...")
        diff_blocks = chunk_diff_by_files(raw_diff)
    else:
        diff_blocks = [raw_diff]

    for idx, block in enumerate(diff_blocks):
        logger.info(f"[Review Agent] Processing diff segment {idx + 1}/{len(diff_blocks)}")
        
        user_prompt = f"### GIT DIFF CHUNK TO REVIEW:\n{block}"
        full_prompt = f"{system_prompt}\n\nUser Input:\n{user_prompt}"
        logger.info(f"[Review Agent] Prompt tokens for segment {idx + 1}: {len(full_prompt) // 4} (approx.)")

        try:
            raw_response = await ollama_client.agenerate(prompt=full_prompt, model=MODEL_NAME)
            
            # Clean response text and strip code blocks if model added them mistakenly
            cleaned = re.sub(r"```json|```", "", raw_response).strip()
            parsed_chunk = json.loads(cleaned)
            
            if "issues" in parsed_chunk and isinstance(parsed_chunk["issues"], list):
                compiled_issues.extend(parsed_chunk["issues"])
            if "summary" in parsed_chunk:
                summaries.append(parsed_chunk["summary"])
                
        except Exception as e:
            logger.error(f"[Review Agent] Error analyzing segment {idx + 1}: {str(e)}")
            continue

    # Consolidate our fragmented runs back into a single unified output report
    state["output"] = {
        "summary": " | ".join(summaries) if summaries else "Review completed across chunks.",
        "issues": compiled_issues
    }
    
    return state