import { useState, useRef, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import './index.css'

const SENDER_PRESETS = [
  { name: 'You', id: 'user_1', role: 'Group Organizer', color: '#6366f1', initial: 'Y' },
  { name: 'Alice', id: 'user_alice', role: 'Budget Conscious', color: '#06b6d4', initial: 'A' },
  { name: 'Bob', id: 'user_bob', role: 'Luxury Explorer', color: '#f59e0b', initial: 'B' },
  { name: 'Charlie', id: 'user_charlie', role: 'Food & Culture', color: '#ec4899', initial: 'C' }
]

const STARTER_PROMPTS = [
  {
    label: '🗺️ 3-Day Tokyo Itinerary',
    text: 'Create a 3-day geographically clustered itinerary for Tokyo'
  },
  {
    label: '🏨 Hotel in Shinjuku',
    text: 'Find a boutique hotel in Shinjuku, Tokyo with rating above 4.5'
  },
  { label: '✈️ Flights to Tokyo', text: 'Find flights from Singapore to Tokyo for next month' },
  {
    label: '💸 Split Dinner $150',
    text: 'Alice paid $150 for dinner, split it equally between Alice, Bob and You'
  },
  { label: '🔌 Active Skills', text: 'What skills and specialist capabilities do you have active?' }
]

export default function App() {
  const [messages, setMessages] = useState([
    {
      id: 'welcome',
      sender: 'RoamAI',
      isRoamAI: true,
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      text: "Hey group! I'm RoamAI. What are we planning?",
      buttons: []
    }
  ])
  const [currentSender, setCurrentSender] = useState(SENDER_PRESETS[0])
  const [inputValue, setInputValue] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [channelId] = useState(() => {
    const stored = sessionStorage.getItem('roamai-channel') || `web_${crypto.randomUUID()}`
    sessionStorage.setItem('roamai-channel', stored)
    return stored
  })
  const [addressBot, setAddressBot] = useState(true)
  const [listenerMode, setListenerMode] = useState('connecting')
  const [connectionError, setConnectionError] = useState('')
  const [waitingForReply, setWaitingForReply] = useState(false)
  const receivedSequence = useRef(0)
  const messagesScrollRef = useRef(null)
  const messagesEndRef = useRef(null)

  const scrollToBottom = () => {
    if (messagesScrollRef.current) {
      messagesScrollRef.current.scrollTo({
        top: messagesScrollRef.current.scrollHeight,
        behavior: 'smooth'
      })
    } else {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages, isLoading])

  useEffect(() => {
    let stopped = false
    let timer
    const controller = new AbortController()
    const receive = async () => {
      try {
        const response = await fetch(
          `/api/chat/messages?channel_id=${encodeURIComponent(channelId)}&after=${receivedSequence.current}`,
          { signal: controller.signal }
        )
        if (!response.ok) throw new Error(`Connection unavailable (${response.status})`)
        const data = await response.json()
        if (stopped) return
        setConnectionError('')
        setListenerMode(data.listener_mode)
        if (data.messages.length) {
          receivedSequence.current = data.messages.at(-1).sequence
          setWaitingForReply(false)
          setMessages((previous) => [
            ...previous,
            ...data.messages.map((message) => ({
              id: `server_${message.sequence}`,
              sender: 'RoamAI',
              isRoamAI: true,
              time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
              text: message.text,
              buttons: (message.buttons || []).flat(),
              toolCalls: message.tool_calls || []
            }))
          ])
        }
      } catch (error) {
        if (!stopped) setConnectionError(error.message)
      } finally {
        if (!stopped) timer = setTimeout(receive, 1500)
      }
    }
    receive()
    return () => {
      stopped = true
      clearTimeout(timer)
      controller.abort()
    }
  }, [channelId])

  const handleSendMessage = async (textToSend, callbackData = null) => {
    const text = (textToSend || inputValue).trim()
    if (!text || isLoading) return

    setInputValue('')
    const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })

    // Append user message
    const userMsg = {
      id: `usr_${Date.now()}`,
      sender: currentSender.name,
      senderColor: currentSender.color,
      initial: currentSender.initial,
      isRoamAI: false,
      time: timeStr,
      text: text
    }
    setMessages((prev) => [...prev, userMsg])
    setIsLoading(true)

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          channel_id: channelId,
          sender_name: currentSender.name,
          sender_id: currentSender.id,
          text: text,
          client_message_id: crypto.randomUUID(),
          is_bot_mentioned: addressBot,
          callback_data: callbackData
        })
      })

      if (!response.ok) throw new Error(`Request was not accepted (${response.status})`)
      setWaitingForReply(addressBot || Boolean(callbackData))
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          id: `err_${Date.now()}`,
          sender: 'RoamAI (System)',
          isRoamAI: true,
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          text: `⚠️ Network error connecting to RoamAI backend: ${err.message}`,
          buttons: []
        }
      ])
    } finally {
      setIsLoading(false)
    }
  }

  const handleButtonClick = (button) => {
    if (button.url) {
      window.open(button.url, '_blank', 'noopener,noreferrer')
    } else {
      handleSendMessage(button.label, button.id)
    }
  }

  return (
    <div className="app-container">
      {/* Header */}
      <header className="app-header">
        <div className="brand-section">
          <div className="brand-icon">🌍</div>
          <div>
            <div className="brand-name">RoamAI</div>
          </div>
          <span className="brand-tag">React + Vite</span>
        </div>
        <div className="header-status">
          <div className="status-badge">
            <span className="status-dot"></span>
            <span>Listener: {listenerMode}</span>
          </div>
          <div className="status-badge">
            <span>✈️ Travel MCP</span>
          </div>
          <div className="status-badge">
            <span>💾 Durable queue</span>
          </div>
        </div>
      </header>

      {/* Main Grid */}
      <main className="app-main">
        {/* Sidebar */}
        <aside className="app-sidebar">
          <div>
            <div className="sidebar-title">RoamAI Group Context</div>
            <div className="group-card">
              <div className="group-name">Group Planner</div>
            </div>
          </div>

          <div>
            <div className="sidebar-title">Simulate Speaking As</div>
            <div className="members-stack">
              {SENDER_PRESETS.map((member) => (
                <button
                  key={member.id}
                  className={`member-option ${currentSender.id === member.id ? 'active' : ''}`}
                  onClick={() => setCurrentSender(member)}
                >
                  <div
                    className="member-avatar"
                    style={{ background: member.color, color: '#fff' }}
                  >
                    {member.initial}
                  </div>
                  <div>
                    <div style={{ fontWeight: 600 }}>{member.name}</div>
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                      {member.role}
                    </div>
                  </div>
                </button>
              ))}
            </div>
          </div>

          <div>
            <div className="sidebar-title">Group Services</div>
            <div className="subagents-list">
              <div className="agent-tag">Conversation listener</div>
              <div className="agent-tag">Live discovery</div>
              <div className="agent-tag">Expense consent</div>
              <div className="agent-tag">Polls and reminders</div>
            </div>
          </div>
        </aside>

        {/* Chat Feed */}
        <section className="chat-workspace">
          <div className="messages-scroll" ref={messagesScrollRef}>
            {messages.map((msg) => (
              <div key={msg.id} className="message-row">
                <div
                  className="member-avatar"
                  style={{
                    background: msg.isRoamAI
                      ? 'linear-gradient(135deg, #10b981 0%, #06b6d4 100%)'
                      : msg.senderColor || '#6366f1',
                    color: msg.isRoamAI ? '#000' : '#fff'
                  }}
                >
                  {msg.isRoamAI ? '🌍' : msg.initial || msg.sender[0]}
                </div>
                <div className="msg-bubble-wrap">
                  <div className="msg-meta">
                    <span
                      className="msg-name"
                      style={{ color: msg.isRoamAI ? '#34d399' : msg.senderColor || '#818cf8' }}
                    >
                      {msg.sender}
                    </span>
                    <span className="msg-timestamp">{msg.time}</span>
                  </div>
                  <div className={`bubble ${msg.isRoamAI ? 'bubble-roamai' : 'bubble-user'}`}>
                    {msg.toolCalls && msg.toolCalls.length > 0 && (
                      <div className="tool-calls-header">
                        <span className="tool-pulse-dot"></span>
                        <span className="tool-calls-label">Live Tools Executed:</span>
                        <div className="tool-tags">
                          {msg.toolCalls.map((tc, idx) => (
                            <span key={idx} className="tool-pill" title={JSON.stringify(tc.args)}>
                              ⚡ {tc.name}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                    <div className="markdown-content">
                      <ReactMarkdown
                        remarkPlugins={[[remarkGfm, { singleTilde: false }]]}
                        components={{
                          a: ({ node, ...props }) => {
                            const isMap = props.href && (props.href.includes('google.com/maps') || props.href.includes('maps.google.com'))
                            return (
                              <a
                                {...props}
                                target="_blank"
                                rel="noopener noreferrer"
                                className={isMap ? 'map-location-link' : 'inline-link'}
                              />
                            )
                          }
                        }}
                      >
                        {msg.text}
                      </ReactMarkdown>
                    </div>
                  </div>
                  {msg.buttons && msg.buttons.length > 0 && (
                    <div className="buttons-row">
                      {msg.buttons.map((btn, idx) => (
                        <button
                          key={btn.id || idx}
                          className="action-btn"
                          onClick={() => handleButtonClick(btn)}
                        >
                          {btn.label}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}

            {(isLoading || waitingForReply) && (
              <div className="typing-row">
                <div className="spinner-pulse"></div>
                <span>{isLoading ? 'Sending...' : 'Request queued or processing...'}</span>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Quick Prompt Chips */}
          <div className="prompts-carousel">
            {STARTER_PROMPTS.map((prompt, idx) => (
              <button
                key={idx}
                className="prompt-chip"
                onClick={() => handleSendMessage(prompt.text)}
              >
                {prompt.label}
              </button>
            ))}
          </div>

          {/* Footer Input */}
          <div className="chat-footer">
            <label
              style={{ display: 'flex', gap: '8px', alignItems: 'center', marginBottom: '8px' }}
            >
              <input
                type="checkbox"
                checked={addressBot}
                onChange={(event) => setAddressBot(event.target.checked)}
              />
              Address RoamAI
            </label>
            {connectionError && <div role="alert">{connectionError}</div>}
            <div className="input-container">
              <input
                type="text"
                className="text-input"
                placeholder={`Speaking as ${currentSender.name} (type message or mention @roam)...`}
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleSendMessage()
                }}
                disabled={isLoading}
                autoFocus
              />
              <button
                className="submit-btn"
                onClick={() => handleSendMessage()}
                disabled={isLoading || !inputValue.trim()}
              >
                <span>Send</span>
                <span>↵</span>
              </button>
            </div>
          </div>
        </section>
      </main>
    </div>
  )
}
