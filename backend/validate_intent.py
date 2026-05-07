import json

from backend.utils.schema import SharedState, ValidationSchema
from backend.utils.prompts import INTENT_VALIDATION_PROMPT
from backend.utils.config import gemini_model
from langchain.agents import create_agent

agent = create_agent(
    model=gemini_model,
    system_prompt=INTENT_VALIDATION_PROMPT,
    response_format=ValidationSchema
)

def validate_intent(state: SharedState) -> bool:
    if state.validate_intent.retries >= 3:
        return True
    payload = {
        "query": state.raw_query,
        "intent": state.intent.model_dump() if state.intent is not None else None,
    }
    response = agent.invoke({"messages": [{"role": "user", "content": json.dumps(payload)}]})
    parsed = ValidationSchema.model_validate(response["structured_response"])
    state.validate_intent.is_valid = parsed.is_valid
    state.validate_intent.retries += 1
    return parsed.is_valid