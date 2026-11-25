import { useCallback, useEffect, useState } from 'react'

export type Theme = 'light' | 'dark'

const KEY = 'hubter-theme'

const systemTheme = (): Theme =>
  typeof window !== 'undefined' && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'

const initial = (): Theme => {
  const set = document.documentElement.dataset.theme
  return set === 'light' || set === 'dark' ? set : systemTheme()
}

/** Tema mengikuti sistem sampai pengguna memilih sendiri; pilihan disimpan di browser. */
export function useTheme() {
  const [theme, setTheme] = useState<Theme>(initial)

  useEffect(() => {
    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    const onChange = () => {
      if (!document.documentElement.dataset.theme) setTheme(systemTheme())
    }
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [])

  const toggle = useCallback(() => {
    const next: Theme = theme === 'dark' ? 'light' : 'dark'
    document.documentElement.dataset.theme = next
    try {
      localStorage.setItem(KEY, next)
    } catch {
      /* penyimpanan tidak tersedia */
    }
    setTheme(next)
  }, [theme])

  return { theme, toggle }
}
