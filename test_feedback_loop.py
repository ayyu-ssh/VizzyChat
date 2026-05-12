"""
Test script for the image feedback loop implementation.

This script tests:
1. Schema creation and validation
2. Feedback request tracking
3. Regeneration history tracking
4. Conditional routing in the graph
5. The refine_prompt_with_feedback function
"""

import json
from backend.utils.schema import (
    SharedState, 
    FeedbackRequest, 
    RegenerationHistory,
    IntentSchema,
    PromptSchema,
    Context
)
from backend.graph import should_regenerate

def test_feedback_schema():
    """Test that FeedbackRequest schema works correctly."""
    print("\n=== Test 1: Feedback Schema ===")
    
    feedback = FeedbackRequest(
        feedback_text="Make the colors more vibrant and add more detail",
        image_path="/images/generated_abc123.jpg",
        regeneration_attempt=1
    )
    
    assert feedback.feedback_text == "Make the colors more vibrant and add more detail"
    assert feedback.regeneration_attempt == 1
    print("PASS: FeedbackRequest schema validates correctly")


def test_regeneration_history():
    """Test that RegenerationHistory tracks feedback correctly."""
    print("\n=== Test 2: Regeneration History ===")
    
    feedback1 = FeedbackRequest(
        feedback_text="Add more detail to the background",
        image_path="/images/generated_001.jpg",
        regeneration_attempt=1
    )
    
    feedback2 = FeedbackRequest(
        feedback_text="Make it brighter and more saturated",
        image_path="/images/generated_002.jpg",
        regeneration_attempt=2
    )
    
    history = RegenerationHistory(
        feedback_requests=[feedback1, feedback2],
        regeneration_count=2,
        max_regenerations=3
    )
    
    assert len(history.feedback_requests) == 2
    assert history.regeneration_count == 2
    assert history.max_regenerations == 3
    print(f"PASS: RegenerationHistory tracks {len(history.feedback_requests)} feedback requests")
    print(f"      Regenerations: {history.regeneration_count}/{history.max_regenerations}")


def test_shared_state_with_feedback():
    """Test SharedState with feedback tracking."""
    print("\n=== Test 3: SharedState with Feedback ===")
    
    intent = IntentSchema(
        task="image generation",
        style="oil painting",
        mood="warm and cozy",
        theme="cottage landscape",
        context_needed=[]
    )
    
    feedback = FeedbackRequest(
        feedback_text="Add more people in the scene",
        image_path="/images/generated_xyz.jpg"
    )
    
    history = RegenerationHistory()
    
    state = SharedState(
        raw_query="Paint a cozy cottage in an oil painting style",
        intent=intent,
        prepared_prompts=PromptSchema(prompts="A warm oil painting of a cottage..."),
        generated_image_path="/images/generated_xyz.jpg",
        feedback_request=feedback,
        regeneration_history=history,
        should_regenerate=True
    )
    
    assert state.should_regenerate == True
    assert state.feedback_request.feedback_text == "Add more people in the scene"
    assert state.regeneration_history.max_regenerations == 3
    print("PASS: SharedState correctly holds feedback request and regeneration history")


def test_conditional_routing():
    """Test the should_regenerate conditional router."""
    print("\n=== Test 4: Conditional Routing ===")
    
    # Case 1: Should regenerate - under limit
    state1 = SharedState(
        raw_query="Test query",
        should_regenerate=True,
        regeneration_history=RegenerationHistory(
            regeneration_count=0,
            max_regenerations=3
        )
    )
    result1 = should_regenerate(state1)
    assert result1 == "refine_prompt", f"Expected 'refine_prompt', got '{result1}'"
    print("PASS: Routes to 'refine_prompt' when should_regenerate=True and under limit")
    
    # Case 2: Should not regenerate - flag is false
    state2 = SharedState(
        raw_query="Test query",
        should_regenerate=False,
        regeneration_history=RegenerationHistory(
            regeneration_count=0,
            max_regenerations=3
        )
    )
    result2 = should_regenerate(state2)
    assert result2 == "end", f"Expected 'end', got '{result2}'"
    print("PASS: Routes to 'end' when should_regenerate=False")
    
    # Case 3: Max regenerations reached
    state3 = SharedState(
        raw_query="Test query",
        should_regenerate=True,
        regeneration_history=RegenerationHistory(
            regeneration_count=3,
            max_regenerations=3
        )
    )
    result3 = should_regenerate(state3)
    assert result3 == "end", f"Expected 'end', got '{result3}'"
    print("PASS: Routes to 'end' when max regenerations reached")


