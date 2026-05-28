import operator
from typing import List, Dict, Any, Literal, Annotated
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, SystemMessage
from core.logger import logger

# Import tools and schemas
from dto.code_editor_dto import EditorState
from workflow.code_editor.ask_node import ask_node
from workflow.code_editor.router_edge import mode_router_edge
from workflow.code_editor.plan_node import plan_node
from workflow.code_editor.agent_node import agent_node

workflow = StateGraph(EditorState)

# Define our processing building blocks
workflow.add_node("ask_node", ask_node)
workflow.add_node("plan_node", plan_node)
workflow.add_node("agent_node", agent_node)

# Map our Entry Point to evaluate the conditional router edge function
workflow.set_conditional_entry_point(
    mode_router_edge,
    {
        "ask_node": "ask_node",
        "plan_node": "plan_node",
        "agent_node": "agent_node"
    }
)

# Pipe all execution paths to a uniform termination point
workflow.add_edge("ask_node", END)
workflow.add_edge("plan_node", END)
workflow.add_edge("agent_node", END)

# Compile the final application graph object
code_editor_app = workflow.compile()
logger.info("Successfully compiled Multi-Mode AI Code Editor LangGraph engine.")