import { FormEvent, useState } from 'react'
import { sendFeedback, startWorkflow } from './api'
import type { ChatMessage, Intent, WorkflowSessionResponse } from './types'


const welcomeMessage: ChatMessage = {
  id: 'welcome',
  role: 'assistant',
  kind: 'status',
  title: 'Describe an image and Vizzy will turn it into a workflow thread.',
  description: 'The chat shows your request, the parsed intent, the prepared prompt, and the generated result as bubbles in sequence.',
}

type ComposerMode = 'feedback' | 'new-thread'

type ThreadRecord = {
  sessionId: string
  title: string
  messages: ChatMessage[]
  regenerationCount: number
  isDraft?: boolean
}

function uid(prefix: string): string {
  return `${prefix}-${Math.random().toString(36).slice(2, 10)}`
}

function buildMessagesFromResponse(response: WorkflowSessionResponse, mode: 'initial' | 'regeneration'): ChatMessage[] {
  const messages: ChatMessage[] = []
  const state = response.state

  messages.push({
    id: uid('intent'),
    role: 'assistant',
    kind: 'intent',
    intent: state.intent ?? { task: 'image generation', context_needed: [] },
  })

  // Only display the prepared prompt for the initial generation pass.
  // For feedback-driven regenerations we keep the original prompt visible
  // (do not re-render a prompt bubble), since regenerations reuse the prior image.
  if (mode === 'initial' && state.prepared_prompts?.prompts) {
    messages.push({
      id: uid('prompt'),
      role: 'assistant',
      kind: 'prompt',
      prompt: state.prepared_prompts.prompts,
    })
  }

  if (response.generated_image_url) {
    messages.push({
      id: uid('image'),
      role: 'assistant',
      kind: 'image',
      imageUrl: response.generated_image_url,
      imagePath: response.generated_image_path,
      regenerationCount: response.regeneration_count,
      note: mode === 'initial' ? 'Generated from the parsed intent and prompt.' : 'Regenerated from the prior image and your feedback.',
    })
  }

  return messages
}

function createThreadTitle(query: string, index: number): string {
  const trimmed = query.trim()
  if (!trimmed) {
    return `Thread ${index + 1}`
  }

  if (trimmed.length <= 28) {
    return trimmed
  }

  return `${trimmed.slice(0, 28).trimEnd()}…`
}

function IntentBubble({ intent }: { intent: Intent }) {
  const chips = [
    ['Task', intent.task],
    ['Style', intent.style],
    ['Mood', intent.mood],
    ['Theme', intent.theme],
  ].filter(([, value]) => Boolean(value)) as Array<[string, string]>

  return (
    <div className="bubble assistant bubble-intent">
      <div className="bubble-label">🪄 Vizzy</div>
      <p className="bubble-title">I interpreted your request into the following creative direction.</p>
      <div className="chip-grid">
        {chips.map(([label, value]) => (
          <span className="chip" key={label}>
            <strong>{label}:</strong> {value}
          </span>
        ))}
      </div>
      <div className="context-box">
        <span className="context-label">Context needed</span>
        <span>{intent.context_needed.length ? intent.context_needed.join(', ') : 'None'}</span>
      </div>
    </div>
  )
}

function PromptBubble({ prompt }: { prompt: string }) {
  const [copied, setCopied] = useState(false)

  async function handleCopy() {
    await navigator.clipboard.writeText(prompt)
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1400)
  }

  return (
    <div className="bubble assistant bubble-prompt">
      <div className="bubble-header-row">
        <div>
          <div className="bubble-label">Prepared prompt</div>
          <p className="bubble-title">This is the generation prompt passed into the model.</p>
        </div>
        <button className="ghost-button" type="button" onClick={handleCopy}>
          {copied ? 'Copied' : 'Copy'}
        </button>
      </div>
      <pre className="prompt-block">{prompt}</pre>
    </div>
  )
}

function ImageBubble({ imageUrl, imagePath, regenerationCount, note }: { imageUrl: string; imagePath?: string | null; regenerationCount: number; note?: string }) {
  async function handleDownload() {
    const response = await fetch(imageUrl)
    const blob = await response.blob()
    const objectUrl = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = objectUrl
    link.download = imagePath?.split('/').pop() ?? 'vizzy-generated-image'
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(objectUrl)
  }

  return (
    <div className="bubble assistant bubble-image">
      <div className="bubble-label">Image result</div>
      <p className="bubble-title">{note ?? 'Here is the generated image.'}</p>
      <img className="result-image" src={imageUrl} alt="Generated result" />
      <div className="image-meta">
        <span>Session image</span>
        <span>Regenerations: {regenerationCount}</span>
        <button className="ghost-button" type="button" onClick={handleDownload}>
          Download image
        </button>
      </div>
    </div>
  )
}

