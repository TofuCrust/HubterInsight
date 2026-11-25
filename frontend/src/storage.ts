import type { Conversation } from './types'

const KEY = 'hubter.conversations.v1'

export function loadConversations(): Conversation[] {
  try {
    const raw = localStorage.getItem(KEY)
    if (!raw) return []
    const data = JSON.parse(raw)
    return Array.isArray(data) ? (data as Conversation[]) : []
  } catch {
    return []
  }
}

const SESSION_KEY = 'hubter.session'

/** ID acak per browser untuk mengelompokkan pertanyaan di log evaluasi. Bukan identitas. */
export function getSessionId(): string {
  try {
    let id = localStorage.getItem(SESSION_KEY)
    if (!id) {
      id =
        typeof crypto !== 'undefined' && 'randomUUID' in crypto
          ? crypto.randomUUID()
          : Math.random().toString(36).slice(2) + Date.now().toString(36)
      localStorage.setItem(SESSION_KEY, id)
    }
    return id
  } catch {
    return 'tanpa-penyimpanan'
  }
}

export function saveConversations(items: Conversation[]): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(items))
  } catch {
    /* penyimpanan penuh atau dinonaktifkan: aplikasi tetap jalan tanpa riwayat */
  }
}