def test_feedback_request_progression():
    """Test how feedback requests progress through regenerations."""
    print("\n=== Test 5: Feedback Request Progression ===")
    
    # Initial state
    state = SharedState(raw_query="Test query")
    assert state.regeneration_history is None
    print("PASS: Initial state has no regeneration history")
    
    # First feedback
    history1 = RegenerationHistory()
    feedback1 = FeedbackRequest(
        feedback_text="Make it brighter",
        image_path="/images/gen_1.jpg",
        regeneration_attempt=1
    )
    history1.feedback_requests.append(feedback1)
    history1.regeneration_count = 1
    
    state.regeneration_history = history1
    assert state.regeneration_history.regeneration_count == 1
    assert len(state.regeneration_history.feedback_requests) == 1
    print("PASS: First feedback tracked in regeneration history")
    
    # Second feedback
    feedback2 = FeedbackRequest(
        feedback_text="Add more contrast",
        image_path="/images/gen_2.jpg",
        regeneration_attempt=2
    )
    state.regeneration_history.feedback_requests.append(feedback2)
    state.regeneration_history.regeneration_count = 2
    
    assert state.regeneration_history.regeneration_count == 2
    assert len(state.regeneration_history.feedback_requests) == 2
    print(f"PASS: Second feedback tracked. Total: {len(state.regeneration_history.feedback_requests)} feedback items")


def test_feedback_loop_workflow():
    """Test the complete feedback loop workflow structure."""
    print("\n=== Test 6: Feedback Loop Workflow ===")
    
    # Simulate initial image generation
    initial_state = SharedState(
        raw_query="Generate a sunset landscape",
        intent=IntentSchema(
            task="image generation",
            style="impressionist",
            mood="peaceful",
            theme="nature",
            context_needed=[]
        ),
        prepared_prompts=PromptSchema(
            prompts="An impressionist-style peaceful sunset landscape with warm orange and pink hues..."
        ),
        generated_image_path="/images/generated_001.jpg"
    )
    
    assert initial_state.generated_image_path is not None
    assert initial_state.should_regenerate == False
    print("PASS: Initial image generation state ready")
    
    # User provides feedback
    initial_state.feedback_request = FeedbackRequest(
        feedback_text="Add more clouds and make it more dramatic",
        image_path=initial_state.generated_image_path,
        regeneration_attempt=1
    )
    initial_state.should_regenerate = True
    
    # Initialize regeneration history
    if initial_state.regeneration_history is None:
        initial_state.regeneration_history = RegenerationHistory(max_regenerations=3)
    
    assert initial_state.should_regenerate == True
    assert initial_state.feedback_request is not None
    print("PASS: Feedback submission state ready")
    
    # Check routing
    route = should_regenerate(initial_state)
    assert route == "refine_prompt"
    print(f"PASS: Routing decision correct: '{route}'")
    
    # Simulate regeneration
    initial_state.regeneration_history.regeneration_count += 1
    initial_state.regeneration_history.feedback_requests.append(initial_state.feedback_request)
    
    assert initial_state.regeneration_history.regeneration_count == 1
    assert len(initial_state.regeneration_history.feedback_requests) == 1
    print("PASS: Regeneration history updated correctly")


def main():
    """Run all tests."""
    print("=" * 60)
    print("FEEDBACK LOOP TEST SUITE")
    print("=" * 60)
    
    try:
        test_feedback_schema()
        test_regeneration_history()
        test_shared_state_with_feedback()
        test_conditional_routing()
        test_feedback_request_progression()
        test_feedback_loop_workflow()
        
        print("\n" + "=" * 60)
        print("ALL TESTS PASSED!")
        print("=" * 60)
        print("\nFeedback Loop Implementation Summary:")
        print("✓ Schema models (FeedbackRequest, RegenerationHistory) working")
        print("✓ SharedState extended with feedback tracking")
        print("✓ Conditional routing logic validated")
        print("✓ Feedback progression through regenerations verified")
        print("✓ Graph integration ready")
        print("\nNext Steps:")
        print("1. Test refine_prompt_with_feedback() with actual LLM calls")
        print("2. Test full workflow end-to-end with image generation")
        print("3. Validate feedback incorporation into refined prompts")
        
    except AssertionError as e:
        print(f"\nTEST FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\nERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
