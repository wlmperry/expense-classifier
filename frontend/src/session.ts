// Where the login session token lives between page loads, and how the rest
// of the app finds out the session has ended.
//
// localStorage rather than a cookie: the frontend and backend are on
// different onrender.com subdomains, and browsers treat onrender.com as a
// public suffix, so a cookie set by the backend would be a third-party
// cookie that many browsers block. The tradeoff is that any script running
// on this page could read the token, which is why the app loads no
// third-party scripts besides Plaid Link.
//
// Every storage call is wrapped in try/catch: localStorage can throw (for
// example in some private-browsing modes), and the app should still work
// there, just without staying logged in across page loads.

const TOKEN_KEY = "expense-classifier.session-token"

export function getSessionToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

export function saveSessionToken(token: string): void {
  try {
    localStorage.setItem(TOKEN_KEY, token)
  } catch {
    // Not fatal: the user stays logged in until the page is reloaded.
  }
}

export function clearSessionToken(): void {
  try {
    localStorage.removeItem(TOKEN_KEY)
  } catch {
    // Nothing was saved, so there is nothing to clear.
  }
}

// AuthGate registers this so it can show the login screen when the backend
// reports that the saved session is no longer valid (expired, or ended by
// a password change). api.ts calls it on any 401 sent with a token.
let sessionEndedHandler: (() => void) | null = null

export function onSessionEnded(handler: (() => void) | null): void {
  sessionEndedHandler = handler
}

export function endSession(): void {
  clearSessionToken()
  sessionEndedHandler?.()
}