function StatusBubble({ title, description }: { title: string; description: string }) {
  return (
    <div className="bubble assistant bubble-status">
      <div className="bubble-label">🪄 Vizzy</div>
      <p className="bubble-title">{title}</p>
      <p className="bubble-text">{description}</p>
    </div>
  )
}

function QueryBubble({ content, role }: { content: string; role: 'user' | 'assistant' }) {
  return (
    <div className={`bubble ${role}`}>
      <div className="bubble-label">{role === 'user' ? '👤 You' : '🪄 Vizzy'}</div>
      <p className="bubble-text">{content}</p>
    </div>
  )
}

export default function App() {
  const [composerText, setComposerText] = useState('')
  const [referenceImageDataUrl, setReferenceImageDataUrl] = useState<string | null>(null)
  const [threads, setThreads] = useState<ThreadRecord[]>([])
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const activeThread = threads.find((thread) => thread.sessionId === activeSessionId) ?? null
  const visibleMessages = activeThread?.messages ?? [welcomeMessage]
  const canContinueCurrentThread = activeThread !== null && !activeThread.isDraft
  const activeComposerMode: ComposerMode = canContinueCurrentThread ? 'feedback' : 'new-thread'
  const submitLabel = activeComposerMode === 'feedback' ? 'Send feedback' : 'Generate'
  const composerTitle = activeComposerMode === 'feedback' ? 'Refine the current thread' : 'Start a new thread'
  const composerDescription =
    activeComposerMode === 'feedback'
      ? 'Your message is sent as feedback for the current image and stays in the same session tab.'
      : 'This draft will open as a new chat tab when you generate.'

  function activateThread(sessionId: string) {
    setActiveSessionId(sessionId)
    setError(null)
    setComposerText('')
  }

  function handleReferenceImageUpload(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    if (file) {
      const reader = new FileReader()
      reader.onload = (e) => {
        const dataUrl = e.target?.result as string
        setReferenceImageDataUrl(dataUrl)
      }
      reader.readAsDataURL(file)
    }
  }

  function clearReferenceImage() {
    setReferenceImageDataUrl(null)
    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement
    if (fileInput) {
      fileInput.value = ''
    }
  }

  function startDraftSession() {
    const draftId = `draft-${uid('session')}`
    setThreads((currentThreads) => [
      ...currentThreads,
      {
        sessionId: draftId,
        title: 'New session',
        messages: [welcomeMessage],
        regenerationCount: 0,
        isDraft: true,
      },
    ])
    setActiveSessionId(draftId)
    setError(null)
    setComposerText('')
  }

  async function handleComposerSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setLoading(true)

    const userMessage: ChatMessage = {
      id: uid(activeComposerMode === 'feedback' ? 'feedback' : 'query'),
      role: 'user',
      kind: activeComposerMode === 'feedback' ? 'feedback' : 'query',
      content: composerText,
    }

    try {
      if (activeComposerMode === 'feedback' && activeThread) {
        const sessionId = activeThread.sessionId
        setThreads((currentThreads) =>
          currentThreads.map((thread) => {
            if (thread.sessionId !== sessionId) {
              return thread
            }

            return {
              ...thread,
              messages: [...thread.messages, userMessage],
            }
          }),
        )

        const response = await sendFeedback(sessionId, composerText)
        const responseMessages = buildMessagesFromResponse(response, 'regeneration')

        setThreads((currentThreads) =>
          currentThreads.map((thread) => {
            if (thread.sessionId !== sessionId) {
              return thread
            }

            return {
              ...thread,
              messages: [...thread.messages, ...responseMessages],
              regenerationCount: response.regeneration_count,
            }
          }),
        )
      } else {
        const response = await startWorkflow(composerText, activeComposerMode === 'new-thread' ? referenceImageDataUrl : null)
        const responseMessages = buildMessagesFromResponse(response, 'initial')

        setThreads((currentThreads) => [
          ...currentThreads.filter((thread) => thread.sessionId !== activeSessionId),
          {
            sessionId: response.session_id,
            title: createThreadTitle(composerText, currentThreads.filter((thread) => thread.sessionId !== activeSessionId).length),
            messages: [userMessage, ...responseMessages],
            regenerationCount: response.regeneration_count,
            isDraft: false,
          },
        ])
        setActiveSessionId(response.session_id)
        clearReferenceImage()
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : activeComposerMode === 'feedback' ? 'Feedback request failed' : 'Generation failed')
    } finally {
      setLoading(false)
      setComposerText('')
    }
  }

  return (
    <div className="app-shell">
      <section className="hero-stack">
        <section className="hero-panel hero-outside">
          <div>
            <p className="eyebrow">Vizzy</p>
            <h1>Chat-first image workflow</h1>
            <p className="hero-copy">
              Intent, prompt refinement, image output, and feedback regeneration all stay in the same conversation.
            </p>
          </div>
          <div className="session-pill">
            <span>Active tab</span>
            <strong>{activeThread ? activeThread.title : 'No tab selected'}</strong>
          </div>
        </section>

        <section className="thread-tabs" aria-label="Session tabs">
          {threads.map((thread) => (
            <button
              type="button"
              key={thread.sessionId}
              className={thread.sessionId === activeSessionId ? 'thread-tab active' : 'thread-tab'}
              onClick={() => activateThread(thread.sessionId)}
            >
              <span>{thread.title}</span>
              <small>{thread.isDraft ? 'draft' : thread.sessionId.slice(0, 8)}</small>
            </button>
          ))}
        </section>
      </section>

      <div className="window-shell">
        <header className="window-bar" aria-label="Vizzy window chrome">
          <div className="window-controls" aria-hidden="true">
            <span />
            <span />
            <span />
          </div>
          <div className="window-title">Vizzy</div>
          <div className="task-pane">
            <div className="window-caption">Threaded image studio</div>
            <button className="primary-button task-pane-button" type="button" onClick={startDraftSession}>
              New session
            </button>
          </div>
        </header>

        <main className="chat-app">
          <section className="chat-timeline" aria-live="polite">
            {visibleMessages.map((message) => {
              if (message.kind === 'status') {
                return <StatusBubble key={message.id} title={message.title} description={message.description} />
              }

              if (message.kind === 'query' || message.kind === 'feedback') {
                return <QueryBubble key={message.id} role={message.role} content={message.content} />
              }

              if (message.kind === 'intent') {
                return <IntentBubble key={message.id} intent={message.intent} />
              }

              if (message.kind === 'prompt') {
                return <PromptBubble key={message.id} prompt={message.prompt} />
              }

              if (message.kind === 'image') {
                return (
                  <ImageBubble
                    key={message.id}
                    imageUrl={message.imageUrl}
                    imagePath={message.imagePath}
                    regenerationCount={message.regenerationCount}
                    note={message.note}
                  />
                )
              }

              return null
            })}

            {loading ? <StatusBubble title="Working on it" description="Vizzy is parsing your request and updating the active thread." /> : null}
            {error ? <StatusBubble title="Something blocked the flow" description={error} /> : null}
          </section>

          <section className="composer-grid">
            <form className="composer-card composer-card-merged" onSubmit={handleComposerSubmit}>
              <div className="composer-header">
                <div>
                  <div className="bubble-label">Composer</div>
                  <h2>{composerTitle}</h2>
                  <p className="composer-copy">{composerDescription}</p>
                </div>
              </div>

              {activeComposerMode === 'new-thread' && (
                <div className="reference-image-section">
                  <div className="reference-image-upload">
                    <label htmlFor="reference-image-input" className="reference-image-label">
                      📸 Reference Image (optional)
                    </label>
                    <input
                      id="reference-image-input"
                      type="file"
                      accept="image/*"
                      onChange={handleReferenceImageUpload}
                      className="reference-image-input"
                      disabled={loading}
                    />
                  </div>

                  {referenceImageDataUrl && (
                    <div className="reference-image-preview">
                      <div className="preview-header">
                        <span>Reference image</span>
                        <button
                          type="button"
                          className="ghost-button"
                          onClick={clearReferenceImage}
                          disabled={loading}
                        >
                          Remove
                        </button>
                      </div>
                      <img
                        src={referenceImageDataUrl}
                        alt="Reference"
                        className="preview-thumbnail"
                      />
                    </div>
                  )}
                </div>
              )}

              <textarea
                value={composerText}
                onChange={(event) => setComposerText(event.target.value)}
                rows={4}
                placeholder={
                  activeComposerMode === 'feedback'
                    ? 'Tell Vizzy what to change in this tab'
                    : 'Describe the image you want to generate'
                }
              />
              <div className="composer-footer">
                <span className="composer-hint">
                  {activeComposerMode === 'feedback'
                    ? 'This will append feedback to the current session tab.'
                    : 'This will create a fresh session tab and a new generation thread.'}
                </span>
                <button className="primary-button" type="submit" disabled={loading}>
                  {loading ? 'Working...' : submitLabel}
                </button>
              </div>
            </form>
          </section>
        </main>
      </div>
    </div>
  )
}
