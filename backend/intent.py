from pathlib import Path
import sys

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from langchain.agents import create_agent
from backend.utils.config import gemini_model
from backend.utils.prompts import INTENT_EXTRACTION_PROMPT
from backend.utils.schema import IntentSchema,SharedState


agent = create_agent(
    model=gemini_model,
    system_prompt=INTENT_EXTRACTION_PROMPT,
    response_format=IntentSchema
)

def extract_intent(state: SharedState) -> SharedState:
    # Implementation for extracting intent from shared state

    print ("ReAct loop execution count:", state.validate_intent.retries)
    query = state.raw_query
    response = agent.invoke({"messages": [{"role": "user", "content": query}]})
    state.intent = IntentSchema.model_validate(response["structured_response"])
    return state


# if __name__ == "__main__":
#     result = extract_intent(
#         SharedState(raw_query="I want to generate a serene landscape painting in the style of Monet.")
#     )
#     print(result.intent)