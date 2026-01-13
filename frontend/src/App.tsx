import { useState, useRef, useEffect } from 'react'
import { Search, Moon, Sun, Menu, X, Clock, Loader2, ArrowRight, Copy, Share2, ExternalLink, MessageSquare, BookOpen } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import clsx from 'clsx'
import logo from './assets/logo.png'

interface SourceMetadata {
  title?: string;
  url?: string;
  [key: string]: unknown;
}

interface SourceDoc {
  id: number;
  content: string;
  metadata: SourceMetadata;
  score?: number;
  date?: string;
}

interface SearchHit {
  id?: string;
  content: string;
  metadata: SourceMetadata;
  date?: string;
  score?: number;
}

interface Message {
  role: 'user' | 'ai';
  content: string;
  sources?: SourceDoc[];
}

interface StepStatus {
  id: string;
  label: string;
  status: 'pending' | 'loading' | 'completed';
}

const isSourceDocArray = (value: unknown): value is SourceDoc[] => {
  if (!Array.isArray(value)) return false
  return value.every((item) => {
    if (typeof item !== 'object' || item === null) return false
    const obj = item as Record<string, unknown>
    return typeof obj.id === 'number' && typeof obj.content === 'string' && typeof obj.metadata === 'object' && obj.metadata !== null
  })
}

const SourcePreview = ({ source }: { source: SourceDoc }) => {
  const [showFull, setShowFull] = useState(false)
  const timerRef = useRef<number | null>(null)

  const handleMouseEnter = () => {
    timerRef.current = setTimeout(() => {
      setShowFull(true)
    }, 1000)
  }

  const handleMouseLeave = () => {
    if (timerRef.current !== null) clearTimeout(timerRef.current)
    setShowFull(false)
  }

  return (
    <div 
      className="relative group border border-brand-100 dark:border-brand-800 rounded-lg bg-brand-50/50 dark:bg-brand-900/20 p-2 mb-2 transition-all hover:bg-brand-50 dark:hover:bg-brand-900/40"
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      <div className="text-xs text-brand-600 dark:text-brand-400 font-medium flex items-center gap-2">
         <span className="bg-brand-200 dark:bg-brand-800 text-brand-800 dark:text-brand-200 px-1.5 py-0.5 rounded text-[10px]">Doc {source.id}</span>
         <span className="text-gray-500 dark:text-gray-400 truncate max-w-[150px]">{source.metadata.title ?? ''}</span>
      </div>
      <div className="text-sm text-gray-700 dark:text-gray-300 mt-1 cursor-help transition-all">
        {showFull ? (
           <div className="absolute left-0 bottom-full mb-2 p-3 bg-white dark:bg-slate-800 border border-brand-100 dark:border-slate-700 rounded-xl shadow-card w-64 z-50 animate-fade-in-up">
             <div className="text-xs text-gray-500 dark:text-gray-400 mb-1 font-semibold">Full Content Preview:</div>
             <div className="max-h-48 overflow-y-auto text-xs leading-relaxed text-gray-700 dark:text-gray-300">
               {source.content}
             </div>
           </div>
        ) : (
           <span className="opacity-80 hover:opacity-100">{source.content.slice(0, 40)}...</span>
        )}
      </div>
    </div>
  )
}

interface HistorySession {
  id: string;
  title: string;
  timestamp: number;
  messages: Message[];
}

