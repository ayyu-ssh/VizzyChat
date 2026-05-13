import requests
import json
from backend.utils.schema import (
    SharedState,
    PromptSchema,
    RegenerationHistory,
    FeedbackRequest,
    Checkpoint,
    FeedbackClassification,
    FeedbackType,
)
from datetime import datetime
from dotenv import load_dotenv
import os
from pathlib import Path
import uuid
from base64 import b64encode
from langchain.agents import create_agent
from backend.utils.config import (
    openai_model,
    ENABLE_FEEDBACK_CLASSIFICATION,
    CLASSIFIER_CONFIDENCE_THRESHOLD,
)
from backend.utils.prompts import PROMPT_REFINEMENT_PROMPT, FEEDBACK_CLASSIFIER_PROMPT
load_dotenv()

CLOUDFLARE_API_KEY = os.getenv("CLOUDFLARE_API_KEY")
CLOUDFLARE_WORKER_URL = os.getenv("CLOUDFLARE_WORKER_URL")
IMAGES_DIR = Path(__file__).resolve().parents[1] / "images"


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def _rule_based_feedback_classification(feedback_text: str) -> FeedbackClassification:
    text = feedback_text.lower().strip()

    prompt_override_terms = (
        "completely different",
        "ignore previous",
        "start over",
        "new scene",
        "different subject",
    )
    style_terms = (
        "style",
        "watercolor",
        "oil painting",
        "anime",
        "photorealistic",
        "ghibli",
        "pixel art",
    )
    semantic_terms = (
        "mood",
        "emotion",
        "feeling",
        "story",
        "narrative",
        "theme",
        "winter",
        "summer",
        "night",
        "day",
    )
    composition_terms = (
        "add",
        "remove",
        "move",
        "position",
        "background",
        "foreground",
        "bigger",
        "smaller",
    )
    visual_terms = (
        "brighter",
        "darker",
        "contrast",
        "saturation",
        "color",
        "sharper",
        "blur",
        "lighting",
    )

    if _contains_any(text, prompt_override_terms):
        return FeedbackClassification(
            feedback_type=FeedbackType.PROMPT_OVERRIDE,
            confidence=0.95,
            rationale="User requested a full reset or major replacement.",
            suggested_strategy="prompt_refine",
            classifier_version="rule-v1",
            raw_feedback=feedback_text,
        )

    if _contains_any(text, style_terms):
        return FeedbackClassification(
            feedback_type=FeedbackType.STYLE_SHIFT,
            confidence=0.9,
            rationale="Feedback indicates an artistic style change.",
            suggested_strategy="prompt_refine",
            classifier_version="rule-v1",
            raw_feedback=feedback_text,
        )

    if _contains_any(text, semantic_terms):
        return FeedbackClassification(
            feedback_type=FeedbackType.SEMANTIC_CHANGE,
            confidence=0.85,
            rationale="Feedback changes scene semantics or overall meaning.",
            suggested_strategy="prompt_refine",
            classifier_version="rule-v1",
            raw_feedback=feedback_text,
        )

    if _contains_any(text, composition_terms):
        return FeedbackClassification(
            feedback_type=FeedbackType.COMPOSITION_CHANGE,
            confidence=0.8,
            rationale="Feedback requests element-level composition adjustments.",
            suggested_strategy="image_regen",
            classifier_version="rule-v1",
            raw_feedback=feedback_text,
        )

    if _contains_any(text, visual_terms):
        return FeedbackClassification(
            feedback_type=FeedbackType.VISUAL_REFINEMENT,
            confidence=0.8,
            rationale="Feedback requests local visual refinements.",
            suggested_strategy="image_regen",
            classifier_version="rule-v1",
            raw_feedback=feedback_text,
        )

    return FeedbackClassification(
        feedback_type=FeedbackType.UNCLASSIFIABLE,
        confidence=0.4,
        rationale="Could not confidently classify; defaulting to safer image regeneration.",
        suggested_strategy="image_regen",
        classifier_version="rule-v1",
        raw_feedback=feedback_text,
    )


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


def _last_generated_image_data(state: SharedState) -> tuple[str | None, str | None]:
    image_path = None
    if getattr(state, "checkpoints", None):
        try:
            image_path = state.checkpoints[-1].image_path
        except Exception:
            image_path = state.generated_image_path
    else:
        image_path = state.generated_image_path

    if not image_path:
        return None, None

    path = Path(image_path)
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[1] / image_path

    if not path.exists():
        return image_path, None

    content_type = "image/jpeg"
    suffix = path.suffix.lower()
    if suffix == ".png":
        content_type = "image/png"
    elif suffix == ".gif":
        content_type = "image/gif"
    elif suffix == ".webp":
        content_type = "image/webp"

    image_bytes = path.read_bytes()
    data_url = f"data:{content_type};base64,{b64encode(image_bytes).decode('ascii')}"
    return str(path), data_url

