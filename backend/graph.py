from pathlib import Path
import sys

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.utils.schema import SharedState
from backend.intent import extract_intent
from backend.validate_intent import validate_intent
from backend.retrive_context import retrieve_context
from backend.prompt_generator import generate_prompts
from backend.image import generate_image
from langgraph.graph import StateGraph, END
import json
from pydantic import BaseModel

graph = StateGraph(SharedState)

graph.add_node("extract_intent", extract_intent)
graph.add_node("retrieve_context", retrieve_context)
graph.add_node("generate_prompts", generate_prompts)
graph.add_node("generate_image", generate_image)

graph.set_entry_point("extract_intent")

graph.add_conditional_edges(
    "extract_intent",
    validate_intent,
    {
        True: "retrieve_context",
        False: "extract_intent"
    }
)

graph.add_edge("retrieve_context", "generate_prompts")
graph.add_edge("generate_prompts", "generate_image")
graph.add_edge("generate_image", END)

workflow = graph.compile()


def to_json_safe(value):
    if isinstance(value, BaseModel):
        return {key: to_json_safe(item) for key, item in value.model_dump().items()}
    if isinstance(value, dict):
        return {key: to_json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [to_json_safe(item) for item in value]
    return value


def run_workflow(raw_query: str) -> SharedState:
    initial_state = SharedState(raw_query=raw_query)
    final_state = workflow.invoke(initial_state)
    return final_state

raw_query = "Picture a moment from my last trip in Ghibli art, capture moments of laughter and fun."

if __name__ == "__main__":
    final_state = run_workflow(raw_query)
    with open("logs/final_state.json", "w") as f:
        json.dump(to_json_safe(final_state), f, indent=2)

