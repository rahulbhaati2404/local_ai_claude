from typing import Optional
from pydantic import BaseModel, Field
from pydantic import BaseModel
from typing import List, Optional
from typing import Optional
from pydantic import BaseModel, Field

class QueryRequest(BaseModel):
    query: str
    session_id: str

class PRReviewRequest(BaseModel):
    pr_url: Optional[str] = Field(
        default=None, 
        description="Direct URL to the GitHub pull request"
    )

class CodeEditorQueryParams(BaseModel):
    file_path: str = Field(
        default=None, 
        description="absolute path to the target file"
    )
    user_prompt: str = Field(
        default=None,
        description="The task instruction for the agent"
    )
    mode: str = Field(
        default="ask", 
        description="Execution strategy: 'plan', 'agent', or 'ask'"
    )


