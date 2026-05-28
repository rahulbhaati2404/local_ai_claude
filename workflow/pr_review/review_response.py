import os
import json
from datetime import datetime
from dto.review_dto import PRReviewState
from core.logger import logger

DATA_REVIEW_DIR = os.path.join(os.getcwd(), "data", "review")

async def structured_response_generator_node(state: PRReviewState) -> PRReviewState:
    """
    Extracts, validates the AI generated payload, and permanently 
    archives the code review down to a local log file inside ./data/review/
    """
    logger.info("[Output Node] Generating structured response and writing to data directory...")
    
    review_data = state.get("output", {})
    
    # Safely build the dynamic './data/review/' folder block path if it doesn't exist
    os.makedirs(DATA_REVIEW_DIR, exist_ok=True)
    
    # Formulate a unique file timestamp index
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    pr_identifier = state.get("pr_id") or "local_repo"
    log_filename = f"review_{pr_identifier}_{timestamp}.json"
    log_filepath = os.path.join(DATA_REVIEW_DIR, log_filename)
    
    log_payload = {
        "timestamp": datetime.now().isoformat(),
        "metadata": {
            "pr_url": state.get("pr_url"),
            "repository_path": state.get("repository_path"),
            "source_branch": state.get("source_branch"),
            "target_branch": state.get("target_branch"),
            "pr_id": state.get("pr_id")
        },
        "review_results": review_data
    }
    
    try:
        with open(log_filepath, "w", encoding="utf-8") as log_file:
            json.dump(log_payload, log_file, indent=2, ensure_ascii=False)
        
        logger.info(f"[Output Node] Review trace successfully archived to: {log_filepath}")
        
    except IOError as e:
        logger.error(f"[Output Node] Failed writing review logs to data disk: {str(e)}", exc_info=True)
        
    return state