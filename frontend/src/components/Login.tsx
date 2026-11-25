import { useState } from 'react'
import type { FormEvent } from 'react'
import { login } from '../api'
import { EyeIcon, EyeOffIcon } from '../icons'

type Props = { onSuccess: () => void }

/** Layar masuk untuk pemakai internal: satu nama pengguna dan kata sandi bersama, tanpa registrasi. */
export default function Login({ onSuccess }: Props) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (busy) return
    setBusy(true)
    setError('')
    const result = await login(username, password)
    setBusy(false)
    if (result.ok) onSuccess()
    else setError(result.message)
  }

  return (
    <main className="login-page">
      <form className="login-card" onSubmit={submit}>
        <span className="logo big" aria-hidden="true" />
        <h1 className="login-title">HubTer Insight</h1>

        <label className="login-field">
          <span>Nama pengguna</span>
          <input
            name="username"
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            autoCapitalize="none"
            autoCorrect="off"
            spellCheck={false}
            required
          />
        </label>

        <label className="login-field">
          <span>Kata sandi</span>
          <div className="password-wrap">
            <input
              name="password"
              type={showPassword ? 'text' : 'password'}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              autoCapitalize="none"
              autoCorrect="off"
              spellCheck={false}
              required
            />
            <button
              type="button"
              className="password-toggle"
              onClick={() => setShowPassword((v) => !v)}
              aria-label={showPassword ? 'Sembunyikan kata sandi' : 'Tampilkan kata sandi'}
              aria-pressed={showPassword}
              title={showPassword ? 'Sembunyikan kata sandi' : 'Tampilkan kata sandi'}
            >
              {showPassword ? <EyeOffIcon /> : <EyeIcon />}
            </button>
          </div>
        </label>

        {error && (
          <div className="error-box login-error" role="alert">
            {error}
          </div>
        )}

        <button className="login-btn" type="submit" disabled={busy || !username.trim() || !password}>
          {busy ? 'Memeriksa…' : 'Masuk'}
        </button>
      </form>
    </main>
  )
}
