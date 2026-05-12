from pathlib import Path
import sys

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.utils.schema import SharedState
from backend.intent import extract_intent
from backend.validate_intent import validate_intent
from backend.retrive_context import retrieve_context
from backend.prompt_generator import generate_prompts
from backend.image import generate_image, refine_prompt_with_feedback
from langgraph.graph import StateGraph, END
import json
from pydantic import BaseModel

graph = StateGraph(SharedState)

graph.add_node("extract_intent", extract_intent)
graph.add_node("retrieve_context", retrieve_context)
graph.add_node("generate_prompts", generate_prompts)
graph.add_node("generate_image", generate_image)
graph.add_node("refine_prompt", refine_prompt_with_feedback)

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


def should_regenerate(state: SharedState) -> str:
    """
    Conditional router after generate_image.
    Routes to refine_prompt if regeneration is needed, otherwise to END.
    """
    if state.should_regenerate:
        regeneration_history = state.regeneration_history
        if regeneration_history and regeneration_history.regeneration_count < regeneration_history.max_regenerations:
            return "refine_prompt"
    return "end"


graph.add_conditional_edges(
    "generate_image",
    should_regenerate,
    {
        "refine_prompt": "refine_prompt",
        "end": END
    }
)

graph.add_edge("refine_prompt", "generate_image")

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

