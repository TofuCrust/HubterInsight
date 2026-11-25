import type { ReactNode } from 'react'

function Svg({ children }: { children: ReactNode }) {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {children}
    </svg>
  )
}

export const PlusIcon = () => (
  <Svg>
    <path d="M12 5v14M5 12h14" />
  </Svg>
)
export const TrashIcon = () => (
  <Svg>
    <path d="M3 6h18M8 6V4h8v2M6 6l1 14h10l1-14" />
  </Svg>
)
export const SendIcon = () => (
  <Svg>
    <path d="M12 19V5M5 12l7-7 7 7" />
  </Svg>
)
export const StopIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
    <rect x="5" y="5" width="14" height="14" rx="2" />
  </svg>
)
export const MenuIcon = () => (
  <Svg>
    <path d="M4 7h16M4 12h16M4 17h16" />
  </Svg>
)
export const CopyIcon = () => (
  <Svg>
    <rect x="9" y="9" width="11" height="11" rx="2" />
    <path d="M5 15V6a2 2 0 0 1 2-2h9" />
  </Svg>
)
export const CheckIcon = () => (
  <Svg>
    <path d="M5 13l4 4L19 7" />
  </Svg>
)
export const RefreshIcon = () => (
  <Svg>
    <path d="M20 11a8 8 0 1 0-2.3 5.7M20 4v7h-7" />
  </Svg>
)
export const ThumbUpIcon = () => (
  <Svg>
    <path d="M7 11v9H4v-9zM7 11l4-8a2 2 0 0 1 2 2v4h6a2 2 0 0 1 2 2.3l-1.2 7A2 2 0 0 1 17.8 20H7" />
  </Svg>
)
export const ThumbDownIcon = () => (
  <Svg>
    <path d="M17 13V4h3v9zM17 13l-4 8a2 2 0 0 1-2-2v-4H5a2 2 0 0 1-2-2.3l1.2-7A2 2 0 0 1 6.2 4H17" />
  </Svg>
)
export const SunIcon = () => (
  <Svg>
    <circle cx="12" cy="12" r="4" />
    <path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6l1.4 1.4M17 17l1.4 1.4M5.6 18.4L7 17M17 7l1.4-1.4" />
  </Svg>
)
export const MoonIcon = () => (
  <Svg>
    <path d="M20 14.5A8 8 0 0 1 9.5 4 8 8 0 1 0 20 14.5z" />
  </Svg>
)
export const ChevronIcon = () => (
  <Svg>
    <path d="M9 6l6 6-6 6" />
  </Svg>
)
export const DocIcon = () => (
  <Svg>
    <path d="M7 3h7l5 5v13H7z" />
    <path d="M14 3v5h5M10 13h6M10 17h6" />
  </Svg>
)

export const EyeIcon = () => (
  <Svg>
    <path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z" />
    <circle cx="12" cy="12" r="3" />
  </Svg>
)
export const EyeOffIcon = () => (
  <Svg>
    <path d="M17.9 17.9A10.4 10.4 0 0 1 12 19c-6.4 0-10-7-10-7a17.8 17.8 0 0 1 4.1-4.9M9.9 5.2A9.7 9.7 0 0 1 12 5c6.4 0 10 7 10 7a17.7 17.7 0 0 1-2.2 3.2M1 1l22 22" />
    <path d="M9.9 9.9a3 3 0 0 0 4.2 4.2" />
  </Svg>
)
export const UploadIcon = () => (
  <Svg>
    <path d="M12 16V4M6 10l6-6 6 6M4 20h16" />
  </Svg>
)
export const FileIcon = () => (
  <Svg>
    <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
    <path d="M14 3v5h5" />
  </Svg>
)
export const SearchIcon = () => (
  <Svg>
    <circle cx="11" cy="11" r="7" />
    <path d="M21 21l-4.3-4.3" />
  </Svg>
)
export const DownloadIcon = () => (
  <Svg>
    <path d="M12 4v12M6 10l6 6 6-6M4 20h16" />
  </Svg>
)
