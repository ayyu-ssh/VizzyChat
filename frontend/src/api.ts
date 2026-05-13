import type { WorkflowSessionResponse, WorkflowStartRequest } from './types'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
    ...init,
  })

  if (!response.ok) {
    const detail = await response.text()
    throw new Error(detail || `Request failed with status ${response.status}`)
  }

  return response.json() as Promise<T>
}

export function startWorkflow(rawQuery: string, imageDataUrl?: string | null): Promise<WorkflowSessionResponse> {
  const payload: WorkflowStartRequest = {
    raw_query: rawQuery,
    ...(imageDataUrl && { image_data_url: imageDataUrl }),
  }
  return requestJson<WorkflowSessionResponse>('/workflows/image-generation', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function sendFeedback(sessionId: string, feedbackText: string): Promise<WorkflowSessionResponse> {
  return requestJson<WorkflowSessionResponse>(`/workflows/${sessionId}/feedback`, {
    method: 'POST',
    body: JSON.stringify({ feedback_text: feedbackText }),
  })
}
