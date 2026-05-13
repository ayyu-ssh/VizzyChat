from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from datetime import datetime
import uuid

from pydantic import BaseModel, Field

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
    classification: Optional["FeedbackClassification"] = None
    selected_strategy: Optional[str] = None


class FeedbackType(str, Enum):
    VISUAL_REFINEMENT = "visual_refinement"
    COMPOSITION_CHANGE = "composition_change"
    STYLE_SHIFT = "style_shift"
    SEMANTIC_CHANGE = "semantic_change"
    PROMPT_OVERRIDE = "prompt_override"
    UNCLASSIFIABLE = "unclassifiable"


class FeedbackClassification(BaseModel):
    feedback_type: FeedbackType
    confidence: float = 0.0
    rationale: str = ""
    suggested_strategy: str = "image_regen"
    classifier_version: str = "rule-v1"
    raw_feedback: str = ""


class RegenerationHistory(BaseModel):
    feedback_requests: List[FeedbackRequest] = []
    regeneration_count: int = 0
    max_regenerations: int = 3


class Checkpoint(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    image_path: Optional[str] = None
    prompt: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    label: Optional[str] = None


class WorkflowStartRequest(BaseModel):
    raw_query: str = Field(..., min_length=1)
    image_data_url: Optional[str] = None


class FeedbackRegenerationRequest(BaseModel):
    feedback_text: Optional[str] = Field(default=None, min_length=1)


class WorkflowStateResponse(BaseModel):
    raw_query: str
    intent: Optional[Dict[str, Any]] = None
    context: Optional[Dict[str, Any]] = None
    prepared_prompts: Optional[Dict[str, Any]] = None
    generated_image_path: Optional[str] = None
    regenerate_request: Optional[Dict[str, Any]] = None
    feedback_request: Optional[Dict[str, Any]] = None
    regeneration_history: Optional[Dict[str, Any]] = None
    should_regenerate: bool = False


class WorkflowSessionResponse(BaseModel):
    session_id: str
    generated_image_path: Optional[str] = None
    generated_image_url: Optional[str] = None
    regeneration_count: int = 0
    state: WorkflowStateResponse


class WorkflowSession(BaseModel):
    session_id: str
    state: SharedState


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
    checkpoints: List[Checkpoint] = []
    current_checkpoint_id: Optional[str] = None
    feedback_classification: Optional[FeedbackClassification] = None
    routing_strategy: Optional[str] = None
    refinement_history: List[str] = Field(default_factory=list)