def generate_image(state: SharedState) -> SharedState:

    if state.prepared_prompts.prompts is None:
        raise ValueError("Error accessing prepared prompts:")

    prompt = state.prepared_prompts.prompts
    last_image_path, last_image_data_url = _last_generated_image_data(state)

    url = CLOUDFLARE_WORKER_URL

    headers = {
        "Authorization": f"Bearer {CLOUDFLARE_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {"prompt": prompt}
    use_feedback_payload = (
        state.feedback_request
        and state.feedback_request.feedback_text
        and (state.routing_strategy in {None, "image_regen"})
    )
    if use_feedback_payload:
        payload["feedback"] = state.feedback_request.feedback_text
        if last_image_data_url:
            payload["image_data_url"] = last_image_data_url
        if last_image_path:
            payload["image_path"] = last_image_path

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
    # Record a checkpoint for this generation
    if image_path:
        try:
            checkpoint = Checkpoint(
                image_path=str(image_path),
                prompt=prompt,
                timestamp=datetime.utcnow()
            )

            if getattr(state, "checkpoints", None) is None:
                state.checkpoints = []

            state.checkpoints.append(checkpoint)
            state.current_checkpoint_id = checkpoint.id
        except Exception as e:
            print(f"Warning: failed to record checkpoint: {e}")
    return state


# Create agent for prompt refinement
refine_agent = create_agent(
    model=openai_model,
    system_prompt=PROMPT_REFINEMENT_PROMPT,
    response_format=PromptSchema
)

classifier_agent = create_agent(
    model=openai_model,
    system_prompt=FEEDBACK_CLASSIFIER_PROMPT,
    response_format=FeedbackClassification,
)


def classify_feedback_strategy(state: SharedState) -> SharedState:
    """Classify feedback and choose either image_regen or prompt_refine."""
    if not state.feedback_request or not state.feedback_request.feedback_text:
        state.feedback_classification = FeedbackClassification(
            feedback_type=FeedbackType.UNCLASSIFIABLE,
            confidence=1.0,
            rationale="No feedback text provided.",
            suggested_strategy="image_regen",
            classifier_version="rule-v1",
            raw_feedback="",
        )
        state.routing_strategy = "image_regen"
        return state

    classification = _rule_based_feedback_classification(state.feedback_request.feedback_text)

    # Optional LLM upgrade path. Rules remain the safe baseline.
    if ENABLE_FEEDBACK_CLASSIFICATION and classification.confidence < CLASSIFIER_CONFIDENCE_THRESHOLD:
        try:
            payload = {
                "feedback_text": state.feedback_request.feedback_text,
                "intent": state.intent.model_dump() if state.intent else None,
                "prompt": state.prepared_prompts.prompts if state.prepared_prompts else None,
            }
            response = classifier_agent.invoke({
                "messages": [{"role": "user", "content": json.dumps(payload)}]
            })
            classification = FeedbackClassification.model_validate(response["structured_response"])
        except Exception:
            # Keep deterministic fallback from rules.
            pass

    state.feedback_classification = classification
    state.routing_strategy = classification.suggested_strategy or "image_regen"
    return state


def refine_prompt_with_feedback(state: SharedState) -> SharedState:
    """
    Preserve the current prompt while recording feedback-driven regeneration.

    The feedback loop now reuses the last generated image and the user's
    feedback without rewriting the prepared prompt.
    """

    if state.regeneration_history is None:
        state.regeneration_history = RegenerationHistory()

    if state.feedback_request and state.feedback_request.feedback_text:
        if state.routing_strategy == "prompt_refine":
            original_prompt = state.prepared_prompts.prompts if state.prepared_prompts else ""
            context_payload = {
                "original_prompt": original_prompt,
                "user_feedback": state.feedback_request.feedback_text,
                "intent": state.intent.model_dump() if state.intent else {},
            }
            response = refine_agent.invoke({
                "messages": [{"role": "user", "content": json.dumps(context_payload)}]
            })
            refined_prompt = PromptSchema.model_validate(response["structured_response"])
            state.prepared_prompts = refined_prompt
        else:
            last_image_path, _ = _last_generated_image_data(state)
            state.feedback_request.image_path = last_image_path or state.feedback_request.image_path or state.generated_image_path or ""
    else:
        if state.intent:
            from backend.prompt_generator import generate_prompts as original_generate_prompts

            state = original_generate_prompts(state)

    state.regeneration_history.regeneration_count += 1
    
    if state.feedback_request:
        state.feedback_request.regeneration_attempt += 1
        state.feedback_request.classification = state.feedback_classification
        state.feedback_request.selected_strategy = state.routing_strategy or "image_regen"
        state.regeneration_history.feedback_requests.append(state.feedback_request)

    if state.routing_strategy:
        state.refinement_history.append(state.routing_strategy)
    
    return state
