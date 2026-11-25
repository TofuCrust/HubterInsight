import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { SendIcon, StopIcon } from '../icons'

type Props = {
  streaming: boolean
  onSend: (text: string) => void
  onStop: () => void
}

const MAX_CHARS = 4000

export default function Composer({ streaming, onSend, onStop }: Props) {
  const [text, setText] = useState('')
  const ref = useRef<HTMLTextAreaElement>(null)

  // Tinggi menyesuaikan isi; diukur ulang bila lebar berubah (mis. layout final, rotasi layar)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const fit = () => {
      el.style.height = 'auto'
      el.style.height = `${Math.min(el.scrollHeight, 200)}px`
    }
    fit()
    const ro = new ResizeObserver(fit)
    ro.observe(el.parentElement ?? el)
    return () => ro.disconnect()
  }, [text])

  const submit = () => {
    const value = text.trim()
    if (!value || streaming) return
    onSend(value)
    setText('')
  }

  return (
    <div className="composer-wrap">
      <form
        className="composer"
        onSubmit={(e) => {
          e.preventDefault()
          submit()
        }}
      >
        <textarea
          ref={ref}
          id="composer-input"
          rows={1}
          value={text}
          maxLength={MAX_CHARS}
          placeholder="Tanyakan sesuatu tentang dokumen referensi…"
          aria-label="Pertanyaan"
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault()
              submit()
            }
          }}
        />
        <AnimatePresence mode="wait" initial={false}>
          {streaming ? (
            <motion.button
              key="stop"
              type="button"
              className="send stop"
              onClick={onStop}
              aria-label="Hentikan jawaban"
              initial={{ scale: 0.6, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.6, opacity: 0 }}
              whileTap={{ scale: 0.92 }}
              transition={{ duration: 0.15 }}
            >
              <StopIcon />
            </motion.button>
          ) : (
            <motion.button
              key="send"
              type="submit"
              className="send"
              disabled={!text.trim()}
              aria-label="Kirim"
              initial={{ scale: 0.6, opacity: 0 }}
              animate={{ scale: 1, opacity: text.trim() ? 1 : 0.2 }}
              exit={{ scale: 0.6, opacity: 0 }}
              whileTap={{ scale: 0.92 }}
              transition={{ duration: 0.15 }}
            >
              <SendIcon />
            </motion.button>
          )}
        </AnimatePresence>
      </form>
      <p className="disclaimer">
        HubTer Insight dapat keliru dan bukan nasihat hukum. Periksa kembali ke dokumen sumber.
      </p>
    </div>
  )
}