const SourceModal = ({ 
  isOpen, 
  onClose, 
  source 
}: { 
  isOpen: boolean; 
  onClose: () => void; 
  source: SourceDoc | null 
}) => {
  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    if (isOpen) {
      window.addEventListener('keydown', handleEsc)
    }
    return () => window.removeEventListener('keydown', handleEsc)
  }, [isOpen, onClose])

  if (!isOpen || !source) return null

  const handleCopy = () => {
    navigator.clipboard.writeText(source.content)
  }

  const handleShare = async () => {
    if (navigator.share) {
      try {
        await navigator.share({
          title: source.metadata.title || 'Source Document',
          text: source.content.slice(0, 100) + '...',
          url: (source.metadata.url as string) || window.location.href
        })
      } catch (err) {
        // Ignore abort errors or logging
      }
    } else {
      handleCopy()
    }
  }

  return (
    <div 
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-in fade-in duration-200"
      onClick={onClose}
    >
      <div 
        className="bg-white dark:bg-slate-900 rounded-2xl shadow-2xl w-full max-w-2xl max-h-[80vh] flex flex-col border border-gray-200 dark:border-slate-800 animate-in zoom-in-95 duration-200"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="p-4 border-b border-gray-100 dark:border-slate-800 flex justify-between items-center bg-gray-50/50 dark:bg-slate-900/50 rounded-t-2xl">
          <div className="flex items-center gap-2">
            <span className="bg-brand-100 dark:bg-brand-900 text-brand-600 dark:text-brand-300 px-2 py-0.5 rounded text-xs font-mono font-medium">
              Doc {source.id}
            </span>
            <h3 className="font-semibold text-gray-800 dark:text-slate-200 truncate max-w-md">
              {source.metadata.title || 'Untitled Document'}
            </h3>
          </div>
          <button 
            onClick={onClose}
            className="p-2 hover:bg-gray-200 dark:hover:bg-slate-800 rounded-full transition-colors text-gray-500"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 custom-scrollbar">
          <div className="prose prose-sm dark:prose-invert max-w-none">
            <p className="text-gray-600 dark:text-gray-300 whitespace-pre-wrap leading-relaxed">
              {source.content}
            </p>
          </div>
          
          {/* Metadata Grid */}
          <div className="mt-6 pt-6 border-t border-gray-100 dark:border-slate-800 grid grid-cols-2 gap-4">
            <div>
              <span className="text-xs text-gray-400 uppercase font-semibold tracking-wider block mb-1">Date</span>
              <span className="text-sm text-gray-700 dark:text-gray-300">
                {String(source.metadata.date || 'Unknown')}
              </span>
            </div>
            <div>
              <span className="text-xs text-gray-400 uppercase font-semibold tracking-wider block mb-1">Source URL</span>
              <a 
                href={String(source.metadata.url || '#')} 
                target="_blank" 
                rel="noreferrer"
                className="text-sm text-brand-500 hover:underline flex items-center gap-1 truncate"
              >
                {String(source.metadata.url || 'No URL')}
                <ExternalLink className="w-3 h-3" />
              </a>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-gray-100 dark:border-slate-800 bg-gray-50/50 dark:bg-slate-900/50 rounded-b-2xl flex justify-end gap-2">
          <button 
            onClick={handleCopy}
            className="flex items-center gap-2 px-4 py-2 bg-white dark:bg-slate-800 border border-gray-200 dark:border-slate-700 rounded-lg hover:bg-gray-50 dark:hover:bg-slate-700 text-sm font-medium text-gray-700 dark:text-gray-300 transition-colors shadow-sm"
          >
            <Copy className="w-4 h-4" />
            Copy Content
          </button>
          <button 
            onClick={handleShare}
            className="flex items-center gap-2 px-4 py-2 bg-brand-500 text-white rounded-lg hover:bg-brand-600 transition-colors text-sm font-medium shadow-lg shadow-brand-500/20"
          >
            <Share2 className="w-4 h-4" />
            Share
          </button>
        </div>
      </div>
    </div>
  )
}

