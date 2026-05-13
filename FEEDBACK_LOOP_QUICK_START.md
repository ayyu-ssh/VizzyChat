# Feedback Loop Quick Start Guide

## TL;DR

The feedback loop is already implemented and tested. Use it like this:

```python
from main import run_full_workflow, submit_feedback_and_regenerate

# Generate image
state = run_full_workflow("Picture a sunset")

# User gives feedback
state = submit_feedback_and_regenerate(state, "Make it more vibrant")

# Done! New image is in state.generated_image_path
```

## Three Main Functions

### 1. Generate Initial Image
```python
state = run_full_workflow("Your image description")
# → state.generated_image_path contains the generated image
```

### 2. Regenerate with Feedback
```python
state = submit_feedback_and_regenerate(
    state,
    feedback_text="Your feedback here",
    max_regenerations=3  # Optional, default=3
)
# → state.generated_image_path is updated with new image
# → state.regeneration_history tracks all feedback
```

### 3. Generate Alternative (No Feedback)
```python
state = regenerate_without_feedback(state)
# → Generates alternative variation of same prompt
```

## Tracking Regenerations

```python
state = run_full_workflow("Image description")

# Check how many regenerations used
print(state.regeneration_history.regeneration_count)  # 0

# Submit feedback
state = submit_feedback_and_regenerate(state, "Make it brighter")

# Check count
print(state.regeneration_history.regeneration_count)  # 1

# View all feedback history
for feedback_req in state.regeneration_history.feedback_requests:
    print(f"Attempt {feedback_req.regeneration_attempt}: {feedback_req.feedback_text}")
```

## What Was Implemented

**Files Created/Modified:**
- ✅ `backend/utils/schema.py` - Added FeedbackRequest, RegenerationHistory
- ✅ `backend/utils/prompts.py` - Added PROMPT_REFINEMENT_PROMPT
- ✅ `backend/image.py` - Added refine_prompt_with_feedback() function
- ✅ `backend/graph.py` - Added "refine_prompt" node & conditional routing
- ✅ `main.py` - Added 3 public functions
- ✅ `test_feedback_loop.py` - Test suite (ALL PASSING)
- ✅ `FEEDBACK_LOOP_DOCUMENTATION.md` - Full documentation

**Key Features:**
- Feedback-driven prompt refinement via LLM
- Max 3 regeneration attempts (configurable)
- Complete feedback history tracking
- Works with existing graph architecture
- Backward compatible

## How It Works

1. **User generates image** → `run_full_workflow()`
2. **User provides feedback** → `submit_feedback_and_regenerate(state, "feedback")`
3. **System refines prompt** using PROMPT_REFINEMENT_PROMPT
4. **System generates new image** with refined prompt
5. **Repeat** up to max_regenerations times

## Graph Integration

The feedback loop integrates into the existing graph:

```
Original: extract_intent → retrieve_context → generate_prompts → generate_image → END

With Feedback:
generate_image → [should_regenerate?]
    ├─ Yes → refine_prompt → generate_prompts → generate_image → [repeat]
    └─ No → END
```

## Testing

Run the test suite:
```bash
python test_feedback_loop.py
```

**All 6 tests pass:**
- ✅ Schema validation
- ✅ Regeneration history  
- ✅ SharedState with feedback
- ✅ Conditional routing
- ✅ Feedback progression
- ✅ Workflow integration

## Limits & Safety

- **Max regenerations**: 3 (default, configurable)
- **Regeneration attempt tracking**: Prevents infinite loops
- **History audit trail**: All feedback stored
- **Backward compatible**: Old states without feedback work fine

## Next Steps

To integrate into your API/UI:

1. Call `run_full_workflow(user_query)` for initial generation
2. Display `state.generated_image_path` to user
3. When user provides feedback, call `submit_feedback_and_regenerate(state, feedback)`
4. Update image display with new `state.generated_image_path`
5. Show regeneration count: `state.regeneration_history.regeneration_count`

Done! The feedback loop is production-ready.
