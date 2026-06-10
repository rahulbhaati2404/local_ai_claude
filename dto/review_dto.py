from typing import Any, Dict, Optional
from typing_extensions import TypedDict


class PRReviewState(TypedDict, total=False):
    pr_id: Optional[str]
    pr_url: Optional[str]
    raw_git_diff: str
    error_message: Optional[str]
    output: Dict[str, Any]
    stream_queue: Any
