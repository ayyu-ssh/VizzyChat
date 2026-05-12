from backend.utils.schema import SharedState, PromptSchema
from backend.utils.prompts import PROMPT_GENERATOR_PROMPT
from backend.utils.config import openai_model
from langchain.agents import create_agent
from pathlib import Path
import base64
import mimetypes
import json

agent = create_agent(
    model=openai_model,
    system_prompt=PROMPT_GENERATOR_PROMPT,
    response_format=PromptSchema
)


def _to_image_data_url(image_reference: str) -> str:
    if not image_reference:
        return image_reference
    if image_reference.startswith("data:image"):
        return image_reference

    image_path = Path(image_reference)
    if not image_path.exists() or not image_path.is_file():
        return image_reference

    mime_type, _ = mimetypes.guess_type(str(image_path))
    if not mime_type:
        mime_type = "application/octet-stream"

    encoded = base64.b64encode(image_path.read_bytes()).decode("utf-8")
    return f"data:{mime_type};base64,{encoded}"

def generate_prompts(state: SharedState) -> SharedState:
    # Implementation for generating prompts based on intent and context in shared state
    query = state.raw_query
    intent = state.intent
    context = state.context

    context_payload = None
    if context is not None:
        context_payload = context.model_dump()
        image_value = context_payload.get("image_data_url")
        if image_value:
            context_payload["image_data_url"] = _to_image_data_url(image_value)
        information = context_payload.get("user_info")
        if information:
            context_payload["user_info"] = information  

    payload = {
        "query": query,
        "intent": intent.model_dump() if intent is not None else None,
        "context": context_payload,
    }
    response = agent.invoke({"messages": [{"role": "user", "content": json.dumps(payload)}]})
    parsed = PromptSchema.model_validate(response["structured_response"])
    state.prepared_prompts = parsed.prompts
    return state