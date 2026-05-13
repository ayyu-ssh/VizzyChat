from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import backend.app as workflow_api
from backend.utils.schema import Context, FeedbackRequest, IntentSchema, PromptSchema, RegenerationHistory, SharedState


def _make_state(image_path: str = "images/generated_test.jpg") -> SharedState:
    return SharedState(
        raw_query="A cozy cabin in the woods",
        intent=IntentSchema(
            task="image generation",
            style="illustrative",
            mood="warm",
            theme="cabin",
            context_needed=[],
        ),
        context=Context(image_data_url=None, user_info=[]),
        prepared_prompts=PromptSchema(prompts="A cozy cabin in the woods at sunset"),
        generated_image_path=image_path,
        regeneration_history=RegenerationHistory(regeneration_count=0),
        should_regenerate=False,
    )


class WorkflowApiTest(unittest.TestCase):
    def setUp(self) -> None:
        workflow_api._sessions.clear()
        self.client = TestClient(workflow_api.app)

    def test_health(self) -> None:
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_start_workflow(self) -> None:
        fake_state = _make_state()
        with patch("backend.app.run_full_workflow", return_value=fake_state) as mocked_run:
            response = self.client.post(
                "/workflows/image-generation",
                json={"raw_query": "A cozy cabin in the woods"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["session_id"])
        self.assertEqual(payload["generated_image_path"], "images/generated_test.jpg")
        self.assertEqual(payload["generated_image_url"], "/images/generated_test.jpg")
        self.assertEqual(mocked_run.call_count, 1)

    def test_feedback_regeneration(self) -> None:
        session_id = "session-123"
        workflow_api._sessions[session_id] = workflow_api.WorkflowSession(session_id=session_id, state=_make_state())
        regenerated_state = _make_state("images/generated_updated.jpg")
        regenerated_state.regeneration_history = RegenerationHistory(regeneration_count=1)
        regenerated_state.feedback_request = FeedbackRequest(
            feedback_text="Make it brighter",
            image_path="images/generated_test.jpg",
            regeneration_attempt=1,
        )

        with patch("backend.app.submit_feedback_and_regenerate", return_value=regenerated_state) as mocked_regenerate:
            response = self.client.post(
                f"/workflows/{session_id}/feedback",
                json={"feedback_text": "Make it brighter"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["generated_image_path"], "images/generated_updated.jpg")
        self.assertEqual(payload["regeneration_count"], 1)
        self.assertEqual(payload["generated_image_url"], "/images/generated_updated.jpg")
        self.assertEqual(mocked_regenerate.call_count, 1)

    def test_feedback_regeneration_preserves_original_prompt(self) -> None:
        session_id = "session-preserve-prompt"
        state = _make_state()
        workflow_api._sessions[session_id] = workflow_api.WorkflowSession(session_id=session_id, state=state)

        regenerated_state = _make_state("images/generated_preserved.jpg")
        regenerated_state.prepared_prompts = state.prepared_prompts
        regenerated_state.regeneration_history = RegenerationHistory(regeneration_count=1)
        regenerated_state.feedback_request = FeedbackRequest(
            feedback_text="Keep the structure but make it warmer",
            image_path="images/generated_test.jpg",
            regeneration_attempt=1,
        )

        with patch("backend.app.submit_feedback_and_regenerate", return_value=regenerated_state):
            response = self.client.post(
                f"/workflows/{session_id}/feedback",
                json={"feedback_text": "Keep the structure but make it warmer"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["state"]["prepared_prompts"]["prompts"], state.prepared_prompts.prompts)

    def test_regenerate_without_feedback(self) -> None:
        session_id = "session-nofeedback"
        workflow_api._sessions[session_id] = workflow_api.WorkflowSession(session_id=session_id, state=_make_state())
        regenerated_state = _make_state("images/generated_no_feedback.jpg")
        regenerated_state.regeneration_history = RegenerationHistory(regeneration_count=1)

        with patch("backend.app.regenerate_without_feedback", return_value=regenerated_state) as mocked_no_fb:
            response = self.client.post(
                f"/workflows/{session_id}/feedback",
                json={},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["generated_image_path"], "images/generated_no_feedback.jpg")
        self.assertEqual(payload["regeneration_count"], 1)
        self.assertEqual(payload["generated_image_url"], "/images/generated_no_feedback.jpg")
        self.assertEqual(mocked_no_fb.call_count, 1)
    def test_feedback_session_missing(self) -> None:
        response = self.client.post(
            "/workflows/missing/feedback",
            json={"feedback_text": "Make it brighter"},
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Session not found")

    def test_feedback_max_regeneration_rejected(self) -> None:
        # Test that regeneration is unlimited - even with many regenerations, it should still work
        session_id = "session-unlimited"
        state = _make_state()
        state.regeneration_history = RegenerationHistory(regeneration_count=100)
        workflow_api._sessions[session_id] = workflow_api.WorkflowSession(session_id=session_id, state=state)
        
        regenerated_state = _make_state("images/generated_unlimited.jpg")
        regenerated_state.regeneration_history = RegenerationHistory(regeneration_count=101)

        with patch("backend.app.regenerate_without_feedback", return_value=regenerated_state) as mocked_no_fb:
            response = self.client.post(
                f"/workflows/{session_id}/feedback",
                json={},
            )

        # Should still succeed (200), not hit a limit (409)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(mocked_no_fb.call_count, 1)


if __name__ == "__main__":
    unittest.main()