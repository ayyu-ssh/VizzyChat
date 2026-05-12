import requests
from backend.utils.schema import SharedState, PromptSchema, RegenerationHistory, FeedbackRequest
from dotenv import load_dotenv
import os
from pathlib import Path
import uuid
import json
from langchain.agents import create_agent
from backend.utils.config import openai_model
from backend.utils.prompts import PROMPT_REFINEMENT_PROMPT
load_dotenv()

CLOUDFLARE_API_KEY = os.getenv("CLOUDFLARE_API_KEY")
CLOUDFLARE_WORKER_URL = os.getenv("CLOUDFLARE_WORKER_URL")
IMAGES_DIR = Path(__file__).resolve().parents[1] / "images"


def _image_extension(content_type: str, response_content: bytes) -> str:
    if content_type.startswith("image/"):
        subtype = content_type.split("/", 1)[1].split(";", 1)[0].strip().lower()
        if subtype in {"jpeg", "jpg"}:
            return ".jpg"
        if subtype in {"png", "gif", "webp", "bmp", "tiff"}:
            return f".{subtype}"

    if response_content.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if response_content.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if response_content.startswith((b"GIF87a", b"GIF89a")):
        return ".gif"

    return ".img"

def generate_image(state: SharedState) -> SharedState:

    if state.prepared_prompts.prompts is None:
        raise ValueError("Error accessing prepared prompts:")

    prompt = state.prepared_prompts.prompts

    url = CLOUDFLARE_WORKER_URL

    headers = {
        "Authorization": f"Bearer {CLOUDFLARE_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "prompt": prompt
    }

    response = requests.post(url, headers=headers, json=payload)

    print(response.status_code)
    content_type = response.headers.get("content-type", "")
    is_image = content_type.startswith("image/") or response.content.startswith((b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n", b"GIF87a", b"GIF89a"))
    is_html = content_type.startswith("text/html") or "html" in content_type

    print(content_type)
    print(response.text[:200])

    if response.ok:
        print(f"Request successful: {response.status_code}")
        print(f"Response content type: {content_type}")
        print(f"Response bytes: {len(response.content)}")

    print(f"Response contains image: {'yes' if is_image else 'no'}")
    print(f"Response contains html: {'yes' if is_html else 'no'}")

    image_path = None

    if is_image:
        IMAGES_DIR.mkdir(parents=True, exist_ok=True)
        image_filename = f"generated_{uuid.uuid4().hex}{_image_extension(content_type, response.content)}"
        image_path = IMAGES_DIR / image_filename

        with open(image_path, "wb") as f:
            f.write(response.content)

        print(f"Image saved as {image_path}")
    elif is_html:
        with open("response.html", "wb") as f:
            f.write(response.content)

        print("HTML saved as response.html")
    else:
        print("Response did not contain an image or html, so nothing was saved.")

    state.generated_image_path = str(image_path) if image_path else None
    return state


# Create agent for prompt refinement
refine_agent = create_agent(
    model=openai_model,
    system_prompt=PROMPT_REFINEMENT_PROMPT,
    response_format=PromptSchema
)


def refine_prompt_with_feedback(state: SharedState) -> SharedState:
    """
    Refines the image generation prompt based on user feedback.
    Handles two cases:
    1. With feedback: Uses LLM to incorporate user feedback into the prompt
    2. Without feedback: Regenerates prompt from existing intent
    
    Updates regeneration history to track feedback and regeneration attempts.
    """
    
    # Initialize regeneration history if not present
    if state.regeneration_history is None:
        state.regeneration_history = RegenerationHistory()
    
    # Prepare context for LLM
    original_prompt = state.prepared_prompts.prompts if state.prepared_prompts else ""
    
    if state.feedback_request and state.feedback_request.feedback_text:
        # Case 1: User provided feedback - refine prompt with it
        feedback_text = state.feedback_request.feedback_text
        regeneration_attempt = state.feedback_request.regeneration_attempt
        
        # Create payload for LLM refinement
        context_payload = {
            "original_prompt": original_prompt,
            "user_feedback": feedback_text,
            "intent": state.intent.model_dump() if state.intent else {}
        }
        
        # Call LLM agent to refine the prompt
        response = refine_agent.invoke({
            "messages": [{"role": "user", "content": json.dumps(context_payload)}]
        })
        
        # Parse the refined prompt
        refined_prompt = PromptSchema.model_validate(response["structured_response"])
        state.prepared_prompts = refined_prompt
        
        print(f"Prompt refined based on feedback (attempt {regeneration_attempt})")
        
    else:
        # Case 2: No feedback - regenerate prompt from intent using simple re-prompt
        # This keeps the same intent but freshly generates a prompt
        if state.intent:
            context_payload = {
                "query": state.raw_query,
                "intent": state.intent.model_dump(),
                "context": state.context.model_dump() if state.context else None,
            }
            
            # For regeneration without feedback, use a lighter re-generation
            # We'll just create a fresh prompt from intent
            from backend.prompt_generator import generate_prompts as original_generate_prompts
            state = original_generate_prompts(state)
            
            print("Prompt regenerated from existing intent (no feedback provided)")
    
    # Update regeneration history
    state.regeneration_history.regeneration_count += 1
    
    if state.feedback_request:
        state.feedback_request.regeneration_attempt += 1
        state.regeneration_history.feedback_requests.append(state.feedback_request)
    
    # Reset the feedback request for the next iteration
    state.feedback_request = None
    
    return state
