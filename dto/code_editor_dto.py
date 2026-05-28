from typing import List, TypedDict, Optional, Dict, Any
from typing import List, Literal
from pydantic import BaseModel, Field

class EditorState(TypedDict):
    # Inputs
    mode: str               # "plan" | "agent" | "ask"
    user_prompt: str        # The instruction (e.g., "Fix the bug in auth.py")
    workspace_path: str     # Path to the code repository
    file_path: str # Specific file for context (optional)
    
    current_plan: Optional[str]        # Holds the technical strategy if in plan mode
    tool_outputs: List[str]            # Log traces of executed tools
    final_response: Dict[str, Any]     # The final dictionary to return via API



# --- 1. Ask Mode Response Schema ---
class AskNodeResponse(BaseModel):
    """
    Structured response schema for direct Q&A interaction.
    """
    answer: str
    key_points: List[str]


# --- 2. Plan Mode Response Schema ---
class PlanStep(BaseModel):
    """
    Represents an isolated, distinct operational task block inside an architectural roadmap.
    """
    step_number: int
    description: str 
    expected_outcome: str

class PlanNodeResponse(BaseModel):
    """
    Structured response schema for codebase analysis and strategy blueprinting.
    """
    estimated_complexity: Literal["Low", "Medium", "High"]
    summary: str 
    steps: List[PlanStep]

# --- 3. Agent Mode Response Schema ---
class AgentNodeResponse(BaseModel):
    """
    Structured response schema for the autonomous modification matrix execution output.
    """
    status: Literal["success", "failure","pending"]
    summary: str 
    modified_files: List[str] 
    execution_logs: str 
    next_step: Optional[str] = None