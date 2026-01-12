import { useState, useRef, useEffect } from 'react'
import { Search, Calendar } from 'lucide-react'
import ReactMarkdown from 'react-markdown'

function App() {
  const [query, setQuery] = useState('')
  const [messages, setMessages] = useState<{role: 'user'|'ai', content: string}[]>([])
  const [sources, setSources] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [streaming, setStreaming] = useState(false)
  const chatEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

  const handleSearch = async () => {
    if (!query.trim()) return
    setLoading(true)
    setMessages(prev => [...prev, {role: 'user', content: query}])
    const currentQuery = query
    setQuery('') // Clear input
    
    // 1. Search (Fetch sources)
    try {
      const res = await fetch('http://localhost:8000/api/search', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({query: currentQuery})
      })
      const data = await res.json()
      setSources(data.results || [])
      
      // 2. Chat (Stream)
      setStreaming(true)
      setMessages(prev => [...prev, {role: 'ai', content: ''}])
      
      const chatRes = await fetch('http://localhost:8000/api/chat', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({query: currentQuery})
      })
      
      const reader = chatRes.body?.getReader()
      const decoder = new TextDecoder()
      
      if (reader) {
        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          const chunk = decoder.decode(value)
          setMessages(prev => {
            const newMsgs = [...prev]
            const last = newMsgs[newMsgs.length - 1]
            newMsgs[newMsgs.length - 1] = {...last, content: last.content + chunk}
            return newMsgs
          })
        }
      }
    } catch (e) {
      console.error(e)
      setMessages(prev => [...prev, {role: 'ai', content: "Error: Failed to fetch response."}])
    } finally {
      setLoading(false)
      setStreaming(false)
    }
  }

  return (
    <div className="h-screen bg-gray-50 flex flex-col overflow-hidden">
      <header className="bg-white border-b p-4 shadow-sm z-10">
        <h1 className="text-xl font-bold text-gray-800">Bristol Campus RAG</h1>
      </header>
      
      <div className="flex-1 flex overflow-hidden">
        {/* Sidebar Filters */}
        <aside className="w-64 bg-white border-r p-4 hidden md:block overflow-y-auto">
          <h2 className="font-semibold mb-4 text-gray-700">Filters</h2>
          <div className="space-y-4">
             <p className="text-sm text-gray-500">Date filtering has been automated by the AI assistant.</p>
          </div>
        </aside>

        {/* Main Content */}
        <div className="flex-1 flex flex-col relative">
          
          <div className="flex-1 flex gap-4 overflow-hidden p-4">
            {/* Chat Area */}
            <div className="flex-1 flex flex-col bg-white rounded-lg border shadow-sm overflow-hidden">
              <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {messages.length === 0 && (
                  <div className="text-center text-gray-400 mt-20">
                    <p className="text-lg font-medium">How can I help you today?</p>
                    <p className="text-sm">Ask about exam schedules, campus events, or administrative notices.</p>
                  </div>
                )}
                {messages.map((msg, i) => (
                  <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                    <div className={`max-w-[85%] rounded-lg p-3 prose prose-sm ${msg.role === 'user' ? 'bg-blue-600 text-white prose-invert' : 'bg-gray-100 text-gray-800'}`}>
                      <ReactMarkdown>{msg.content}</ReactMarkdown>
                    </div>
                  </div>
                ))}
                <div ref={chatEndRef} />
              </div>

              {/* Input Area */}
              <div className="p-4 border-t bg-gray-50">
                <div className="flex gap-2">
                  <input 
                    className="flex-1 border rounded-lg px-4 py-3 focus:ring-2 focus:ring-blue-500 outline-none shadow-sm"
                    placeholder="Ask about campus notifications..."
                    value={query}
                    onChange={e => setQuery(e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && handleSearch()}
                    disabled={loading || streaming}
                  />
                  <button 
                    onClick={handleSearch}
                    disabled={loading || streaming || !query.trim()}
                    className="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50 flex items-center gap-2 font-medium transition-colors"
                  >
                    {loading ? '...' : <Search className="w-5 h-5"/>}
                  </button>
                </div>
              </div>
            </div>

            {/* Source Cards (Right Panel) */}
            <div className="w-80 bg-gray-50 rounded-lg border p-4 overflow-y-auto hidden lg:flex flex-col">
              <h3 className="font-semibold mb-3 text-gray-700 sticky top-0 bg-gray-50 pb-2 border-b">References</h3>
              <div className="space-y-3 flex-1">
                {sources.map((source, i) => (
                  <div key={i} className="bg-white p-3 rounded border shadow-sm hover:shadow-md transition-all hover:-translate-y-0.5 cursor-pointer group">
                    <div className="flex justify-between items-start mb-1">
                      <span className="bg-blue-100 text-blue-800 text-xs px-2 py-0.5 rounded-full font-mono">[{i+1}]</span>
                      <span className="text-xs text-gray-400">{source.date || 'No Date'}</span>
                    </div>
                    <a href={source.metadata?.url} target="_blank" className="text-sm font-medium text-blue-600 group-hover:underline block mb-1 leading-tight">
                      {source.metadata?.title || 'Untitled Notification'}
                    </a>
                    <p className="text-xs text-gray-500 line-clamp-3">
                      {source.content}
                    </p>
                    <div className="mt-2 flex items-center gap-1">
                       <div className="h-1 bg-gray-200 rounded-full flex-1 overflow-hidden">
                          <div className="h-full bg-green-500" style={{width: `${Math.min((source.score || 0) * 100, 100)}%`}}></div>
                       </div>
                       <span className="text-[10px] text-gray-400">{(source.score || 0).toFixed(2)}</span>
                    </div>
                  </div>
                ))}
                {sources.length === 0 && (
                  <div className="text-center py-10 text-gray-400">
                    <p className="text-sm">References will appear here after search.</p>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default App
