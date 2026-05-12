from backend.intent import extract_intent
from backend.retrive_context import retrieve_context
from backend.prompt_generator import generate_prompts
from backend.image import generate_image, refine_prompt_with_feedback
from backend.utils.schema import SharedState, FeedbackRequest, RegenerationHistory
from backend.graph import workflow
import json 
from typing import Optional

raw_query = "Picture a moment from my last trip."


def main():
    """Run the complete image generation workflow."""
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


def run_full_workflow(raw_query: str) -> SharedState:
    """
    Run the complete image generation workflow using LangGraph.
    
    Args:
        raw_query: The user's natural language request for image generation
        
    Returns:
        The final SharedState with generated_image_path populated
    """
    initial_state = SharedState(raw_query=raw_query)
    final_state = workflow.invoke(initial_state)
    return final_state


def submit_feedback_and_regenerate(
    state: SharedState,
    feedback_text: str,
    max_regenerations: int = 3
) -> SharedState:
    """
    Submit feedback on a generated image and trigger regeneration.
    
    This function refines the prompt based on feedback and regenerates the image.
    NOTE: Does NOT re-extract intent or retrieve context - only refines prompt and regenerates image.
    
    Args:
        state: The current SharedState with generated_image_path populated
        feedback_text: User's feedback on the generated image (e.g., "make it brighter" or "add more colors")
        max_regenerations: Maximum number of regeneration attempts allowed (default: 3)
        
    Returns:
        Updated SharedState with new generated_image_path and updated regeneration_history
        
    Example:
        ```
        # Initial generation
        state = run_full_workflow("Picture a sunset over mountains")
        
        # User views image and provides feedback
        state = submit_feedback_and_regenerate(
            state,
            feedback_text="The colors are too muted, make it more vibrant",
            max_regenerations=3
        )
        
        # Check the new generated image
        print(f"Regenerated image: {state.generated_image_path}")
        ```
    """
    
    # Initialize regeneration history if not present
    if state.regeneration_history is None:
        state.regeneration_history = RegenerationHistory(max_regenerations=max_regenerations)
    
    # Check if we haven't exceeded max regenerations
    if state.regeneration_history.regeneration_count >= state.regeneration_history.max_regenerations:
        print(f"Maximum regenerations ({max_regenerations}) reached. Cannot regenerate further.")
        return state
    
    # Create feedback request
    state.feedback_request = FeedbackRequest(
        feedback_text=feedback_text,
        image_path=state.generated_image_path or "",
        regeneration_attempt=state.regeneration_history.regeneration_count + 1
    )
    
    # Refine prompt based on feedback (skips intent extraction and context retrieval)
    state = refine_prompt_with_feedback(state)
    
    # Regenerate image with refined prompt
    state = generate_image(state)
    
    return state


def regenerate_without_feedback(state: SharedState, max_regenerations: int = 3) -> SharedState:
    """
    Regenerate the image prompt and image without explicit user feedback.
    
    This is useful for trying alternative variations of the image without
    requiring specific feedback. It regenerates the prompt from the existing
    intent and generates a new image.
    NOTE: Does NOT re-extract intent or retrieve context - only regenerates prompt and image.
    
    Args:
        state: The current SharedState with generated_image_path populated
        max_regenerations: Maximum number of regeneration attempts allowed (default: 3)
        
    Returns:
        Updated SharedState with new generated_image_path and updated regeneration_history
        
    Example:
        ```
        state = run_full_workflow("Picture a sunset over mountains")
        
        # User wants to see another variation
        state = regenerate_without_feedback(state)
        print(f"Alternative image: {state.generated_image_path}")
        ```
    """
    
    # Initialize regeneration history if not present
    if state.regeneration_history is None:
        state.regeneration_history = RegenerationHistory(max_regenerations=max_regenerations)
    
    # Check if we haven't exceeded max regenerations
    if state.regeneration_history.regeneration_count >= state.regeneration_history.max_regenerations:
        print(f"Maximum regenerations ({max_regenerations}) reached. Cannot regenerate further.")
        return state
    
    # Set feedback to None to trigger simple prompt regeneration (without feedback)
    state.feedback_request = None
    
    # Refine prompt without feedback (regenerates from intent)
    state = refine_prompt_with_feedback(state)
    
    # Regenerate image with new prompt
    state = generate_image(state)
    
    return state


if __name__ == "__main__":
    main()

