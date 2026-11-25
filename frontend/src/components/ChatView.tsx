import { Fragment, useEffect, useRef, useState } from 'react'
import { pickGreeting } from '../greetings'
import { AnimatePresence, motion, type Variants } from 'motion/react'
import type { ChatMessage } from '../types'
import MessageItem from './MessageItem'

const SUGGESTIONS = [
  'Apa saja aspek yang membuat pengusaha pabrik dianggap memiliki hubungan keterkaitan?',
  'Apa akibat penetapan hubungan keterkaitan terhadap golongan dan tarif cukai?',
  'Apa perubahan yang dibuat PMK 131/PMK.011/2013 terhadap PMK 78/PMK.011/2013?',
  'Apa yang harus dilakukan Kepala Kantor untuk mendapatkan indikasi hubungan keterkaitan?',
]

const heroList: Variants = { hidden: {}, show: { transition: { staggerChildren: 0.07, delayChildren: 0.05 } } }
const rise: Variants = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0, transition: { duration: 0.35, ease: [0.22, 1, 0.36, 1] } },
}

const words: Variants = { hidden: {}, show: { transition: { staggerChildren: 0.05 } } }
const word: Variants = {
  hidden: { opacity: 0, y: 10, filter: 'blur(6px)' },
  show: { opacity: 1, y: 0, filter: 'blur(0px)', transition: { duration: 0.4, ease: [0.22, 1, 0.36, 1] } },
}

/** Sapaan acak; dipilih sekali saat halaman sambutan tampil, muncul kata demi kata. */
function Greeting() {
  const [text] = useState(pickGreeting)
  return (
    <motion.h2 variants={words}>
      {text.split(' ').map((w, i) => (
        <Fragment key={i}>
          <motion.span className="word" variants={word}>
            {w}
          </motion.span>{' '}
        </Fragment>
      ))}
    </motion.h2>
  )
}

type Props = {
  messages: ChatMessage[]
  streamingId: string | null
  onSuggest: (text: string) => void
  onRegenerate: () => void
  onFeedback: (messageId: string, fb: { rating?: 1 | -1; comment?: string }) => Promise<boolean>
}

export default function ChatView({ messages, streamingId, onSuggest, onRegenerate, onFeedback }: Props) {
  const scroller = useRef<HTMLDivElement>(null)
  const stick = useRef(true)

  // Ikut turun saat jawaban mengalir dan saat selesai (tombol aksi muncul menambah tinggi)
  useEffect(() => {
    const el = scroller.current
    if (el && stick.current) el.scrollTop = el.scrollHeight
  }, [messages, streamingId])

  // Percakapan baru dibuka: mulai dari bawah
  useEffect(() => {
    stick.current = true
  }, [messages.length === 0])

  const onScroll = () => {
    const el = scroller.current
    if (!el) return
    stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80
  }

  if (messages.length === 0) {
    return (
      <div className="chat empty">
        <motion.div className="hero" variants={heroList} initial="hidden" animate="show">
          <motion.span className="logo big" aria-hidden="true" variants={rise} />
          <Greeting />
          <motion.p className="muted" variants={rise}>
            Tanyakan apa saja seputar Hubungan Keterkaitan.
          </motion.p>
          <div className="suggestions">
            {SUGGESTIONS.map((s) => (
              <motion.button
                key={s}
                className="chip"
                variants={rise}
                whileHover={{ y: -2 }}
                whileTap={{ scale: 0.98 }}
                onClick={() => onSuggest(s)}
              >
                {s}
              </motion.button>
            ))}
          </div>
        </motion.div>
      </div>
    )
  }

  const lastAssistant = [...messages].reverse().find((m) => m.role === 'assistant')

  return (
    <div className="chat" ref={scroller} onScroll={onScroll}>
      <div className="thread">
        {/* initial={false}: pesan yang sudah ada saat dibuka tidak dianimasikan */}
        <AnimatePresence initial={false}>
          {messages.map((m) => (
            <MessageItem
              key={m.id}
              message={m}
              streaming={m.id === streamingId}
              canRegenerate={!streamingId && m.id === lastAssistant?.id}
              onRegenerate={onRegenerate}
              onFeedback={onFeedback}
            />
          ))}
        </AnimatePresence>
      </div>
    </div>
  )
}
