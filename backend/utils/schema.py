from pydantic import BaseModel
from typing import List, Optional

class IntentSchema(BaseModel):
    task: str
    style: Optional[str] = None
    mood: Optional[str] = None
    theme: Optional[str] = None
    context_needed: List[str]

class Context(BaseModel):
    image_data_url: Optional[str] = None
    user_info: Optional[List[str]] = []


class PromptSchema(BaseModel):
    prompts: Optional[str] = None


class ValidationSchema(BaseModel):
    is_valid: bool = False
    retries: int = 1
    feedback: Optional[str] = None

class RegenrateImageRequest(BaseModel):
    feedback: Optional[str] = None
    regenerate: bool = False
    count: int = 0


class FeedbackRequest(BaseModel):
    feedback_text: str
    image_path: str
    regeneration_attempt: int = 1


class RegenerationHistory(BaseModel):
    feedback_requests: List[FeedbackRequest] = []
    regeneration_count: int = 0
    max_regenerations: int = 3


class SharedState(BaseModel):
    raw_query: str
    intent: Optional[IntentSchema] = None
    validate_intent: ValidationSchema = ValidationSchema()
    context: Optional[Context] = None
    prepared_prompts: Optional[PromptSchema] = None
    generated_image_path: Optional[str] = None
    regenerate_request: Optional[RegenrateImageRequest] = None
    feedback_request: Optional[FeedbackRequest] = None
    regeneration_history: Optional[RegenerationHistory] = None
    should_regenerate: bool = False