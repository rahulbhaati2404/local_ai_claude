from typing import List, Optional, Dict, Any
from typing_extensions import TypedDict

class PRReviewState(TypedDict):
    repository_path: Optional[str]  # Optional now
    source_branch: Optional[str]     # Optional now
    target_branch: Optional[str]     # Optional now
    pr_id: Optional[str]
    pr_url: Optional[str]            
    
    raw_git_diff: str
    error_message: Optional[str]
    output: Dict[str, Any]