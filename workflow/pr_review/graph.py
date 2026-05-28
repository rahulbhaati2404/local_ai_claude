from langgraph.graph import StateGraph, END
from dto.review_dto import PRReviewState
from workflow.pr_review.extract_diff import extract_context_node 
from workflow.pr_review.code_reviewer import planner_agent_node
from workflow.pr_review.review_response import structured_response_generator_node

workflow = StateGraph(PRReviewState)

workflow.add_node("extract_context", extract_context_node)
workflow.add_node("planner_agent", planner_agent_node)
workflow.add_node("structured_generator", structured_response_generator_node)

workflow.set_entry_point("extract_context")

workflow.add_edge("extract_context", "planner_agent")      # Move to LLM Analysis
workflow.add_edge("planner_agent", "structured_generator")  # Move to Output Formatting & Storage
workflow.add_edge("structured_generator", END)

# Compile
pr_review_app = workflow.compile()