import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { fetchConfig, fetchSession, logout, onUnauthorized, sendFeedback, streamChat } from './api'
import { loadConversations, saveConversations } from './storage'
import type { ApiMessage, ChatMessage, Conversation } from './types'
import ChatView from './components/ChatView'
import Composer from './components/Composer'
import FilesView from './components/FilesView'
import Login from './components/Login'
import Sidebar from './components/Sidebar'
import { MenuIcon, MoonIcon, SunIcon } from './icons'
import { useTheme } from './theme'

const MAX_HISTORY = 12
const FILES_HASH = '#/dokumen'

const uid = () =>
  typeof crypto !== 'undefined' && 'randomUUID' in crypto ? crypto.randomUUID() : Math.random().toString(36).slice(2)

const titleFrom = (text: string) => {
  const t = text.replace(/\s+/g, ' ').trim()
  return t.length > 42 ? `${t.slice(0, 42)}…` : t
}

/** Riwayat yang dikirim ke server: hanya pesan bermakna, dibatasi agar hemat biaya. */
const toHistory = (messages: ChatMessage[]): ApiMessage[] =>
  messages
    .filter((m) => m.content.trim() && !m.error)
    .slice(-MAX_HISTORY)
    .map((m) => ({ role: m.role, content: m.content }))

type ChatProps = { authRequired: boolean; onLoggedOut: () => void }

