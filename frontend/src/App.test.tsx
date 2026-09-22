import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'

function stubFetch(response: { ok: boolean; status?: number; body: unknown }) {
  vi.stubGlobal(
    'fetch',
    vi.fn(() =>
      Promise.resolve({
        ok: response.ok,
        status: response.status ?? 200,
        json: () => Promise.resolve(response.body),
      }),
    ),
  )
}

describe('App', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('renders the application heading', () => {
    stubFetch({ ok: true, body: [] })
    render(<App />)
    expect(screen.getByRole('heading', { name: /expense classifier/i })).toBeInTheDocument()
  })

  it('shows a loading state before the fetch resolves', () => {
    vi.stubGlobal('fetch', vi.fn(() => new Promise(() => {})))
    render(<App />)
    expect(screen.getByText(/loading expenses/i)).toBeInTheDocument()
  })

  it('renders a table row for each returned expense, with amount and date as plain strings', async () => {
    stubFetch({
      ok: true,
      body: [
        { id: 1, merchant: 'Corner Store', description: 'Coffee', amount: '3.50', expense_date: '2026-09-01' },
        { id: 2, merchant: 'Gas Station', description: 'Fuel', amount: '42.00', expense_date: '2026-09-02' },
      ],
    })

    render(<App />)

    expect(await screen.findByText('Corner Store')).toBeInTheDocument()
    expect(screen.getByText('Coffee')).toBeInTheDocument()
    expect(screen.getByText('3.50')).toBeInTheDocument()
    expect(screen.getByText('2026-09-01')).toBeInTheDocument()
    expect(screen.getByText('Gas Station')).toBeInTheDocument()
    expect(screen.getByText('42.00')).toBeInTheDocument()
  })

  it('shows an empty state when the API returns no expenses', async () => {
    stubFetch({ ok: true, body: [] })

    render(<App />)

    expect(await screen.findByText(/no expenses found/i)).toBeInTheDocument()
  })

  it('shows an error state when the request fails', async () => {
    stubFetch({ ok: false, status: 500, body: null })

    render(<App />)

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(/failed to fetch expenses: 500/i)
  })
})