function App() {
  const [query, setQuery] = useState('')
  const [messages, setMessages] = useState<Message[]>([])
  const [sources, setSources] = useState<SearchHit[]>([])
  const [loading, setLoading] = useState(false)
  const [streaming, setStreaming] = useState(false)
  const chatEndRef = useRef<HTMLDivElement>(null)
  const [isSidebarOpen, setIsSidebarOpen] = useState(false)
  const [isDarkMode, setIsDarkMode] = useState(false)
  const [steps, setSteps] = useState<StepStatus[]>([
    { id: 'rewrite', label: 'Query Rewrite', status: 'pending' },
    { id: 'search', label: 'Vector Search', status: 'pending' },
    { id: 'rerank', label: 'Rerank', status: 'pending' },
    { id: 'judge', label: 'Relevance Judge', status: 'pending' },
  ])
  
  // History State
  const [sessions, setSessions] = useState<HistorySession[]>([])
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null)
  
  // Modal State
  const [modalSource, setModalSource] = useState<SourceDoc | null>(null)
  const [isModalOpen, setIsModalOpen] = useState(false)

  // Load History from LocalStorage
  useEffect(() => {
    const saved = localStorage.getItem('chat_history')
    if (saved) {
      try {
        const parsed = JSON.parse(saved)
        setSessions(parsed)
      } catch (e) {
        console.error("Failed to parse history", e)
      }
    }
  }, [])

  // Save History to LocalStorage
  useEffect(() => {
    localStorage.setItem('chat_history', JSON.stringify(sessions))
  }, [sessions])

  // Update current session when messages change
  useEffect(() => {
    if (!currentSessionId && messages.length > 0) {
      // Create new session
      const newId = Date.now().toString()
      const newSession: HistorySession = {
        id: newId,
        title: messages[0].content.slice(0, 30) + (messages[0].content.length > 30 ? '...' : ''),
        timestamp: Date.now(),
        messages: messages
      }
      setSessions(prev => [newSession, ...prev])
      setCurrentSessionId(newId)
    } else if (currentSessionId && messages.length > 0) {
      // Update existing session
      setSessions(prev => prev.map(s => 
        s.id === currentSessionId ? { ...s, messages: messages, timestamp: Date.now() } : s
      ))
    }
  }, [messages, currentSessionId])

  const loadSession = (session: HistorySession) => {
    setMessages(session.messages)
    setCurrentSessionId(session.id)
    // Extract sources from the last AI message if available
    const lastAiMsg = [...session.messages].reverse().find(m => m.role === 'ai' && m.sources)
    if (lastAiMsg && lastAiMsg.sources) {
        const mappedSources: SearchHit[] = lastAiMsg.sources.map(doc => ({
            id: String(doc.id),
            content: doc.content,
            metadata: doc.metadata,
            date: String(doc.metadata.date || ''),
            score: 0
        }))
        setSources(mappedSources)
    } else {
        setSources([])
    }
    
    // Close sidebar on mobile
    if (window.innerWidth < 768) {
        setIsSidebarOpen(false)
    }
  }

  const startNewChat = () => {
    setMessages([])
    setSources([])
    setQuery('')
    setCurrentSessionId(null)
    resetSteps()
  }

  const openSourceModal = (source: SourceDoc) => {
    setModalSource(source)
    setIsModalOpen(true)
  }

  // Group sessions by date
  const groupedSessions = sessions.reduce((groups, session) => {
    const date = new Date(session.timestamp)
    const today = new Date()
    const yesterday = new Date(today)
    yesterday.setDate(yesterday.getDate() - 1)
    
    let key = 'Older'
    if (date.toDateString() === today.toDateString()) key = 'Today'
    else if (date.toDateString() === yesterday.toDateString()) key = 'Yesterday'
    
    if (!groups[key]) groups[key] = []
    groups[key].push(session)
    return groups
  }, {} as Record<string, HistorySession[]>)

  // Toggle Dark Mode
  useEffect(() => {
    if (isDarkMode) {
      document.documentElement.classList.add('dark')
    } else {
      document.documentElement.classList.remove('dark')
    }
  }, [isDarkMode])

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, steps])

  const updateStep = (id: string, status: 'loading' | 'completed') => {
    setSteps(prev => prev.map(s => s.id === id ? { ...s, status } : s))
  }

  const resetSteps = () => {
    setSteps([
      { id: 'rewrite', label: 'Query Rewrite', status: 'pending' },
      { id: 'search', label: 'Vector Search', status: 'pending' },
      { id: 'rerank', label: 'Rerank', status: 'pending' },
      { id: 'judge', label: 'Relevance Judge', status: 'pending' },
    ])
  }

  const handleSearch = async () => {
    if (!query.trim()) return
    
    // If we are in a historical session and user types new query, 
    // we continue appending to it. 
    // Ideally, LLM context should carry over, but backend API is stateless single-turn RAG for now.
    // We will just append to UI.
    
    setLoading(true)
    resetSteps()
    setMessages(prev => [...prev, {role: 'user', content: query}])
    const currentQuery = query
    setQuery('') // Clear input
    
    // Simulate steps for UI effect
    updateStep('rewrite', 'loading')
    setTimeout(() => { updateStep('rewrite', 'completed'); updateStep('search', 'loading') }, 800)
    setTimeout(() => { updateStep('search', 'completed'); updateStep('rerank', 'loading') }, 1500)
    setTimeout(() => { updateStep('rerank', 'completed'); updateStep('judge', 'loading') }, 2500)
    setTimeout(() => { updateStep('judge', 'completed') }, 3200)

    try {
      // 1. Chat (Stream) - Single request approach
      setStreaming(true)
      setMessages(prev => [...prev, {role: 'ai', content: ''}])
      
      const chatRes = await fetch('http://localhost:8000/api/chat', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({query: currentQuery})
      })
      
      const reader = chatRes.body?.getReader()
      const decoder = new TextDecoder()
      
      let buffer = ''
      let sourcesParsed = false

      if (reader) {
        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          
          const chunk = decoder.decode(value, {stream: true})
          buffer += chunk
          
          if (!sourcesParsed) {
             // Check if we have the sources prefix
             if (buffer.startsWith('__SOURCES__:')) {
                const newlineIdx = buffer.indexOf('\n')
                if (newlineIdx !== -1) {
                   const jsonStr = buffer.slice('__SOURCES__:'.length, newlineIdx)
                   try {
                      const parsed = JSON.parse(jsonStr) as unknown
                      const extractedSources: SourceDoc[] = isSourceDocArray(parsed) ? parsed : []
                      
                      // Update Sources State directly for Right Panel
                      // Map SourceDoc structure to SearchHit structure for right panel compatibility
                      const mappedSources: SearchHit[] = extractedSources.map(doc => ({
                        id: String(doc.id),
                        content: doc.content,
                        metadata: doc.metadata,
                        date: doc.metadata.date as string | undefined,
                        score: 0 // Score is not passed in this simplified view, or could be added to SourceDoc
                      }))
                      setSources(mappedSources)

                      setMessages(prev => {
                        const newMsgs = [...prev]
                        const last = newMsgs[newMsgs.length - 1]
                        newMsgs[newMsgs.length - 1] = {...last, sources: extractedSources}
                        return newMsgs
                      })
                   } catch (e) {
                      console.error("Failed to parse sources", e)
                   }
                   buffer = buffer.slice(newlineIdx + 1)
                   sourcesParsed = true
                }
             } else {
                // If buffer gets long enough and doesn't start with prefix, assume no sources
                if (buffer.length > 20) {
                   sourcesParsed = true
                }
             }
          }
          
          // Stream rendering optimization: Render whatever we have immediately
          if (sourcesParsed && buffer.length > 0) {
            const textToAppend = buffer
            buffer = ''
            setMessages(prev => {
              const newMsgs = [...prev]
              const last = newMsgs[newMsgs.length - 1]
              newMsgs[newMsgs.length - 1] = {...last, content: last.content + textToAppend}
              return newMsgs
            })
          }
        }
      }
    } catch (e) {
      console.error(e)
      setMessages(prev => [...prev, {role: 'ai', content: "Error: Failed to fetch response."}])
    } finally {
      setLoading(false)
      setStreaming(false)
      // Ensure all steps are completed
      setSteps(prev => prev.map(s => ({...s, status: 'completed'})))
    }
  }

  return (
    <div className="h-screen bg-surface-50 dark:bg-slate-900 flex flex-col overflow-hidden font-sans text-slate-800 dark:text-slate-100 transition-colors duration-300">
      <SourceModal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} source={modalSource} />
      
      {/* Header */}
      <header className="bg-white/80 dark:bg-slate-900/80 backdrop-blur-md border-b border-gray-200 dark:border-slate-800 p-4 shadow-sm z-20 flex justify-between items-center sticky top-0">
        <div className="flex items-center gap-3">
          <img src={logo} alt="Logo" className="w-8 h-8 rounded-lg shadow-lg shadow-brand-500/30 object-contain bg-white" />
          <h1 className="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-brand-600 to-brand-400 dark:from-brand-400 dark:to-brand-200">
            Bristol Campus RAG
          </h1>
        </div>
        <div className="flex items-center gap-2">
          <button 
            onClick={() => setIsDarkMode(!isDarkMode)}
            className="p-2 rounded-full hover:bg-gray-100 dark:hover:bg-slate-800 text-gray-500 dark:text-gray-400 transition-colors"
          >
            {isDarkMode ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
          </button>
          <button 
            className="md:hidden p-2 text-gray-500 dark:text-gray-400 hover:text-brand-600 transition-colors"
            onClick={() => setIsSidebarOpen(!isSidebarOpen)}
          >
            {isSidebarOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>
        </div>
      </header>
      
      <div className="flex-1 flex overflow-hidden relative">
        {/* Left Sidebar (History) */}
        <aside className={`
          absolute md:relative z-10 w-64 bg-white dark:bg-slate-900 border-r border-gray-100 dark:border-slate-800 h-full transition-transform duration-300 ease-in-out
          ${isSidebarOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}
          flex flex-col shadow-xl md:shadow-none
        `}>
          <div className="p-6 flex-1 overflow-y-auto">
            <div className="flex justify-between items-center mb-6">
                <h2 className="font-bold text-gray-800 dark:text-slate-200 flex items-center gap-2">
                <span className="w-1 h-4 bg-brand-500 rounded-full"></span>
                History
                </h2>
                <button 
                    onClick={startNewChat}
                    className="p-1.5 bg-brand-50 dark:bg-slate-800 text-brand-600 dark:text-brand-400 rounded-lg hover:bg-brand-100 dark:hover:bg-slate-700 transition-colors"
                    title="New Chat"
                >
                    <MessageSquare className="w-4 h-4" />
                </button>
            </div>
            
            <div className="space-y-6">
               {['Today', 'Yesterday', 'Older'].map(group => (
                   groupedSessions[group] && groupedSessions[group].length > 0 && (
                       <div key={group}>
                           <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3 px-1">{group}</h3>
                           <div className="space-y-2">
                               {groupedSessions[group].map(session => (
                                   <div 
                                     key={session.id}
                                     onClick={() => loadSession(session)}
                                     className={clsx(
                                         "p-3 rounded-xl border transition-all cursor-pointer group",
                                         currentSessionId === session.id 
                                            ? "bg-brand-50 dark:bg-slate-800/80 border-brand-200 dark:border-slate-600"
                                            : "bg-white dark:bg-slate-900 border-gray-100 dark:border-slate-800 hover:border-brand-200 dark:hover:border-slate-700"
                                     )}
                                   >
                                     <div className="flex items-center gap-2 mb-1">
                                        <Clock className={clsx("w-3 h-3", currentSessionId === session.id ? "text-brand-500" : "text-gray-400")} />
                                        <span className="text-xs text-gray-400">
                                            {new Date(session.timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}
                                        </span>
                                     </div>
                                     <p className={clsx(
                                         "text-sm font-medium truncate transition-colors",
                                         currentSessionId === session.id ? "text-brand-700 dark:text-brand-300" : "text-gray-600 dark:text-gray-400 group-hover:text-gray-900 dark:group-hover:text-gray-200"
                                     )}>
                                         {session.title}
                                     </p>
                                   </div>
                               ))}
                           </div>
                       </div>
                   )
               ))}
               
               {sessions.length === 0 && (
                   <div className="text-center py-10 text-gray-400">
                       <p className="text-sm">No history yet.</p>
                   </div>
               )}
            </div>
          </div>
        </aside>

        {/* Main Content */}
        <div className="flex-1 flex flex-col relative w-full">
          
          <div className="flex-1 flex gap-6 overflow-hidden p-4 md:p-6 max-w-7xl mx-auto w-full">
            {/* Chat Area */}
            <div className="flex-1 flex flex-col bg-white dark:bg-slate-900 rounded-2xl border border-gray-100 dark:border-slate-800 shadow-card overflow-hidden relative transition-colors duration-300">
              <div className="flex-1 overflow-y-auto p-6 space-y-6 scroll-smooth">
                {messages.length === 0 && (
                  <div className="h-full flex flex-col items-center justify-center text-center p-8 animate-fade-in-up">
                    <div className="w-16 h-16 bg-brand-100 dark:bg-slate-800 rounded-2xl flex items-center justify-center mb-6 text-brand-500">
                      <Search className="w-8 h-8" />
                    </div>
                    <h3 className="text-2xl font-bold text-gray-800 dark:text-slate-100 mb-2">How can I help you today?</h3>
                    <p className="text-gray-500 dark:text-gray-400 max-w-md">
                      Ask about exam schedules, campus events, or administrative notices. I'll search through official documents for you.
                    </p>
                    <div className="mt-8 flex flex-wrap justify-center gap-2">
                      {['Exam timetable', 'Library opening hours', 'Student support'].map(suggestion => (
                        <button 
                          key={suggestion}
                          onClick={() => setQuery(suggestion)}
                          className="px-4 py-2 bg-surface-100 dark:bg-slate-800 hover:bg-surface-200 dark:hover:bg-slate-700 text-sm text-gray-600 dark:text-gray-300 rounded-full transition-colors border border-transparent hover:border-brand-200 dark:hover:border-slate-600"
                        >
                          {suggestion}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
                {messages.map((msg, i) => (
                  <div key={i} className={`flex flex-col animate-fade-in-up ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
                    <div className={clsx(
                      "max-w-[85%] rounded-2xl p-5 prose prose-sm shadow-sm transition-colors duration-300",
                      msg.role === 'user' 
                        ? 'bg-brand-500 text-white prose-invert rounded-tr-none shadow-brand-500/20' 
                        : 'bg-surface-50 dark:bg-slate-800 text-gray-800 dark:text-slate-200 border border-gray-100 dark:border-slate-700 rounded-tl-none dark:prose-invert'
                    )}>
                      
                      {/* Render Sources if available (Only for AI) */}
                      {msg.role === 'ai' && msg.sources && msg.sources.length > 0 && (
                        <div className="mb-4 p-3 bg-white/50 dark:bg-slate-900/50 rounded-xl border border-brand-100/50 dark:border-slate-600/50 not-prose">
                          <p className="text-xs font-bold text-brand-600 dark:text-brand-400 mb-2 flex items-center gap-1">
                            <span className="w-1.5 h-1.5 bg-brand-500 rounded-full"></span>
                            Sources Used
                          </p>
                          <div className="flex flex-wrap gap-2">
                             {msg.sources.map((src, idx) => (
                               <div 
                                 key={idx}
                                 onClick={() => openSourceModal(src)}
                                 className="cursor-pointer"
                               >
                                 <SourcePreview source={src} />
                               </div>
                             ))}
                          </div>
                        </div>
                      )}
                      
                      <ReactMarkdown 
                        components={{
                          a: ({node, ...props}) => {
                             const content = props.children?.toString() || '';
                             // 1. Check if it's a source reference like [1]
                             const isRef = content.match(/^\[\d+\]$/);
                             if (isRef && msg.sources) {
                                // Extract index from [1] -> 1
                                const idx = parseInt(content.replace('[', '').replace(']', '')) - 1;
                                const source = msg.sources[idx];
                                return (
                                   <span className="inline-block mx-1">
                                      <span 
                                        onClick={() => source && openSourceModal(source)}
                                        className="bg-brand-100 dark:bg-brand-900 text-brand-600 dark:text-brand-300 px-1.5 rounded text-xs font-mono cursor-pointer hover:bg-brand-200 dark:hover:bg-brand-800 transition-colors" 
                                        title="View Source Details"
                                      >
                                         {props.children}
                                      </span>
                                   </span>
                                )
                             }
                             // 2. Check if it's a generated link like [1] http://...
                             return <a {...props} className="text-brand-500 hover:text-brand-600 hover:underline break-all" target="_blank" rel="noopener noreferrer" />
                          }
                        }}
                      >
                        {msg.content}
                      </ReactMarkdown>
                    </div>
                  </div>
                ))}
                
                {/* Progress Steps (Shown when loading/streaming) */}
                {(loading || streaming) && (
                  <div className="flex flex-col gap-2 max-w-[85%] animate-fade-in-up">
                    <div className="bg-surface-50 dark:bg-slate-800/50 rounded-xl p-4 border border-gray-100 dark:border-slate-800 flex items-center gap-3">
                       {steps.map((step, idx) => (
                         <div key={step.id} className="flex items-center gap-2">
                            <div className={clsx(
                               "flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium transition-all duration-300",
                               step.status === 'completed' ? "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400" :
                               step.status === 'loading' ? "bg-brand-100 text-brand-700 dark:bg-brand-900/30 dark:text-brand-400 ring-2 ring-brand-500/20" :
                               "bg-gray-100 text-gray-400 dark:bg-slate-800 dark:text-gray-600"
                            )}>
                               {step.status === 'loading' && <Loader2 className="w-3 h-3 animate-spin" />}
                               {step.label}
                            </div>
                            {idx < steps.length - 1 && (
                               <ArrowRight className={clsx(
                                  "w-3 h-3 transition-colors duration-300",
                                  steps[idx+1].status !== 'pending' ? "text-brand-300" : "text-gray-200 dark:text-slate-700"
                               )} />
                            )}
                         </div>
                       ))}
                    </div>
                  </div>
                )}
                
                <div ref={chatEndRef} />
              </div>

              {/* Input Area */}
              <div className="p-4 md:p-6 bg-white dark:bg-slate-900 border-t border-gray-100 dark:border-slate-800 transition-colors duration-300">
                <div className="flex gap-3 relative max-w-4xl mx-auto">
                  <div className="flex-1 relative">
                    <input 
                      className="w-full border border-gray-200 dark:border-slate-700 bg-surface-50 dark:bg-slate-800 rounded-xl px-5 py-4 pr-12 focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 outline-none transition-all shadow-sm text-gray-700 dark:text-slate-200 placeholder-gray-400 dark:placeholder-gray-500"
                      placeholder="Ask about campus notifications..."
                      value={query}
                      onChange={e => setQuery(e.target.value)}
                      onKeyDown={e => e.key === 'Enter' && handleSearch()}
                      disabled={loading || streaming}
                    />
                    {loading && (
                      <div className="absolute right-4 top-1/2 -translate-y-1/2">
                        <div className="animate-spin h-5 w-5 border-2 border-brand-500 border-t-transparent rounded-full"></div>
                      </div>
                    )}
                  </div>
                  <button 
                    onClick={handleSearch}
                    disabled={loading || streaming || !query.trim()}
                    className="bg-brand-500 text-white p-4 rounded-xl hover:bg-brand-600 disabled:opacity-50 disabled:hover:bg-brand-500 shadow-lg shadow-brand-500/30 transition-all hover:scale-105 active:scale-95"
                  >
                    <Search className="w-5 h-5"/>
                  </button>
                </div>
              </div>
            </div>

            {/* Source Cards (Right Panel) */}
            <div className="hidden lg:flex w-80 flex-col gap-4">
               <div className="bg-white dark:bg-slate-900 rounded-2xl border border-gray-100 dark:border-slate-800 shadow-card p-5 flex-1 overflow-hidden flex flex-col transition-colors duration-300">
                  <h3 className="font-bold text-gray-800 dark:text-slate-200 mb-4 flex items-center gap-2">
                    <span className="p-1.5 bg-accent-50 dark:bg-accent-900/20 text-accent-500 rounded-lg">
                      <Search className="w-4 h-4" />
                    </span>
                    References
                  </h3>
                  <div className="space-y-3 flex-1 overflow-y-auto pr-1 custom-scrollbar">
                    {sources.map((source, i) => (
                      <div 
                        key={i} 
                        onClick={() => {
                            // Convert SearchHit back to SourceDoc for modal (approximate)
                            const doc: SourceDoc = {
                                id: parseInt(source.id || '0'),
                                content: source.content,
                                metadata: source.metadata
                            }
                            openSourceModal(doc)
                        }}
                        className="bg-surface-50 dark:bg-slate-800 p-4 rounded-xl border border-gray-100 dark:border-slate-700 hover:border-brand-200 dark:hover:border-slate-600 hover:shadow-soft transition-all cursor-pointer group hover:-translate-y-1"
                      >
                        <div className="flex justify-between items-start mb-2">
                          <span className="bg-white dark:bg-slate-900 border border-gray-200 dark:border-slate-600 text-gray-500 dark:text-gray-400 text-[10px] px-2 py-0.5 rounded-full font-mono group-hover:border-brand-200 dark:group-hover:border-slate-500 group-hover:text-brand-500 transition-colors">#{i+1}</span>
                          <span className="text-[10px] text-gray-400 dark:text-gray-500 font-medium">{source.date || 'No Date'}</span>
                        </div>
                        <a href={source.metadata?.url} target="_blank" onClick={(e) => e.stopPropagation()} className="text-sm font-semibold text-gray-800 dark:text-slate-200 group-hover:text-brand-600 dark:group-hover:text-brand-400 transition-colors block mb-2 leading-snug">
                          {source.metadata?.title || 'Untitled Notification'}
                        </a>
                        <p className="text-xs text-gray-500 dark:text-gray-400 line-clamp-3 mb-3">
                          {source.content}
                        </p>
                        <div className="flex items-center justify-between mt-2">
                           <div className="flex items-center gap-2 flex-1 mr-4">
                             <div className="h-1.5 bg-gray-200 dark:bg-slate-700 rounded-full flex-1 overflow-hidden">
                                <div 
                                  className="h-full bg-gradient-to-r from-brand-400 to-accent-500 rounded-full transition-all duration-500" 
                                  style={{width: `${Math.min((source.score || 0) * 100, 100)}%`}}
                                ></div>
                             </div>
                             <span className="text-[10px] font-mono text-gray-400">{(source.score || 0).toFixed(2)}</span>
                           </div>
                           <button 
                             onClick={(e) => {
                               e.stopPropagation()
                               const doc: SourceDoc = {
                                   id: parseInt(source.id || '0'),
                                   content: source.content,
                                   metadata: source.metadata,
                                   score: source.score,
                                   date: source.date
                               }
                               openSourceModal(doc)
                             }}
                             className="flex items-center gap-1 text-[10px] font-medium text-brand-500 hover:text-brand-600 hover:bg-brand-50 dark:hover:bg-brand-900/30 px-2 py-1 rounded transition-colors"
                           >
                             <BookOpen className="w-3 h-3" />
                             Read Full
                           </button>
                        </div>
                      </div>
                    ))}
                    {sources.length === 0 && (
                      <div className="text-center py-12 text-gray-400 dark:text-gray-600 flex flex-col items-center">
                        <div className="w-12 h-12 bg-gray-100 dark:bg-slate-800 rounded-full flex items-center justify-center mb-3">
                           <Search className="w-5 h-5 opacity-50" />
                        </div>
                        <p className="text-sm">References will appear here</p>
                      </div>
                    )}
                  </div>
               </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default App
