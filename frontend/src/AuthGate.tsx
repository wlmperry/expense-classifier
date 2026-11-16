import { useEffect, useState } from "react"
import { fetchCurrentUser, logout } from "./api"
import App from "./App"
import AuthScreen from "./AuthScreen"
import Brand from "./Brand"
import { clearSessionToken, getSessionToken, onSessionEnded, saveSessionToken } from "./session"
import type { User } from "./types"

// "checking": a saved token is being confirmed with GET /auth/me.
// "unreachable": that check failed for a reason other than the session
//   having ended, so the token is kept and the user can try again.
// "done": nothing left to check; show the app or the login screen.
type SessionCheck = "checking" | "unreachable" | "done"

// Decides what to show: the login screen when nobody is logged in, or the
// app for the logged-in user. On page load, a saved token is checked with
// GET /auth/me first, since it may have expired while the page was closed.
function AuthGate() {
  const [user, setUser] = useState<User | null>(null)
  const [sessionCheck, setSessionCheck] = useState<SessionCheck>(() =>
    getSessionToken() === null ? "done" : "checking",
  )

  // sessionCheck must already be "checking" when this runs: it starts that
  // way when a token is saved, and retrySessionCheck sets it.
  function checkSavedSession() {
    fetchCurrentUser()
      .then((current) => {
        setUser(current)
        setSessionCheck("done")
      })
      .catch(() => {
        // A 401 means the session really ended, and apiFetch has already
        // cleared the token by now, so the login screen shows. Any other
        // failure (the free-tier backend waking up, a 502, a dropped
        // connection) says nothing about the session, so the token is kept.
        setSessionCheck(getSessionToken() === null ? "done" : "unreachable")
      })
  }

  function retrySessionCheck() {
    setSessionCheck("checking")
    checkSavedSession()
  }

  // Runs once, on page load. Later logins set the user directly.
  useEffect(() => {
    if (getSessionToken() !== null) {
      checkSavedSession()
    }
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

  if (sessionCheck === "checking") {
    return <p className="auth-page__loading">Loading...</p>
  }
  if (sessionCheck === "unreachable") {
    return (
      <main className="auth-page">
        <Brand />
        <div className="card auth-form">
          <p role="alert" className="message message--error">
            Couldn't reach the server. It may be starting up, which can take about a minute.
          </p>
          <button className="button button--primary" type="button" onClick={retrySessionCheck}>
            Try again
          </button>
        </div>
      </main>
    )
  }
  if (user === null) {
    return <AuthScreen onAuthenticated={handleAuthenticated} />
  }
  return <App user={user} onLogout={handleLogout} />
}

export default AuthGate
