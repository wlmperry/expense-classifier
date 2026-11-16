import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import AuthGate from './AuthGate'
import { getSessionToken, saveSessionToken } from './session'

const USER = { id: 1, email: 'dave@example.com' }

type Route = { status: number; body?: unknown }

// A fake backend: answers each "METHOD /path" with the given status and body.
// Anything not listed gets a harmless 200, e.g. ConnectBank's /plaid/item check.
function stubBackend(routes: Record<string, Route>) {
  const fetchMock = vi.fn((url: string, init?: RequestInit) => {
    const path = new URL(url).pathname
    const route = routes[`${init?.method ?? 'GET'} ${path}`] ?? {
      status: 200,
      body: path === '/expenses' ? [] : { item_id: null },
    }
    return Promise.resolve({
      ok: route.status >= 200 && route.status < 300,
      status: route.status,
      json: () => Promise.resolve(route.body),
    })
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function authHeaderOf(fetchMock: ReturnType<typeof stubBackend>, method: string, path: string) {
  const call = fetchMock.mock.calls.find(
    ([url, init]) => (init?.method ?? 'GET') === method && new URL(url).pathname === path,
  )
  const headers = call?.[1]?.headers as Record<string, string> | undefined
  return headers?.Authorization
}

function submitCredentials(email: string, password: string) {
  fireEvent.change(screen.getByLabelText(/email/i), { target: { value: email } })
  fireEvent.change(screen.getByLabelText(/password/i), { target: { value: password } })
  fireEvent.submit(screen.getByRole('form'))
}

describe('AuthGate', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('shows the login screen when no session is saved', () => {
    const fetchMock = stubBackend({})

    render(<AuthGate />)

    expect(screen.getByRole('heading', { name: /log in/i })).toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('logs in, saves the token, and shows the app using that token', async () => {
    const fetchMock = stubBackend({
      'POST /auth/login': { status: 200, body: { token: 'token-123', user: USER } },
    })

    render(<AuthGate />)
    submitCredentials('dave@example.com', 'a-long-password')

    expect(await screen.findByRole('heading', { name: /expense classifier/i })).toBeInTheDocument()
    expect(screen.getByText('dave@example.com')).toBeInTheDocument()
    expect(getSessionToken()).toBe('token-123')
    await vi.waitFor(() => expect(authHeaderOf(fetchMock, 'GET', '/expenses')).toBe('Bearer token-123'))
  })

  it('shows an error and stays on the login screen when the password is wrong', async () => {
    stubBackend({ 'POST /auth/login': { status: 401, body: { detail: 'Invalid email or password' } } })

    render(<AuthGate />)
    submitCredentials('dave@example.com', 'wrong-password')

    expect(await screen.findByRole('alert')).toHaveTextContent(/invalid email or password/i)
    expect(screen.getByRole('heading', { name: /log in/i })).toBeInTheDocument()
    expect(getSessionToken()).toBeNull()
  })

  it('signs up through the register endpoint after switching modes', async () => {
    const fetchMock = stubBackend({
      'POST /auth/register': { status: 201, body: { token: 'token-new', user: USER } },
    })

    render(<AuthGate />)
    fireEvent.click(screen.getByRole('button', { name: /create an account/i }))
    expect(screen.getByRole('heading', { name: /create an account/i })).toBeInTheDocument()
    submitCredentials('dave@example.com', 'a-long-password')

    expect(await screen.findByRole('heading', { name: /expense classifier/i })).toBeInTheDocument()
    const registerCall = fetchMock.mock.calls.find(([url]) => url.endsWith('/auth/register'))
    expect(JSON.parse(registerCall?.[1]?.body as string)).toEqual({
      email: 'dave@example.com',
      password: 'a-long-password',
    })
  })

  it('shows a clear message when the email already has an account', async () => {
    stubBackend({ 'POST /auth/register': { status: 409, body: { detail: 'exists' } } })

    render(<AuthGate />)
    fireEvent.click(screen.getByRole('button', { name: /create an account/i }))
    submitCredentials('dave@example.com', 'a-long-password')

    expect(await screen.findByRole('alert')).toHaveTextContent(/already exists/i)
  })

  it('skips the login screen when a saved session is still valid', async () => {
    saveSessionToken('token-saved')
    const fetchMock = stubBackend({ 'GET /auth/me': { status: 200, body: USER } })

    render(<AuthGate />)

    expect(await screen.findByRole('heading', { name: /expense classifier/i })).toBeInTheDocument()
    expect(authHeaderOf(fetchMock, 'GET', '/auth/me')).toBe('Bearer token-saved')
  })

  it('shows the login screen and forgets the token when the saved session has expired', async () => {
    saveSessionToken('token-expired')
    stubBackend({ 'GET /auth/me': { status: 401, body: { detail: 'expired' } } })

    render(<AuthGate />)

    expect(await screen.findByRole('heading', { name: /log in/i })).toBeInTheDocument()
    expect(getSessionToken()).toBeNull()
  })

  it('logs out: ends the session on the backend and returns to the login screen', async () => {
    saveSessionToken('token-saved')
    const fetchMock = stubBackend({
      'GET /auth/me': { status: 200, body: USER },
      'POST /auth/logout': { status: 204 },
    })

    render(<AuthGate />)
    fireEvent.click(await screen.findByRole('button', { name: /log out/i }))

    expect(await screen.findByRole('heading', { name: /log in/i })).toBeInTheDocument()
    expect(authHeaderOf(fetchMock, 'POST', '/auth/logout')).toBe('Bearer token-saved')
    expect(getSessionToken()).toBeNull()
  })

  it('returns to the login screen when the session ends while using the app', async () => {
    saveSessionToken('token-saved')
    stubBackend({
      'GET /auth/me': { status: 200, body: USER },
      'GET /expenses': { status: 401, body: { detail: 'expired' } },
    })

    render(<AuthGate />)

    expect(await screen.findByRole('heading', { name: /log in/i })).toBeInTheDocument()
    expect(getSessionToken()).toBeNull()
  })
})