function Chat({ authRequired, onLoggedOut }: ChatProps) {
  const [items, setItems] = useState<Conversation[]>(loadConversations)
  const [activeId, setActiveId] = useState<string | null>(null)
  const [streamingId, setStreamingId] = useState<string | null>(null)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [mode, setMode] = useState<string | null>(null)
  const [version, setVersion] = useState('')
  const [freshNonce, setFreshNonce] = useState(0)
  // Halaman Dokumen punya alamat sendiri (#/dokumen) agar bisa dibuka langsung dan tombol kembali berfungsi
  const [view, setView] = useState<'chat' | 'files'>(() => (window.location.hash === FILES_HASH ? 'files' : 'chat'))
  useEffect(() => {
    const onHash = () => setView(window.location.hash === FILES_HASH ? 'files' : 'chat')
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])
  const toChat = () => {
    if (window.location.hash === FILES_HASH) window.history.pushState(null, '', window.location.pathname + window.location.search)
    setView('chat')
  }
  const openFiles = () => {
    stop()
    window.location.hash = FILES_HASH
    setSidebarOpen(false)
  }
  // Sidebar desktop: bisa disembunyikan; pilihan diingat di browser
  const [collapsed, setCollapsed] = useState(() => {
    try {
      return localStorage.getItem('hubter-sidebar') === 'collapsed'
    } catch {
      return false
    }
  })
  useEffect(() => {
    try {
      localStorage.setItem('hubter-sidebar', collapsed ? 'collapsed' : 'open')
    } catch {
      /* penyimpanan tidak tersedia */
    }
  }, [collapsed])
  const abortRef = useRef<AbortController | null>(null)
  const { theme, toggle: toggleTheme } = useTheme()

  // Simpan riwayat (ditunda agar tidak menulis setiap token)
  useEffect(() => {
    const t = window.setTimeout(() => saveConversations(items), 400)
    return () => window.clearTimeout(t)
  }, [items])

  // Sesi login habis (cookie kedaluwarsa): kembali ke layar masuk
  useEffect(() => {
    onUnauthorized(onLoggedOut)
    return () => onUnauthorized(null)
  }, [onLoggedOut])

  const signOut = useCallback(() => {
    abortRef.current?.abort()
    void logout().then(onLoggedOut)
  }, [onLoggedOut])

  useEffect(() => {
    fetchConfig().then((cfg) => {
      setMode(cfg?.mode ?? null)
      setVersion(cfg?.version ?? '')
    })
  }, [])

  const sorted = useMemo(() => [...items].sort((a, b) => b.updatedAt - a.updatedAt), [items])
  const active = items.find((c) => c.id === activeId) ?? null

  const stop = useCallback(() => abortRef.current?.abort(), [])

  const run = useCallback(async (convId: string, history: ApiMessage[], assistantId: string) => {
    const ctrl = new AbortController()
    abortRef.current = ctrl
    setStreamingId(assistantId)

    const patch = (fn: (m: ChatMessage) => ChatMessage) =>
      setItems((prev) =>
        prev.map((c) =>
          c.id === convId
            ? { ...c, updatedAt: Date.now(), messages: c.messages.map((m) => (m.id === assistantId ? fn(m) : m)) }
            : c,
        ),
      )

    try {
      await streamChat(
        history,
        {
          onMeta: (chatId) => patch((m) => ({ ...m, chatId })),
          onSources: (sources) => patch((m) => ({ ...m, sources })),
          onToken: (t) => patch((m) => ({ ...m, content: m.content + t })),
        },
        ctrl.signal,
      )
    } catch (e) {
      if (!ctrl.signal.aborted) {
        const msg = e instanceof Error ? e.message : 'Terjadi kesalahan.'
        patch((m) => ({ ...m, error: msg }))
      }
    } finally {
      if (abortRef.current === ctrl) abortRef.current = null
      setStreamingId(null)
    }
  }, [])

  const send = useCallback(
    (text: string) => {
      const question = text.trim()
      if (!question || streamingId) return

      const userMsg: ChatMessage = { id: uid(), role: 'user', content: question }
      const assistantMsg: ChatMessage = { id: uid(), role: 'assistant', content: '' }

      if (active) {
        setItems((prev) =>
          prev.map((c) =>
            c.id === active.id
              ? { ...c, updatedAt: Date.now(), messages: [...c.messages, userMsg, assistantMsg] }
              : c,
          ),
        )
        void run(active.id, toHistory([...active.messages, userMsg]), assistantMsg.id)
      } else {
        const conv: Conversation = {
          id: uid(),
          title: titleFrom(question),
          messages: [userMsg, assistantMsg],
          updatedAt: Date.now(),
        }
        setItems((prev) => [conv, ...prev])
        setActiveId(conv.id)
        void run(conv.id, toHistory([userMsg]), assistantMsg.id)
      }
    },
    [active, run, streamingId],
  )

  const regenerate = useCallback(() => {
    if (!active || streamingId) return
    const msgs = active.messages
    const lastIdx = msgs.length - 1
    if (lastIdx < 1 || msgs[lastIdx].role !== 'assistant') return

    const assistantMsg: ChatMessage = { id: uid(), role: 'assistant', content: '' }
    const kept = msgs.slice(0, lastIdx)
    setItems((prev) =>
      prev.map((c) => (c.id === active.id ? { ...c, updatedAt: Date.now(), messages: [...kept, assistantMsg] } : c)),
    )
    void run(active.id, toHistory(kept), assistantMsg.id)
  }, [active, run, streamingId])

  /** Penilaian dan komentar penilai: tampil langsung di layar, lalu dikirim ke server. */
  const giveFeedback = useCallback(
    (messageId: string, fb: { rating?: 1 | -1; comment?: string }): Promise<boolean> => {
      const convId = active?.id
      const chatId = active?.messages.find((m) => m.id === messageId)?.chatId
      if (!convId || !chatId) return Promise.resolve(false)
      setItems((prev) =>
        prev.map((c) =>
          c.id === convId ? { ...c, messages: c.messages.map((m) => (m.id === messageId ? { ...m, ...fb } : m)) } : c,
        ),
      )
      return sendFeedback(chatId, fb)
    },
    [active],
  )

  const newChat = () => {
    stop()
    toChat()
    setFreshNonce((n) => n + 1) // sapaan baru tiap "Percakapan baru"
    setActiveId(null)
    setSidebarOpen(false)
  }

  const select = (id: string) => {
    stop()
    toChat()
    setActiveId(id)
    setSidebarOpen(false)
  }

  const remove = (id: string) => {
    if (id === activeId) {
      stop()
      setActiveId(null)
    }
    setItems((prev) => prev.filter((c) => c.id !== id))
  }

  const [mobile, setMobile] = useState(() => window.matchMedia('(max-width: 820px)').matches)
  useEffect(() => {
    const mq = window.matchMedia('(max-width: 820px)')
    const onChange = () => setMobile(mq.matches)
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [])

  // Di HP tombol menu membuka/menutup drawer; di desktop menyembunyikan/menampilkan sidebar
  const sidebarShown = mobile ? sidebarOpen : !collapsed
  const toggleSidebar = () => (mobile ? setSidebarOpen((v) => !v) : setCollapsed((v) => !v))

  return (
    <div className={`app${collapsed ? ' collapsed' : ''}`}>
      <a className="skip-link" href="#composer-input">
        Langsung ke kolom pertanyaan
      </a>
      <Sidebar
        items={sorted}
        activeId={activeId}
        open={sidebarOpen}
        version={version}
        onNew={newChat}
        onSelect={select}
        onDelete={remove}
        onClose={() => setSidebarOpen(false)}
        onLogout={authRequired ? signOut : undefined}
        onFiles={openFiles}
        filesActive={view === 'files'}
      />

      <main className="main">
        <header className="topbar">
          <button
            className="icon-btn menu"
            aria-label={sidebarShown ? 'Sembunyikan riwayat' : 'Tampilkan riwayat'}
            aria-expanded={sidebarShown}
            onClick={toggleSidebar}
          >
            <MenuIcon />
          </button>
          <h1 className="topbar-title">{view === 'files' ? 'Dokumen' : (active?.title ?? 'HubTer Insight')}</h1>
          {mode === 'mock' && <span className="badge">Mode demo</span>}
          <button
            className="icon-btn"
            onClick={toggleTheme}
            aria-label={theme === 'dark' ? 'Ganti ke tema terang' : 'Ganti ke tema gelap'}
            title={theme === 'dark' ? 'Tema terang' : 'Tema gelap'}
          >
            {theme === 'dark' ? <SunIcon /> : <MoonIcon />}
          </button>
        </header>

        {view === 'files' ? (
          <FilesView />
        ) : (
          <>
            <ChatView
              key={activeId ?? `new-${freshNonce}`}
              messages={active?.messages ?? []}
              streamingId={streamingId}
              onSuggest={send}
              onRegenerate={regenerate}
              onFeedback={giveFeedback}
            />

            <Composer streaming={streamingId !== null} onSend={send} onStop={stop} />
          </>
        )}
      </main>
    </div>
  )
}

type AuthState = 'checking' | 'login' | 'ok'

export default function App() {
  const [auth, setAuth] = useState<AuthState>('checking')
  const [authRequired, setAuthRequired] = useState(false)

  useEffect(() => {
    fetchSession().then((s) => {
      setAuthRequired(Boolean(s?.authRequired))
      // Server tidak terjangkau: tampilkan aplikasi, galatnya muncul saat bertanya
      setAuth(!s || !s.authRequired || s.authenticated ? 'ok' : 'login')
    })
  }, [])

  const toLogin = useCallback(() => setAuth('login'), [])

  if (auth === 'checking') return <div className="login-page" aria-busy="true" />
  if (auth === 'login') {
    return (
      <Login
        onSuccess={() => {
          setAuthRequired(true)
          setAuth('ok')
        }}
      />
    )
  }
  return <Chat authRequired={authRequired} onLoggedOut={toLogin} />
}
