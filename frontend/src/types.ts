export type Intent = {
  task: string
  style?: string | null
  mood?: string | null
  theme?: string | null
  context_needed: string[]
}

export type Prompt = {
  prompts?: string | null
}

export type WorkflowState = {
  raw_query: string
  intent?: Intent | null
  context?: Record<string, unknown> | null
  prepared_prompts?: Prompt | null
  generated_image_path?: string | null
  generated_image_url?: string | null
  regenerate_request?: Record<string, unknown> | null
  feedback_request?: Record<string, unknown> | null
  regeneration_history?: {
    feedback_requests?: Array<Record<string, unknown>>
    regeneration_count?: number
  } | null
  should_regenerate?: boolean
}

export type WorkflowSessionResponse = {
  session_id: string
  generated_image_path?: string | null
  generated_image_url?: string | null
  regeneration_count: number
  state: WorkflowState
}

export type ChatMessage =
  | { id: string; role: 'user'; kind: 'query' | 'feedback'; content: string }
  | { id: string; role: 'assistant'; kind: 'intent'; intent: Intent }
  | { id: string; role: 'assistant'; kind: 'prompt'; prompt: string }
  | { id: string; role: 'assistant'; kind: 'image'; imageUrl: string; imagePath?: string | null; regenerationCount: number; note?: string }
  | { id: string; role: 'assistant'; kind: 'status'; title: string; description: string }

export interface WorkflowStartRequest {
  raw_query: string;
  image_data_url?: string | null;
}

export interface FeedbackRegenerationRequest {
  feedback_text?: string | null;
}
