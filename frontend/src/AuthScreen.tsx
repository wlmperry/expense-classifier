import { useState, type FormEvent } from "react"
import { login, register } from "./api"
import Brand from "./Brand"
import type { User } from "./types"

interface AuthScreenProps {
  // Called once login or sign-up succeeds. The caller saves the token.
  onAuthenticated: (user: User, token: string) => void
}

// One form that switches between logging in and signing up, since both
// send the same two fields.
function AuthScreen({ onAuthenticated }: AuthScreenProps) {
  const [mode, setMode] = useState<"login" | "register">("login")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const isRegistering = mode === "register"

  function switchMode() {
    setMode(isRegistering ? "login" : "register")
    setError(null)
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      const send = isRegistering ? register : login
      const { token, user } = await send({ email, password })
      onAuthenticated(user, token)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
      setSubmitting(false)
    }
  }

  const title = isRegistering ? "Create an account" : "Log in"

  return (
    <main className="auth-page">
      <Brand />
      <form className="card auth-form" onSubmit={handleSubmit} aria-label={title}>
        <h1>{title}</h1>
        <label>
          Email
          <input
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </label>
        <label>
          Password
          <input
            type="password"
            autoComplete={isRegistering ? "new-password" : "current-password"}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </label>
        {isRegistering && <p className="auth-form__hint">At least 8 characters.</p>}
        {error && (
          <p role="alert" className="message message--error">
            {error}
          </p>
        )}
        <button className="button button--primary" type="submit" disabled={submitting}>
          {submitting ? "Please wait..." : isRegistering ? "Sign up" : "Log in"}
        </button>
        <p className="auth-form__switch">
          {isRegistering ? "Already have an account?" : "New here?"}{" "}
          <button type="button" className="link-button" onClick={switchMode}>
            {isRegistering ? "Log in" : "Create an account"}
          </button>
        </p>
      </form>
    </main>
  )
}

export default AuthScreen
