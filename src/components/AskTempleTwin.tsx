import { useState, type FormEvent } from 'react'
import { askTempleTwin } from '../services/api'

type Props = {
  buildingSlug?: string | null
  date: string | null
  hour: number
  suggestedPrompts: string[]
}

export function AskTempleTwin({
  buildingSlug = null,
  date,
  hour,
  suggestedPrompts,
}: Props) {
  const [isOpen, setIsOpen] = useState(false)
  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isSending, setIsSending] = useState(false)

  const submitQuestion = async (event?: FormEvent) => {
    event?.preventDefault()
    const trimmed = question.trim()
    if (!trimmed || !date || isSending) return

    setIsSending(true)
    setError(null)
    try {
      const response = await askTempleTwin(trimmed, {
        buildingSlug,
        date,
        hour,
      })
      setAnswer(response.answer)
    } catch (err) {
      console.error('Ask Temple Twin request failed:', err)
      setAnswer(null)
      setError('Ask Temple Twin is temporarily unavailable.')
    } finally {
      setIsSending(false)
    }
  }

  const choosePrompt = (prompt: string) => {
    setQuestion(prompt)
    setAnswer(null)
    setError(null)
  }

  return (
    <section className="ask-twin">
      <button
        type="button"
        className="ask-twin-toggle"
        aria-expanded={isOpen}
        onClick={() => setIsOpen((open) => !open)}
      >
        <span>
          <strong>Ask Temple Twin</strong>
          <small>{buildingSlug ? 'About this building' : 'About the campus'}</small>
        </span>
        <span className="ask-twin-chevron" aria-hidden="true">{isOpen ? '−' : '+'}</span>
      </button>

      {isOpen && (
        <div className="ask-twin-body">
          <div className="ask-twin-prompts" aria-label="Suggested questions">
            {suggestedPrompts.map((prompt) => (
              <button type="button" key={prompt} onClick={() => choosePrompt(prompt)}>
                {prompt}
              </button>
            ))}
          </div>

          <div className="ask-twin-response">
            {answer && <div className="ask-twin-answer">{answer}</div>}
            {error && <div className="ask-twin-error">{error}</div>}
          </div>

          <form className="ask-twin-form" onSubmit={(event) => void submitQuestion(event)}>
            <input
              type="text"
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="Ask about energy use…"
              aria-label="Ask Temple Twin"
              disabled={!date || isSending}
            />
            <button
              type="submit"
              aria-label="Send question"
              disabled={!question.trim() || !date || isSending}
            >
              {isSending ? '…' : '→'}
            </button>
          </form>
        </div>
      )}
    </section>
  )
}
