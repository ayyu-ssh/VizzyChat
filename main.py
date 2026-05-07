from backend.intent import extract_intent
from backend.retrive_context import retrieve_context
from backend.prompt_generator import generate_prompts
from backend.utils.schema import SharedState
import json 

raw_query = "Picture a moment from my last trip."

def main():
    state = SharedState(raw_query=raw_query)
    state = extract_intent(state)
    with open("logs/intent.json", "w") as f:
        json.dump(state.model_dump(), f, indent=2)
    state = retrieve_context(state, image_data_url="path/to/image.jpg")
    with open("logs/context.json", "w") as f:
        json.dump(state.model_dump(), f, indent=2)
    state = generate_prompts(state)
    with open("logs/prepared_prompts.json", "w") as f:
        json.dump(state.model_dump(), f, indent=2)
    
    return state

if __name__ == "__main__":
    main()
