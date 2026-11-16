import { useEffect, useState } from "react"
import { fetchCurrentUser, logout } from "./api"
import App from "./App"
import AuthScreen from "./AuthScreen"
import { clearSessionToken, getSessionToken, onSessionEnded, saveSessionToken } from "./session"
import type { User } from "./types"

// Decides what to show: the login screen when nobody is logged in, or the
// app for the logged-in user. On page load, a saved token is checked with
// GET /auth/me first, since it may have expired while the page was closed.
function AuthGate() {
  const [user, setUser] = useState<User | null>(null)
  const [checkingSavedSession, setCheckingSavedSession] = useState(
    () => getSessionToken() !== null,
  )

  // Runs once, on page load. Later logins set the user directly.
  useEffect(() => {
    if (getSessionToken() === null) {
      return
    }
    fetchCurrentUser()
      .then(setUser)
      .catch(() => clearSessionToken())
      .finally(() => setCheckingSavedSession(false))
  }, [])

  useEffect(() => {
    onSessionEnded(() => setUser(null))
    return () => onSessionEnded(null)
  }, [])

  function handleAuthenticated(loggedIn: User, token: string) {
    saveSessionToken(token)
    setUser(loggedIn)
  }

  async function handleLogout() {
    try {
      await logout()
    } catch {
      // Logging out locally still works if the request fails.
    }
    clearSessionToken()
    setUser(null)
  }

  if (checkingSavedSession) {
    return <p className="auth-page__loading">Loading...</p>
  }
  if (user === null) {
    return <AuthScreen onAuthenticated={handleAuthenticated} />
  }
  return <App user={user} onLogout={handleLogout} />
}

export default AuthGate
