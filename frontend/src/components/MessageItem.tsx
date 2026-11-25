import { useState } from 'react'
import type { ChatMessage } from '../types'
import { CheckIcon, ChevronIcon, CopyIcon, DocIcon, RefreshIcon, ThumbDownIcon, ThumbUpIcon } from '../icons'
import { motion } from 'motion/react'
import Markdown from './Markdown'

const enter = {
  initial: { opacity: 0, y: 10 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.3, ease: [0.22, 1, 0.36, 1] as const },
}

type Props = {
  message: ChatMessage
  streaming: boolean
  canRegenerate: boolean
  onRegenerate: () => void
  onFeedback: (messageId: string, fb: { rating?: 1 | -1; comment?: string }) => Promise<boolean>
}

export default function MessageItem({ message, streaming, canRegenerate, onRegenerate, onFeedback }: Props) {
  const [copied, setCopied] = useState(false)
  const [draft, setDraft] = useState(message.comment ?? '')
  const [saved, setSaved] = useState<'idle' | 'saving' | 'ok' | 'fail'>('idle')

  if (message.role === 'user') {
    return (
      <motion.div className="msg user" {...enter}>
        <div className="bubble">{message.content}</div>
      </motion.div>
    )
  }

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(message.content)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1500)
    } catch {
      /* clipboard tidak tersedia */
    }
  }

  const waiting = streaming && !message.content
  // Setelah komentar terkirim, tombol 👍/👎 dan kolom teks diganti ucapan terima kasih. `message.comment` terisi
  // sebelum kiriman berhasil, jadi kegagalan (saved === 'fail') tetap menampilkan kolom agar bisa dicoba lagi.
  const thanked = saved === 'ok' || (saved === 'idle' && !!message.comment && draft === message.comment)

  const rate = async (rating: 1 | -1) => {
    setSaved('saving')
    setSaved((await onFeedback(message.id, { rating })) ? 'idle' : 'fail')
  }

  const sendComment = async () => {
    const comment = draft.trim()
    if (!comment) return
    setSaved('saving')
    setSaved((await onFeedback(message.id, { comment })) ? 'ok' : 'fail')
  }

  return (
    <motion.div className="msg assistant" {...enter}>
      <span className="avatar" aria-hidden="true" />
      <div className="body">
        {waiting ? (
          <div className="typing" role="status" aria-label="Menyusun jawaban">
            <span />
            <span />
            <span />
          </div>
        ) : (
          message.content && <Markdown text={message.content} />
        )}

        {message.error && <div className="error-box">{message.error}</div>}

        {message.sources && message.sources.length > 0 && !waiting && (
          <details className="sources">
            <summary>
              <DocIcon /> Sumber ({message.sources.length})
              <span className="chevron">
                <ChevronIcon />
              </span>
            </summary>
            <ol>
              {message.sources.map((s) => (
                <li key={s.id}>
                  <strong>{s.title}</strong>
                  {s.location && <span className="muted"> · {s.location}</span>}
                  <p className="snippet">{s.snippet}</p>
                </li>
              ))}
            </ol>
          </details>
        )}

        {!streaming && message.content && (
          <div className="actions">
            <button className="icon-btn" onClick={copy} aria-label="Salin jawaban" title="Salin">
              {copied ? <CheckIcon /> : <CopyIcon />}
            </button>
            {canRegenerate && (
              <button className="icon-btn" onClick={onRegenerate} aria-label="Buat ulang jawaban" title="Buat ulang">
                <RefreshIcon />
              </button>
            )}
            {message.chatId && !message.error && !thanked && (
              <>
                <button
                  className={`icon-btn rate${message.rating === 1 ? ' on' : ''}`}
                  onClick={() => rate(1)}
                  aria-label="Jawaban bagus"
                  aria-pressed={message.rating === 1}
                  title="Jawaban bagus"
                >
                  <ThumbUpIcon />
                </button>
                <button
                  className={`icon-btn rate bad${message.rating === -1 ? ' on' : ''}`}
                  onClick={() => rate(-1)}
                  aria-label="Jawaban kurang tepat"
                  aria-pressed={message.rating === -1}
                  title="Jawaban kurang tepat"
                >
                  <ThumbDownIcon />
                </button>
              </>
            )}
          </div>
        )}

        {!streaming && thanked && <p className="thanks">Terima kasih atas masukan Anda.</p>}

        {!streaming && message.chatId && message.rating && !thanked && (
          <div className="feedback">
            <textarea
              value={draft}
              onChange={(e) => {
                setDraft(e.target.value)
                setSaved('idle')
              }}
              maxLength={2000}
              rows={2}
              placeholder={message.rating === -1 ? 'Apa yang salah atau kurang? (opsional)' : 'Catatan tambahan (opsional)'}
              aria-label="Komentar untuk jawaban ini"
            />
            <div className="feedback-row">
              <button className="btn-small" onClick={sendComment} disabled={!draft.trim() || saved === 'saving'}>
                Kirim komentar
              </button>
              {saved === 'fail' && <span className="error-text small">Gagal terkirim. Coba lagi.</span>}
            </div>
          </div>
        )}
      </div>
    </motion.div>
  )
}
