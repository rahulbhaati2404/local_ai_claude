from pydantic import BaseModel
from typing import Optional


class TokenUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    
class QueryResponse(BaseModel):
    query: str
    answer: str
    model_used: str
    tokens_used: TokenUsage
    latency_ms: float