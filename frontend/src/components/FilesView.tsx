import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { ChangeEvent, DragEvent } from 'react'
import { fileUrl, listFiles, uploadFile } from '../api'
import type { FileInfo, FileList } from '../api'
import { DownloadIcon, FileIcon, SearchIcon, UploadIcon } from '../icons'

const ALLOWED = ['md', 'pdf', 'xlsx', 'pptx', 'docx', 'png', 'jpg', 'jpeg']
const ACCEPT = ALLOWED.map((e) => `.${e}`).join(',')

type Job = { id: number; name: string; percent: number; state: 'uploading' | 'done' | 'error'; message?: string }

const extOf = (name: string) => name.split('.').pop()?.toLowerCase() ?? ''

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

function formatDate(iso: string): string {
  const d = new Date(iso)
  return Number.isNaN(d.getTime())
    ? ''
    : d.toLocaleString('id-ID', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

let jobSeq = 0

/** Halaman Dokumen: unggah berkas, lihat daftar berkas di server, cari. Tanpa pratinjau. */
export default function FilesView() {
  const [data, setData] = useState<FileList | null>(null)
  const [loading, setLoading] = useState(true)
  const [failed, setFailed] = useState(false)
  const [query, setQuery] = useState('')
  const [jobs, setJobs] = useState<Job[]>([])
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const refresh = useCallback(async () => {
    const result = await listFiles()
    setFailed(result === null)
    if (result) setData(result)
    setLoading(false)
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const maxMb = data?.maxFileMb ?? 25

  const patchJob = (id: number, patch: Partial<Job>) =>
    setJobs((prev) => prev.map((j) => (j.id === id ? { ...j, ...patch } : j)))

  const upload = useCallback(
    async (files: File[]) => {
      for (const file of files) {
        const id = ++jobSeq
        const base: Job = { id, name: file.name, percent: 0, state: 'uploading' }
        if (!ALLOWED.includes(extOf(file.name))) {
          setJobs((prev) => [{ ...base, state: 'error', message: 'Jenis berkas tidak diizinkan.' }, ...prev])
          continue
        }
        if (file.size > maxMb * 1024 * 1024) {
          setJobs((prev) => [{ ...base, state: 'error', message: `Terlalu besar (maksimal ${maxMb} MB).` }, ...prev])
          continue
        }
        setJobs((prev) => [base, ...prev])
        const result = await uploadFile(file, (percent) => patchJob(id, { percent }))
        if (result.ok) {
          patchJob(id, { state: 'done', percent: 100, name: result.name })
          void refresh()
        } else {
          patchJob(id, { state: 'error', message: result.message })
        }
      }
    },
    [maxMb, refresh],
  )

  const onPick = (e: ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? [])
    e.target.value = '' // supaya berkas yang sama bisa dipilih lagi
    if (files.length) void upload(files)
  }

  const onDrop = (e: DragEvent) => {
    e.preventDefault()
    setDragging(false)
    const files = Array.from(e.dataTransfer.files)
    if (files.length) void upload(files)
  }

  const shown: FileInfo[] = useMemo(() => {
    const q = query.trim().toLowerCase()
    const all = data?.files ?? []
    return q ? all.filter((f) => f.name.toLowerCase().includes(q)) : all
  }, [data, query])

  return (
    <div className="files-page">
      <div className="files-inner">
        <section
          className={`dropzone${dragging ? ' over' : ''}`}
          onDragOver={(e) => {
            e.preventDefault()
            setDragging(true)
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
        >
          <UploadIcon />
          <p className="dropzone-title">Seret berkas ke sini, atau</p>
          <button className="btn-small" type="button" onClick={() => inputRef.current?.click()}>
            Pilih berkas
          </button>
          <input ref={inputRef} type="file" accept={ACCEPT} multiple hidden onChange={onPick} />
          <p className="muted small">
            .md .pdf .xlsx .pptx .docx .png .jpg .jpeg · maksimal {maxMb} MB per berkas
          </p>
        </section>

        {jobs.length > 0 && (
          <ul className="jobs" aria-live="polite">
            {jobs.slice(0, 8).map((j) => (
              <li key={j.id} className={`job ${j.state}`}>
                <span className="job-name">{j.name}</span>
                {j.state === 'uploading' && (
                  <span className="job-status">
                    <span className="bar" aria-hidden="true">
                      <span style={{ width: `${j.percent}%` }} />
                    </span>
                    {j.percent}%
                  </span>
                )}
                {j.state === 'done' && <span className="job-status ok">Terunggah</span>}
                {j.state === 'error' && <span className="job-status error-text">{j.message}</span>}
              </li>
            ))}
          </ul>
        )}

        <div className="files-head">
          <label className="search">
            <SearchIcon />
            <input
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Cari nama berkas…"
              aria-label="Cari nama berkas"
            />
          </label>
          <span className="muted small">
            {data
              ? `${shown.length}${query.trim() ? ` dari ${data.files.length}` : ''} berkas · ${formatSize(data.usedBytes)}`
              : ''}
          </span>
        </div>

        {loading && <p className="muted">Memuat daftar…</p>}
        {failed && !loading && (
          <p className="error-text">
            Gagal memuat daftar berkas.{' '}
            <button className="link-btn" onClick={() => void refresh()}>
              Coba lagi
            </button>
          </p>
        )}
        {!loading && !failed && shown.length === 0 && (
          <p className="muted">{query.trim() ? 'Tidak ada berkas yang cocok.' : 'Belum ada berkas.'}</p>
        )}

        <ul className="file-list">
          {shown.map((f) => (
            <li key={f.name} className="file-row">
              <span className="file-icon">
                <FileIcon />
              </span>
              <span className="file-main">
                <span className="file-name" title={f.name}>
                  {f.name}
                </span>
                <span className="muted small">
                  {formatSize(f.size)} · {formatDate(f.modified)}
                </span>
              </span>
              <a className="icon-btn" href={fileUrl(f.name)} download aria-label={`Unduh ${f.name}`} title="Unduh">
                <DownloadIcon />
              </a>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
