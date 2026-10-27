import { useEffect, useRef, useState } from 'react'
import { sendSupportMessage } from '../services/supportApi.js'
import Icon from './Icon.jsx'

const SUGGESTIONS = [
  { icon: 'package', title: 'Where is my order?', prompt: 'Can you help me check the status of my order?' },
  { icon: 'arrow', title: 'Start a return', prompt: 'I would like to ask about returning an item.' },
  { icon: 'help', title: 'Refund question', prompt: 'I have a question about a refund.' },
]

export default function ChatPanel({ onCaseCreated }) {
  const [messages, setMessages] = useState([])
  const [question, setQuestion] = useState('')
  const [orderId, setOrderId] = useState('')
  const [conversationOrderId, setConversationOrderId] = useState('')
  const [customerEmail, setCustomerEmail] = useState('')
  const [isSending, setIsSending] = useState(false)
  const [isTakingLong, setIsTakingLong] = useState(false)
  const [error, setError] = useState('')
  const [retryPayload, setRetryPayload] = useState(null)
  const [detailsOpen, setDetailsOpen] = useState(false)
  const messagesEndRef = useRef(null)
  const questionRef = useRef(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isSending])

  useEffect(() => {
    if (!isSending) return undefined

    const timer = window.setTimeout(() => setIsTakingLong(true), 8000)
    return () => window.clearTimeout(timer)
  }, [isSending])

  async function sendQuestion(payload, isRetry = false) {
    if (!payload.question || isSending) return

    if (!isRetry) {
      const userMessage = {
        id: crypto.randomUUID(),
        role: 'customer',
        text: payload.question,
        createdAt: new Date().toISOString(),
      }
      setMessages((current) => [...current, userMessage])
    }
    setQuestion('')
    setError('')
    setIsTakingLong(false)
    setIsSending(true)

    try {
      const result = await sendSupportMessage({
        question: payload.question,
        orderId: payload.orderId,
        customerEmail: payload.customerEmail,
        idempotencyKey: payload.idempotencyKey,
      })
      const assistantMessage = {
        id: crypto.randomUUID(),
        role: 'assistant',
        text: result.answer,
        status: result.status,
        responseSource: result.response_source,
        approvalRequired: result.approval_required,
        createdAt: new Date().toISOString(),
      }
      setMessages((current) => [...current, assistantMessage])
      setRetryPayload(null)
      if (result.case_id) {
        onCaseCreated({
          case_id: result.case_id,
          thread_id: result.thread_id,
          status: result.status,
          answer: result.answer,
          approval_required: result.approval_required,
          ticket_id: result.ticket_id,
          created_at: assistantMessage.createdAt,
        })
      }
    } catch (requestError) {
      setError(requestError.message || 'We could not send your message. Please try again.')
      setRetryPayload(payload)
    } finally {
      setIsSending(false)
      questionRef.current?.focus()
    }
  }

  function submitMessage(event) {
    event?.preventDefault()
    const cleanQuestion = question.trim()
    if (!cleanQuestion) return
    const mentionedOrderId = cleanQuestion.match(/\bORD\d+\b/i)?.[0] || ''
    const activeOrderId = orderId.trim() || mentionedOrderId || conversationOrderId
    if (activeOrderId) setConversationOrderId(activeOrderId)
    void sendQuestion({
      question: cleanQuestion,
      orderId: activeOrderId,
      customerEmail: customerEmail.trim(),
      idempotencyKey: crypto.randomUUID(),
    })
  }

  function retryLastMessage() {
    if (retryPayload) void sendQuestion(retryPayload, true)
  }

  function selectSuggestion(prompt) {
    setQuestion(prompt)
    questionRef.current?.focus()
  }

  return (
    <section className="chat-page">
      <div className="chat-heading">
        <div>
          <div className="eyebrow"><span className="status-dot" /> CUSTOMER CARE</div>
          <h1>How can we help?</h1>
          <p className="page-intro">Get answers, track a request, or talk to our support assistant.</p>
        </div>
        <div className="response-time">
          <div className="response-icon"><Icon name="clock" size={17} /></div>
          <div><strong>Here to help</strong><span>AI-assisted support</span></div>
        </div>
      </div>

      <div className="chat-layout">
        <div className="chat-main-card">
          <div className="conversation-header">
            <div className="assistant-avatar"><Icon name="sparkles" size={18} /></div>
            <div className="conversation-agent">
              <strong>Kindred Support</strong>
              <span><i /> AI-assisted support</span>
            </div>
            <button
              className="details-toggle"
              type="button"
              onClick={() => setDetailsOpen((open) => !open)}
              aria-expanded={detailsOpen}
            >
              <Icon name="plus" size={16} /> Add details
            </button>
          </div>

          {detailsOpen && (
            <div className="chat-details">
              <label>
                Order ID <span>Optional</span>
                <input
                  value={orderId}
                  onChange={(event) => setOrderId(event.target.value)}
                  placeholder="For example, ORD1001"
                  maxLength={100}
                />
              </label>
              <label>
                Email for updates <span>Optional</span>
                <input
                  type="email"
                  value={customerEmail}
                  onChange={(event) => setCustomerEmail(event.target.value)}
                  placeholder="you@example.com"
                  maxLength={254}
                />
              </label>
            </div>
          )}

          <div className={`conversation-body${messages.length ? ' conversation-active' : ''}`}>
            {messages.length === 0 ? (
              <div className="welcome-state">
                <div className="welcome-orb"><Icon name="sparkles" size={24} /></div>
                <span className="welcome-kicker">A LITTLE HELP, RIGHT AWAY</span>
                <h2>Hi there. What can we<br className="desktop-break" /> help you with?</h2>
                <p>Ask us anything about an order, returns, or refunds.<br className="desktop-break" /> We’ll figure it out together.</p>
                <div className="suggestion-grid">
                  {SUGGESTIONS.map((suggestion) => (
                    <button
                      className="suggestion-card"
                      key={suggestion.title}
                      type="button"
                      onClick={() => selectSuggestion(suggestion.prompt)}
                    >
                      <span className="suggestion-icon"><Icon name={suggestion.icon} size={17} /></span>
                      <span>{suggestion.title}</span>
                      <Icon name="chevron" size={15} />
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <div className="message-list" aria-live="polite">
                {messages.map((message) => (
                  <article
                    className={`message-row message-${message.role}`}
                    key={message.id}
                  >
                    {message.role === 'assistant' && (
                      <div className="message-avatar"><Icon name="sparkles" size={14} /></div>
                    )}
                    <div className="message-content">
                      <div className="message-meta">
                        {message.role === 'customer' ? 'You' : 'Kindred Support'}
                        {message.status && <span className="message-status">{message.status.replaceAll('_', ' ')}</span>}
                        {message.responseSource && (
                          <span className="message-status">
                            {message.responseSource === 'gemini' ? 'Gemini' : 'Local workflow'}
                          </span>
                        )}
                      </div>
                      <div className="message-bubble">{message.text}</div>
                      {message.approvalRequired && (
                        <div className="approval-note">
                          <Icon name="clock" size={14} />
                          Your request is waiting for a support team review.
                        </div>
                      )}
                    </div>
                  </article>
                ))}
                {isSending && (
                  <div className="message-row message-assistant" role="status" aria-label="Assistant is replying">
                    <div className="message-avatar"><Icon name="sparkles" size={14} /></div>
                    <div className="message-content">
                      <div className="message-meta">Kindred Support</div>
                      <div className="message-bubble typing-bubble">
                        <span /><span /><span />
                      </div>
                      {isTakingLong && (
                        <p className="response-wait-hint">
                          Still checking the request and policy. This can take a little longer on a first reply.
                        </p>
                      )}
                    </div>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>
            )}
          </div>

          {error && (
            <div className="error-banner" role="alert">
              <Icon name="info" size={17} />
              <span>{error}</span>
              <button type="button" onClick={retryLastMessage} disabled={isSending || !retryPayload}>
                Try again
              </button>
            </div>
          )}

          <form className="composer" onSubmit={submitMessage}>
            <label className="sr-only" htmlFor="support-message">Your message</label>
            <textarea
              id="support-message"
              ref={questionRef}
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && !event.shiftKey) {
                  event.preventDefault()
                  submitMessage()
                }
              }}
              placeholder="Write a message..."
              maxLength={1500}
              rows={1}
              disabled={isSending}
            />
            <div className="composer-bottom">
              <div className="composer-hint">
                <Icon name="shield" size={14} />
                Your details stay private
                {question.length > 1100 && <span className="character-count">{question.length}/1500</span>}
              </div>
              <button
                className="send-button"
                type="submit"
                disabled={isSending || !question.trim()}
                aria-label="Send message"
              >
                {isSending ? 'Sending' : 'Send'}
                <Icon name="send" size={15} />
              </button>
            </div>
          </form>
          <p className="chat-disclaimer">
            Support responses are AI-assisted. Important actions may need a team member to review.
          </p>
        </div>

        <aside className="chat-aside">
          <div className="aside-card quick-help-card">
            <div className="aside-card-heading"><span className="aside-heading-icon"><Icon name="sparkles" size={16} /></span> QUICK HELP</div>
            <h3>Good to know</h3>
            <p>Have your order number ready so we can look into things faster.</p>
            <button type="button" className="text-action" onClick={() => setDetailsOpen(true)}>
              Add an order number <Icon name="arrow" size={14} />
            </button>
          </div>
          <div className="aside-card policy-card">
            <div className="aside-card-heading"><span className="policy-shield"><Icon name="shield" size={16} /></span> OUR PROMISE</div>
            <h3>People come first.</h3>
            <p>We’ll never approve a refund without checking the details and our policy.</p>
            <div className="policy-card-footer"><span className="tiny-check">✓</span> Thoughtful support, always</div>
          </div>
          <div className="aside-contact">
            <div className="contact-avatar"><Icon name="help" size={17} /></div>
            <div><strong>Rather talk to a person?</strong><span>Ask for a human review in chat.</span></div>
          </div>
        </aside>
      </div>
    </section>
  )
}
