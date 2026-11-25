import { AnimatePresence, motion } from 'motion/react'
import type { Conversation } from '../types'
import { PlusIcon, TrashIcon, UploadIcon } from '../icons'

type Props = {
  items: Conversation[]
  activeId: string | null
  open: boolean
  version: string
  onNew: () => void
  onSelect: (id: string) => void
  onDelete: (id: string) => void
  onClose: () => void
  onLogout?: () => void
  onFiles: () => void
  filesActive: boolean
}

export default function Sidebar({ items, activeId, open, version, onNew, onSelect, onDelete, onClose, onLogout, onFiles, filesActive }: Props) {
  return (
    <>
      <div className={`scrim${open ? ' show' : ''}`} onClick={onClose} />
      <aside className={`sidebar${open ? ' open' : ''}`} aria-label="Riwayat percakapan">
        <button className="brand" onClick={onNew} title="Mulai percakapan baru">
          <span className="logo" aria-hidden="true" />
          <span>HubTer Insight</span>
        </button>

        <button className="new-chat" onClick={onNew}>
          <PlusIcon /> Percakapan baru
        </button>

        <button className={`nav-link${filesActive ? ' active' : ''}`} onClick={onFiles} aria-current={filesActive ? 'page' : undefined}>
          <UploadIcon /> Dokumen
        </button>

        <nav className="history" aria-label="Percakapan">
          {items.length === 0 && <p className="muted small">Belum ada percakapan.</p>}
          <AnimatePresence initial={false}>
            {items.map((c) => (
              <motion.div
                key={c.id}
                layout="position"
                className={`history-item${c.id === activeId ? ' active' : ''}`}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -8 }}
                transition={{ duration: 0.2 }}
              >
                <button
                  className="history-title"
                  onClick={() => onSelect(c.id)}
                  title={c.title}
                  aria-current={c.id === activeId ? 'page' : undefined}
                >
                  {c.title}
                </button>
                <button
                  className="icon-btn"
                  aria-label={`Hapus percakapan: ${c.title}`}
                  onClick={() => {
                    if (window.confirm('Hapus percakapan ini?')) onDelete(c.id)
                  }}
                >
                  <TrashIcon />
                </button>
              </motion.div>
            ))}
          </AnimatePresence>
        </nav>

        <div className="sidebar-foot">
          {version && <p className="muted small sidebar-note">HubTer Insight {version}</p>}
          {onLogout && (
            <button className="link-btn small" onClick={onLogout}>
              Keluar
            </button>
          )}
        </div>
      </aside>
    </>
  )
}
