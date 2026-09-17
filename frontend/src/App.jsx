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
  { label: '🗺️ 3-Day Tokyo Itinerary', text: 'Create a 3-day geographically clustered itinerary for Tokyo' },
  { label: '🏨 Hotel in Shinjuku', text: 'Find a boutique hotel in Shinjuku, Tokyo with rating above 4.5' },
  { label: '✈️ Flights to Tokyo', text: 'Find flights from Singapore to Tokyo for next month' },
  { label: '💸 Split Dinner $150', text: 'Alice paid $150 for dinner, split it equally between Alice, Bob and You' },
  { label: '🔌 Active Skills', text: 'What skills and specialist capabilities do you have active?' }
]

export default function App() {
  const [messages, setMessages] = useState([
    {
      id: 'welcome',
      sender: 'RoamAI Ambient Concierge',
      isRoamAI: true,
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      text: "Hey group! 🌍 I'm your ambient concierge. I passively listen in this group chat and step in whenever summoned, or when you need travel booking, itineraries, or expense debt simplification.\n\nTry sending a message or click any prompt below!",
      buttons: []
    }
  ])
  const [currentSender, setCurrentSender] = useState(SENDER_PRESETS[0])
  const [inputValue, setInputValue] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [channelId] = useState('group_tokyo_summer')
  const messagesEndRef = useRef(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages, isLoading])

  const handleSendMessage = async (textToSend) => {
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
          text: text
        })
      })

      const data = await response.json()
      if (data && data.output) {
        const aiMsg = {
          id: `ai_${Date.now()}`,
          sender: 'RoamAI Ambient Concierge',
          isRoamAI: true,
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          text: data.output,
          buttons: data.buttons ? data.buttons.flat() : []
        }
        setMessages((prev) => [...prev, aiMsg])
      }
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
      window.open(button.url, '_blank')
    } else {
      handleSendMessage(button.label)
    }
  }

  return (
    <div className="app-container">
      {/* Header */}
      <header className="app-header">
        <div className="brand-section">
          <div className="brand-icon">🌍</div>
          <div>
            <div className="brand-name">RoamAI Group Concierge</div>
          </div>
          <span className="brand-tag">React + Vite</span>
        </div>
        <div className="header-status">
          <div className="status-badge">
            <span className="status-dot"></span>
            <span>Gemini Flash Active</span>
          </div>
          <div className="status-badge">
            <span>✈️ Travel MCP</span>
          </div>
          <div className="status-badge">
            <span>💾 SQLite Sliding Window</span>
          </div>
        </div>
      </header>

      {/* Main Grid */}
      <main className="app-main">
        {/* Sidebar */}
        <aside className="app-sidebar">
          <div>
            <div className="sidebar-title">Ambient Group Context</div>
            <div className="group-card">
              <div className="group-name">🏖️ Tokyo Summer Getaway</div>
              <div className="group-subtext">
                RoamAI silently arbitrates constraints and synthesizes plans when summoned.
              </div>
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
                  <div className="member-avatar" style={{ background: member.color, color: '#fff' }}>
                    {member.initial}
                  </div>
                  <div>
                    <div style={{ fontWeight: 600 }}>{member.name}</div>
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{member.role}</div>
                  </div>
                </button>
              ))}
            </div>
          </div>

          <div>
            <div className="sidebar-title">Specialist Subagents</div>
            <div className="subagents-list">
              <div className="agent-tag">✈️ travel_specialist (Flights & Hotels)</div>
              <div className="agent-tag">💸 expense_specialist (Debt Simplifier)</div>
              <div className="agent-tag">📸 vision_specialist (Landmarks & OCR)</div>
              <div className="agent-tag">⏰ proactive_concierge (State Machine)</div>
              <div className="agent-tag">🔌 skill_specialist (Dynamic MCP)</div>
            </div>
          </div>
        </aside>

        {/* Chat Feed */}
        <section className="chat-workspace">
          <div className="messages-scroll">
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
                    <div className="markdown-content">
                      <ReactMarkdown remarkPlugins={[[remarkGfm, { singleTilde: false }]]}>
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

            {isLoading && (
              <div className="typing-row">
                <div className="spinner-pulse"></div>
                <span>RoamAI is thinking and querying tools...</span>
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
