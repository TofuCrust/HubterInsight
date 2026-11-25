import { getSessionId } from './storage'
import type { ApiMessage, AppConfig, Source } from './types'

type Handlers = {
  onMeta: (chatId: string) => void
  onSources: (sources: Source[]) => void
  onToken: (token: string) => void
}

// Dipanggil bila server menolak karena sesi login habis; App kemudian menampilkan layar login lagi.
let unauthorizedHandler: (() => void) | null = null
export function onUnauthorized(fn: (() => void) | null): void {
  unauthorizedHandler = fn
}

export type SessionInfo = { authRequired: boolean; authenticated: boolean }

/** Perlu layar login atau tidak. null bila server tidak terjangkau. */
export async function fetchSession(): Promise<SessionInfo | null> {
  try {
    const res = await fetch('/api/session')
    if (!res.ok) return null
    const body = await res.json()
    return { authRequired: Boolean(body?.auth_required), authenticated: Boolean(body?.authenticated) }
  } catch {
    return null
  }
}

export async function login(username: string, password: string): Promise<{ ok: true } | { ok: false; message: string }> {
  try {
    const res = await fetch('/api/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    })
    if (res.ok) return { ok: true }
    return { ok: false, message: await errorMessage(res) }
  } catch {
    return { ok: false, message: 'Tidak dapat terhubung ke server. Periksa koneksi Anda.' }
  }
}

export async function logout(): Promise<void> {
  try {
    await fetch('/api/logout', { method: 'POST' })
  } catch {
    /* abaikan: cookie akan kedaluwarsa sendiri */
  }
}

async function errorMessage(res: Response): Promise<string> {
  try {
    const body = await res.json()
    if (typeof body?.detail === 'string') return body.detail
  } catch {
    /* abaikan */
  }
  if (res.status === 429) return 'Terlalu banyak permintaan. Tunggu sebentar lalu coba lagi.'
  if (res.status === 413) return 'Pesan terlalu panjang.'
  return `Server menolak permintaan (kode ${res.status}).`
}

/** Mengirim percakapan ke /api/chat dan membaca jawaban yang dialirkan (SSE). */
export async function streamChat(messages: ApiMessage[], handlers: Handlers, signal: AbortSignal): Promise<void> {
  const res = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ messages, session_id: getSessionId() }),
    signal,
  })
  if (res.status === 401) {
    unauthorizedHandler?.()
    throw new Error('Sesi login berakhir. Silakan masuk lagi.')
  }
  if (!res.ok || !res.body) throw new Error(await errorMessage(res))

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  const handle = (raw: string) => {
    let event = 'message'
    let data = ''
    for (const line of raw.split('\n')) {
      if (line.startsWith('event:')) event = line.slice(6).trim()
      else if (line.startsWith('data:')) data += line.slice(5).trim()
    }
    if (!data) return
    const payload = JSON.parse(data)
    if (event === 'meta') handlers.onMeta(payload.id as string)
    else if (event === 'sources') handlers.onSources(payload as Source[])
    else if (event === 'token') handlers.onToken(payload.t as string)
    else if (event === 'error') throw new Error(payload.message || 'Terjadi kesalahan di server.')
  }

  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, '\n')
    let idx: number
    while ((idx = buffer.indexOf('\n\n')) !== -1) {
      const raw = buffer.slice(0, idx)
      buffer = buffer.slice(idx + 2)
      handle(raw)
    }
  }
}

/** Menyimpan penilaian (👍/👎) dan/atau komentar penilai untuk satu jawaban. Mengembalikan true bila tersimpan. */
export async function sendFeedback(chatId: string, fb: { rating?: 1 | -1; comment?: string }): Promise<boolean> {
  try {
    const res = await fetch('/api/feedback', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ chat_id: chatId, ...fb }),
    })
    if (res.status === 401) unauthorizedHandler?.()
    return res.ok
  } catch {
    return false
  }
}

export async function fetchConfig(): Promise<AppConfig | null> {
  try {
    const res = await fetch('/api/config')
    if (res.status === 401) unauthorizedHandler?.()
    if (!res.ok) return null
    const body = await res.json()
    return typeof body?.mode === 'string' ? { mode: body.mode, version: String(body.version ?? '') } : null
  } catch {
    return null
  }
}

export type FileInfo = { name: string; size: number; modified: string }
export type FileList = { files: FileInfo[]; usedBytes: number; maxFileMb: number; quotaMb: number }

/** Daftar berkas di folder unggahan. null bila gagal. */
export async function listFiles(): Promise<FileList | null> {
  try {
    const res = await fetch('/api/files')
    if (res.status === 401) unauthorizedHandler?.()
    if (!res.ok) return null
    const body = await res.json()
    return {
      files: Array.isArray(body?.files) ? (body.files as FileInfo[]) : [],
      usedBytes: Number(body?.used_bytes ?? 0),
      maxFileMb: Number(body?.max_file_mb ?? 25),
      quotaMb: Number(body?.quota_mb ?? 1000),
    }
  } catch {
    return null
  }
}

export const fileUrl = (name: string) => `/api/files/${encodeURIComponent(name)}`

/** Mengunggah satu berkas (isi mentah, nama di header) dengan laporan kemajuan 0-100. */
export function uploadFile(
  file: File,
  onProgress: (percent: number) => void,
): Promise<{ ok: true; name: string } | { ok: false; message: string }> {
  return new Promise((resolve) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', '/api/files')
    xhr.setRequestHeader('Content-Type', 'application/octet-stream')
    xhr.setRequestHeader('X-Filename', encodeURIComponent(file.name))
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100))
    }
    xhr.onerror = () => resolve({ ok: false, message: 'Koneksi terputus. Coba lagi.' })
    xhr.onload = () => {
      if (xhr.status === 401) unauthorizedHandler?.()
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve({ ok: true, name: String(JSON.parse(xhr.responseText).name ?? file.name) })
        } catch {
          resolve({ ok: true, name: file.name })
        }
        return
      }
      let message = `Gagal mengunggah (kode ${xhr.status}).`
      if (xhr.status === 413) message = 'Berkas terlalu besar.'
      try {
        const detail = JSON.parse(xhr.responseText)?.detail
        if (typeof detail === 'string') message = detail
      } catch {
        /* balasan bukan JSON (mis. dari Nginx) */
      }
      resolve({ ok: false, message })
    }
    xhr.send(file)
  })
}
