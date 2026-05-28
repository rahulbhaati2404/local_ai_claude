
from pydantic import BaseModel
from typing import List, Optional
from typing import Optional
from pydantic import BaseModel, Field

class QueryRequest(BaseModel):
    query: str
    session_id: str



class PRReviewRequest(BaseModel):
    # Pass None explicitly as the default argument value
    repository_path: Optional[str] = Field(
        default=None, 
        description="The absolute path to the local git directory on your machine"
    )
    source_branch: Optional[str] = Field(
        default=None, 
        description="The branch containing the new engineering changes"
    )
    target_branch: Optional[str] = Field(
        default=None, 
        description="The base branch the changes are merging into"
    )
    pr_id: Optional[str] = Field(
        default=None, 
        description="The unique pull request identifier"
    )
    pr_url: Optional[str] = Field(
        default=None, 
        description="Direct URL to the GitHub pull request"
    )


from typing import Optional
from pydantic import BaseModel, Field

class CodeEditorQueryParams(BaseModel):
    workspace_path: str = Field(
        default=None, 
        description="Absolute path to the local repository directory"
    )
    user_prompt: str = Field(
        default=None,
        description="The task instruction for the agent"
    )
    mode: str = Field(
        default="ask", 
        description="Execution strategy: 'plan', 'agent', or 'ask'"
    )
    # Add this line here to handle optional file contexts safely
    file_path: Optional[str] = Field(
        default=None, 
        description="Optional relative path to a target file within the workspace"
    )
