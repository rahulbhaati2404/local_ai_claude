from typing import Literal
from core.logger import logger

from dto.code_editor_dto import EditorState


def mode_router_edge(state: EditorState) -> Literal["ask_node", "plan_node", "agent_node"]:
    """
    Inspects the state mode provided by the API layer and 
    branches the execution pipeline into the corresponding operational track.
    """
    mode = state.get("mode", "ask").strip().lower()
    logger.info(f"[Graph Router] Directing execution down the branch path for mode: '{mode}'")
    
    if mode == "ask":
        return "ask_node"
    elif mode == "agent":
        return "agent_node"
    elif mode == "plan":
        return "plan_node"
    else:
        logger.warning(f"[Graph Router] Unknown mode '{mode}' encountered. Falling back to 'ask_node'.")
        return "ask_node"