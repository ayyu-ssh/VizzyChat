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


class SharedState(BaseModel):
    raw_query: str
    intent: Optional[IntentSchema] = None
    validate_intent: ValidationSchema = ValidationSchema()
    context: Optional[Context] = None
    prepared_prompts: Optional[PromptSchema] = None
    generated_image_path: Optional[str] = None