import { useState } from 'react'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000'

function App() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [threadId, setThreadId] = useState(null)
  const [awaitingClarification, setAwaitingClarification] = useState(false)
  const [loading, setLoading] = useState(false)

  const [showConnectionForm, setShowConnectionForm] = useState(false)
  const [dbUrl, setDbUrl] = useState('')
  const [readonlyDbUrl, setReadonlyDbUrl] = useState('')
  const [connected, setConnected] = useState(false)

  function handleConnect() {
    if (!dbUrl.trim()) return
    setConnected(true)
    setShowConnectionForm(false)
    setMessages([])
    setThreadId(null)
    setAwaitingClarification(false)
  }

  function handleDisconnect() {
    setDbUrl('')
    setReadonlyDbUrl('')
    setConnected(false)
    setMessages([])
    setThreadId(null)
    setAwaitingClarification(false)
  }

  async function handleSend() {
    if (!input.trim() || loading) return

    const userText = input
    setMessages((prev) => [...prev, { role: 'user', text: userText }])
    setInput('')
    setLoading(true)

    try {
      let response

      if (awaitingClarification && threadId) {
        response = await fetch(`${API_BASE}/resume`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ thread_id: threadId, answer: userText }),
        })
      } else {
        const body = { question: userText }
        if (connected && dbUrl.trim()) body.db_url = dbUrl
        if (connected && readonlyDbUrl.trim()) body.readonly_db_url = readonlyDbUrl

        response = await fetch(`${API_BASE}/query`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        })
      }

      const data = await response.json()

      if (!response.ok) {
        setMessages((prev) => [...prev, { role: 'assistant', text: data.detail || 'Request failed.' }])
        setLoading(false)
        return
      }

      setThreadId(data.thread_id)

      if (data.status === 'clarification_needed') {
        setAwaitingClarification(true)
        setMessages((prev) => [...prev, { role: 'assistant', text: data.clarification_question }])
      } else {
        setAwaitingClarification(false)
        setMessages((prev) => [
          ...prev,
          { role: 'assistant', text: data.final_answer, sql: data.sql },
        ])
      }
    } catch (err) {
      setMessages((prev) => [...prev, { role: 'assistant', text: 'Something went wrong. Is the backend running?' }])
    } finally {
      setLoading(false)
    }
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter') handleSend()
  }

  return (
    <div className="min-h-screen flex flex-col text-[var(--text)]">
      <header className="border-b border-[var(--border)] bg-[var(--surface)]/80 backdrop-blur px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-2 h-2 bg-[var(--accent)]" />
          <h1 className="text-sm font-semibold tracking-wide uppercase">Text-to-SQL</h1>
        </div>

        <div className="flex items-center gap-4">
          <span className="text-xs text-[var(--text-muted)] font-mono-data">
            {connected ? 'custom db · connected' : 'chinook.db · connected'}
          </span>
          {connected ? (
            <button
              onClick={handleDisconnect}
              className="text-xs border border-[var(--border)] px-3 py-1.5 hover:border-[var(--accent)] transition-colors"
            >
              Disconnect
            </button>
          ) : (
            <button
              onClick={() => setShowConnectionForm(!showConnectionForm)}
              className="text-xs border border-[var(--border)] px-3 py-1.5 hover:border-[var(--accent)] transition-colors"
            >
              Connect your database
            </button>
          )}
        </div>
      </header>

      {showConnectionForm && (
        <div className="border-b border-[var(--border)] bg-[var(--surface)] px-6 py-4">
          <div className="max-w-3xl mx-auto space-y-3">
            <div>
              <label className="text-xs text-[var(--text-muted)] font-mono-data block mb-1">
                db_url (required)
              </label>
              <input
                className="w-full bg-[var(--bg)] border border-[var(--border)] px-3 py-2 text-sm outline-none focus:border-[var(--accent)] transition-colors font-mono-data"
                value={dbUrl}
                onChange={(e) => setDbUrl(e.target.value)}
                placeholder="postgresql://user:pass@host:5432/dbname"
              />
            </div>
            <div>
              <label className="text-xs text-[var(--text-muted)] font-mono-data block mb-1">
                readonly_db_url (optional — leave blank to generate SQL without running it)
              </label>
              <input
                className="w-full bg-[var(--bg)] border border-[var(--border)] px-3 py-2 text-sm outline-none focus:border-[var(--accent)] transition-colors font-mono-data"
                value={readonlyDbUrl}
                onChange={(e) => setReadonlyDbUrl(e.target.value)}
                placeholder="postgresql://readonly_user:pass@host:5432/dbname"
              />
            </div>
            <button
              onClick={handleConnect}
              className="bg-[var(--accent)] text-[var(--bg)] px-4 py-2 text-sm font-semibold hover:bg-[var(--accent-dim)] hover:text-[var(--text)] transition-colors"
            >
              Connect
            </button>
          </div>
        </div>
      )}

      <div className="flex-1 overflow-y-auto px-6 py-6 max-w-3xl w-full mx-auto space-y-5">
        {messages.length === 0 && (
          <div className="text-[var(--text-muted)] text-sm mt-20 text-center">
            Ask a question about the database to get started.
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className="flex gap-3 items-start">
            <span
              className={`font-mono-data text-xs mt-1 shrink-0 ${
                msg.role === 'user' ? 'text-[var(--text-muted)]' : 'text-[var(--accent)]'
              }`}
            >
              {msg.role === 'user' ? '$' : '›'}
            </span>
            <div className="flex-1">
              <div className="text-sm leading-relaxed">{msg.text}</div>
              {msg.sql && (
                <pre className="mt-2 bg-[var(--surface)] border border-[var(--border)] px-3 py-2 text-xs font-mono-data text-[var(--text-muted)] whitespace-pre-wrap break-words">
                  {msg.sql}
                </pre>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex gap-3 items-start">
            <span className="text-[var(--accent)] font-mono-data text-xs mt-1">›</span>
            <div className="text-sm text-[var(--text-muted)]">thinking...</div>
          </div>
        )}
      </div>

      <div className="border-t border-[var(--border)] bg-[var(--surface)]/80 backdrop-blur px-6 py-4">
        <div className="max-w-3xl mx-auto flex gap-2">
          <input
            className="flex-1 bg-[var(--bg)] border border-[var(--border)] px-4 py-3 text-sm outline-none focus:border-[var(--accent)] transition-colors font-mono-data"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={awaitingClarification ? 'Type your answer...' : 'Which artist has the most albums?'}
            disabled={loading}
          />
          <button
            className="bg-[var(--accent)] text-[var(--bg)] px-5 py-3 text-sm font-semibold hover:bg-[var(--accent-dim)] hover:text-[var(--text)] transition-colors disabled:opacity-50"
            onClick={handleSend}
            disabled={loading}
          >
            Run
          </button>
        </div>
      </div>
    </div>
  )
}

export default App