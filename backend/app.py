from __future__ import annotations

from pathlib import Path
import os
from typing import Dict, Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.main import (
    run_full_workflow,
    submit_feedback_and_regenerate,
    regenerate_without_feedback,
)
from backend.utils.schema import (
    FeedbackRegenerationRequest,
    RegenerationHistory,
    SharedState,
    WorkflowSession,
    WorkflowStateResponse,
    WorkflowSessionResponse,
    WorkflowStartRequest,
)


ROOT_DIR = Path(__file__).resolve().parents[1]
IMAGES_DIR = ROOT_DIR / "images"
app = FastAPI(title="VizzyChat Workflow API", version="0.1.0")


def _parse_cors_origins() -> list[str]:
    raw_value = os.getenv("FRONTEND_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    return [origin.strip() for origin in raw_value.split(",") if origin.strip()]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_parse_cors_origins(),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

if IMAGES_DIR.exists():
    app.mount("/images", StaticFiles(directory=str(IMAGES_DIR)), name="images")

_sessions: Dict[str, WorkflowSession] = {}


def _image_url_from_path(image_path: Optional[str]) -> Optional[str]:
    if not image_path:
        return None

    path = Path(image_path)
    if path.is_absolute():
        try:
            relative_path = path.relative_to(IMAGES_DIR)
        except ValueError:
            return None
        return f"/images/{relative_path.as_posix()}"

    if path.parts and path.parts[0] == "images":
        return f"/images/{Path(*path.parts[1:]).as_posix()}"

    return f"/images/{path.name}"


def _serialize_state(state: SharedState) -> WorkflowStateResponse:
    return WorkflowStateResponse(
        raw_query=state.raw_query,
        intent=state.intent.model_dump() if state.intent else None,
        context=state.context.model_dump() if state.context else None,
        prepared_prompts=state.prepared_prompts.model_dump() if state.prepared_prompts else None,
        generated_image_path=state.generated_image_path,
        regenerate_request=state.regenerate_request.model_dump() if state.regenerate_request else None,
        feedback_request=state.feedback_request.model_dump() if state.feedback_request else None,
        regeneration_history=state.regeneration_history.model_dump() if state.regeneration_history else None,
        should_regenerate=state.should_regenerate,
    )


def _build_response(session_id: str, state: SharedState) -> WorkflowSessionResponse:
    history = state.regeneration_history
    return WorkflowSessionResponse(
        session_id=session_id,
        generated_image_path=state.generated_image_path,
        generated_image_url=_image_url_from_path(state.generated_image_path),
        regeneration_count=history.regeneration_count if history else 0,
        state=_serialize_state(state),
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/workflows/image-generation", response_model=WorkflowSessionResponse)
def start_workflow(request: WorkflowStartRequest) -> WorkflowSessionResponse:
    session_id = str(uuid4())
    # Pass optional image_data_url from the request into the workflow
    state = run_full_workflow(request.raw_query, image_data_url=request.image_data_url)

    if state.regeneration_history is None:
        state.regeneration_history = RegenerationHistory()

    _sessions[session_id] = WorkflowSession(session_id=session_id, state=state)
    return _build_response(session_id, state)


@app.post("/workflows/{session_id}/feedback", response_model=WorkflowSessionResponse)
def regenerate_with_feedback(
    session_id: str,
    request: FeedbackRegenerationRequest,
) -> WorkflowSessionResponse:
    session = _sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    state = session.state

    # If the client provided feedback_text, use the feedback-driven regeneration.
    # Otherwise, run a no-feedback regeneration variation.
    if request.feedback_text:
        state = submit_feedback_and_regenerate(
            state,
            feedback_text=request.feedback_text,
        )
    else:
        state = regenerate_without_feedback(state)
    session.state = state
    _sessions[session_id] = session
    return _build_response(session_id, state)


@app.get("/workflows/{session_id}", response_model=WorkflowSessionResponse)
def get_workflow_session(session_id: str) -> WorkflowSessionResponse:
    session = _sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return _build_response(session_id, session.state)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.app:app", host="127.0.0.1", port=8000, reload=False)