export type Source = {
  id: number
  title: string
  location?: string | null
  snippet: string
}

export type ChatMessage = {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources?: Source[]
  error?: string
  /** ID jawaban di server (untuk umpan balik penilai). */
  chatId?: string
  /** 1 = bagus, -1 = kurang tepat. */
  rating?: 1 | -1
  comment?: string
}

export type Conversation = {
  id: string
  title: string
  messages: ChatMessage[]
  updatedAt: number
}

export type ApiMessage = { role: 'user' | 'assistant'; content: string }

export type AppConfig = { mode: string; version: string }
