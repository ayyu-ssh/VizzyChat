from backend.utils.schema import SharedState, Context
from typing import List

def retrieve_user_info(query: str) -> List[str]:
    # Placeholder for actual user info retrieval logic
    return ["Young adult, interested in nature and art, prefers warm color palettes.",
            "Loves to spend time outdoor with friends, enjoys hiking and visiting art museums.",
            "Has a pet dog named Max, who often accompanies them on outdoor adventures.",
            "Recently traveled to the Nainital lake and Mussoorie hills, liked playing with snow and spending time by the lake."]


def retrieve_context(state: SharedState, image_data_url: str = None) -> SharedState:
    context = Context(image_data_url=None, user_info=None)
    context_required = state.intent.context_needed

    if "image" in context_required:
        context.image_data_url = image_data_url
    if "information" in context_required:
        context.user_info = retrieve_user_info(state.raw_query)

    state.context = context

    return state