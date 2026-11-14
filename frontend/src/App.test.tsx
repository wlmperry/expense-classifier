import { fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'

// ConnectBank fetches its own link token lazily (on click), but a couple of
// tests below click into an edit/save flow that can race with it. Routing
// any such call to a harmless, always-successful response keeps each test's
// fetch stub focused on the /expenses behavior it actually means to test.
function stubPlaidLinkToken(url: string) {
  if (!url.includes('/plaid/')) {
    return null
  }
  return Promise.resolve({
    ok: true,
    status: 200,
    json: () => Promise.resolve({ link_token: 'link-sandbox-test', expiration: '2026-01-01T00:00:00Z' }),
  })
}

function stubFetch(response: { ok: boolean; status?: number; body: unknown }) {
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string) =>
      stubPlaidLinkToken(url) ??
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

  it('shows confidence as a percentage, or a dash when null', async () => {
    stubFetch({
      ok: true,
      body: [
        { id: 1, merchant: 'Corner Store', description: 'Coffee', amount: '3.50', expense_date: '2026-09-01', category: 'Coffee Shops', confidence: '0.9' },
        { id: 2, merchant: 'Gas Station', description: 'Fuel', amount: '42.00', expense_date: '2026-09-02', category: 'Gas & Fuel', confidence: null },
      ],
    })

    render(<App />)

    expect(await screen.findByText('90%')).toBeInTheDocument()
    expect(screen.getByText('—')).toBeInTheDocument()
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

  it('adds a newly created expense to the displayed list', async () => {
    const saved = { id: 1, merchant: 'Corner Store', description: 'Coffee', amount: '3.50', expense_date: '2026-09-01' }
    vi.stubGlobal(
      'fetch',
      vi.fn((_url: string, init?: RequestInit) =>
        Promise.resolve({
          ok: true,
          status: init?.method === 'POST' ? 201 : 200,
          json: () => Promise.resolve(init?.method === 'POST' ? saved : []),
        }),
      ),
    )

    render(<App />)
    expect(await screen.findByText(/no expenses found/i)).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText(/merchant/i), { target: { value: 'Corner Store' } })
    fireEvent.change(screen.getByLabelText(/description/i), { target: { value: 'Coffee' } })
    fireEvent.change(screen.getByLabelText(/amount/i), { target: { value: '3.50' } })
    fireEvent.change(screen.getByLabelText(/date/i), { target: { value: '2026-09-01' } })
    fireEvent.click(screen.getByRole('button', { name: /add expense/i }))

    expect(await screen.findByRole('cell', { name: 'Corner Store' })).toBeInTheDocument()
    expect(screen.queryByText(/no expenses found/i)).not.toBeInTheDocument()
  })

  it('shows an error state when the network request itself fails', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn((url: string) => stubPlaidLinkToken(url) ?? Promise.reject(new TypeError('Failed to fetch'))),
    )

    render(<App />)

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(/failed to fetch/i)
  })

  const oneExpense = { id: 1, merchant: 'Corner Store', description: 'Coffee', amount: '3.50', expense_date: '2026-09-01' }

  it('removes the expense when delete is confirmed', async () => {
    vi.stubGlobal('confirm', vi.fn(() => true))
    const fetchMock = vi.fn((_url: string, init?: RequestInit) =>
      Promise.resolve({
        ok: true,
        status: init?.method === 'DELETE' ? 204 : 200,
        json: () => Promise.resolve(init?.method === 'DELETE' ? undefined : [oneExpense]),
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    render(<App />)
    expect(await screen.findByText('Corner Store')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /delete/i }))

    expect(await screen.findByText(/no expenses found/i)).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringMatching(/\/expenses\/1$/),
      expect.objectContaining({ method: 'DELETE' }),
    )
  })

  it('keeps the expense when delete is cancelled', async () => {
    vi.stubGlobal('confirm', vi.fn(() => false))
    const fetchMock = vi.fn(() =>
      Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve([oneExpense]) }),
    )
    vi.stubGlobal('fetch', fetchMock)

    render(<App />)
    expect(await screen.findByText('Corner Store')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /delete/i }))

    expect(screen.getByText('Corner Store')).toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalledWith(expect.anything(), expect.objectContaining({ method: 'DELETE' }))
  })

  it('opens the edit form prefilled, saves, and shows the updated row', async () => {
    const updated = { ...oneExpense, amount: '50.00' }
    const fetchMock = vi.fn((url: string, init?: RequestInit) => {
      const plaidStub = stubPlaidLinkToken(url)
      if (plaidStub) return plaidStub
      if (init?.method === 'PATCH') {
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(updated) })
      }
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve([oneExpense]) })
    })
    vi.stubGlobal('fetch', fetchMock)

    render(<App />)
    expect(await screen.findByText('Corner Store')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /edit expense at corner store/i }))
    expect(screen.getByRole('heading', { name: /edit expense/i })).toBeInTheDocument()
    expect(screen.getByLabelText(/amount/i)).toHaveValue('3.50')

    fireEvent.change(screen.getByLabelText(/amount/i), { target: { value: '50.00' } })
    fireEvent.click(screen.getByRole('button', { name: /^save$/i }))

    expect(await screen.findByText('50.00')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /add expense/i })).toBeInTheDocument()
  })

  it('discards changes when Cancel is clicked and keeps the original row', async () => {
    stubFetch({ ok: true, body: [oneExpense] })

    render(<App />)
    expect(await screen.findByText('Corner Store')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /edit expense at corner store/i }))
    fireEvent.change(screen.getByLabelText(/amount/i), { target: { value: '999.99' } })
    fireEvent.click(screen.getByRole('button', { name: /cancel/i }))

    expect(screen.getByRole('heading', { name: /add expense/i })).toBeInTheDocument()
    expect(screen.getByText('3.50')).toBeInTheDocument()
    expect(screen.queryByText('999.99')).not.toBeInTheDocument()
  })

  it('cancels an in-progress edit when the expense being edited is deleted', async () => {
    vi.stubGlobal('confirm', vi.fn(() => true))
    const fetchMock = vi.fn((_url: string, init?: RequestInit) =>
      Promise.resolve({
        ok: true,
        status: init?.method === 'DELETE' ? 204 : 200,
        json: () => Promise.resolve(init?.method === 'DELETE' ? undefined : [oneExpense]),
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    render(<App />)
    expect(await screen.findByText('Corner Store')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /edit expense at corner store/i }))
    expect(screen.getByRole('heading', { name: /edit expense/i })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /delete/i }))

    expect(await screen.findByText(/no expenses found/i)).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /add expense/i })).toBeInTheDocument()
  })

  it('shows an error and keeps the expense when delete fails', async () => {
    vi.stubGlobal('confirm', vi.fn(() => true))
    vi.stubGlobal(
      'fetch',
      vi.fn((_url: string, init?: RequestInit) =>
        Promise.resolve({
          ok: init?.method !== 'DELETE',
          status: init?.method === 'DELETE' ? 404 : 200,
          json: () => Promise.resolve(init?.method === 'DELETE' ? null : [oneExpense]),
        }),
      ),
    )

    render(<App />)
    expect(await screen.findByText('Corner Store')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /delete/i }))

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(/failed to delete/i)
    expect(screen.getByText('Corner Store')).toBeInTheDocument()
  })

  describe('spending summary', () => {
    const coffee = { ...oneExpense, category: 'Coffee Shops', confidence: null }
    const fuel = { id: 2, merchant: 'Gas Station', description: 'Fuel', amount: '42.00', expense_date: '2026-09-02', category: 'Gas & Fuel', confidence: null }

    function summaryRegion() {
      return screen.getByRole('region', { name: /spending summary/i })
    }

    it('shows the total and a per-category breakdown of the loaded expenses', async () => {
      stubFetch({ ok: true, body: [coffee, fuel] })

      render(<App />)
      expect(await screen.findByText('Corner Store')).toBeInTheDocument()

      const summary = within(summaryRegion())
      expect(summary.getByText('$45.50')).toBeInTheDocument()
      expect(summary.getByText(/across 2 expenses/i)).toBeInTheDocument()

      const rows = within(summary.getByRole('list', { name: /spending by category/i })).getAllByRole('listitem')
      expect(rows).toHaveLength(2)
      // Highest spend first.
      expect(rows[0]).toHaveTextContent('Gas & Fuel')
      expect(rows[0]).toHaveTextContent('$42.00')
      expect(rows[0]).toHaveTextContent('92%')
      expect(rows[1]).toHaveTextContent('Coffee Shops')
      expect(rows[1]).toHaveTextContent('$3.50')
      expect(rows[1]).toHaveTextContent('8%')
    })

    it('shows an empty message when there are no expenses', async () => {
      stubFetch({ ok: true, body: [] })

      render(<App />)
      expect(await screen.findByText(/no expenses found/i)).toBeInTheDocument()

      const summary = within(summaryRegion())
      expect(summary.getByText('$0.00')).toBeInTheDocument()
      expect(summary.getByText(/no spending to summarize yet/i)).toBeInTheDocument()
    })

    it('is not shown while expenses are loading or when loading fails', async () => {
      stubFetch({ ok: false, status: 500, body: null })

      render(<App />)
      expect(screen.queryByRole('region', { name: /spending summary/i })).not.toBeInTheDocument()

      await screen.findByRole('alert')
      expect(screen.queryByRole('region', { name: /spending summary/i })).not.toBeInTheDocument()
    })

    it('updates when an expense is added', async () => {
      const saved = { ...fuel }
      vi.stubGlobal(
        'fetch',
        vi.fn((url: string, init?: RequestInit) =>
          stubPlaidLinkToken(url) ??
          Promise.resolve({
            ok: true,
            status: init?.method === 'POST' ? 201 : 200,
            json: () => Promise.resolve(init?.method === 'POST' ? saved : [coffee]),
          }),
        ),
      )

      render(<App />)
      expect(await screen.findByText('Corner Store')).toBeInTheDocument()
      expect(within(summaryRegion()).getByText('$3.50', { selector: '.summary-card__total-amount' })).toBeInTheDocument()

      fireEvent.change(screen.getByLabelText(/merchant/i), { target: { value: 'Gas Station' } })
      fireEvent.change(screen.getByLabelText(/description/i), { target: { value: 'Fuel' } })
      fireEvent.change(screen.getByLabelText(/amount/i), { target: { value: '42.00' } })
      fireEvent.change(screen.getByLabelText(/date/i), { target: { value: '2026-09-02' } })
      fireEvent.click(screen.getByRole('button', { name: /add expense/i }))

      expect(await within(summaryRegion()).findByText('$45.50')).toBeInTheDocument()
    })

    it('updates when an expense is edited', async () => {
      const updated = { ...coffee, amount: '50.00' }
      vi.stubGlobal(
        'fetch',
        vi.fn((url: string, init?: RequestInit) => {
          const plaidStub = stubPlaidLinkToken(url)
          if (plaidStub) return plaidStub
          if (init?.method === 'PATCH') {
            return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(updated) })
          }
          return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve([coffee, fuel]) })
        }),
      )

      render(<App />)
      expect(await screen.findByText('Corner Store')).toBeInTheDocument()
      expect(within(summaryRegion()).getByText('$45.50')).toBeInTheDocument()

      fireEvent.click(screen.getByRole('button', { name: /edit expense at corner store/i }))
      fireEvent.change(screen.getByLabelText(/amount/i), { target: { value: '50.00' } })
      fireEvent.click(screen.getByRole('button', { name: /^save$/i }))

      expect(await within(summaryRegion()).findByText('$92.00')).toBeInTheDocument()
    })

    it('updates when an expense is deleted', async () => {
      vi.stubGlobal('confirm', vi.fn(() => true))
      vi.stubGlobal(
        'fetch',
        vi.fn((_url: string, init?: RequestInit) =>
          Promise.resolve({
            ok: true,
            status: init?.method === 'DELETE' ? 204 : 200,
            json: () => Promise.resolve(init?.method === 'DELETE' ? undefined : [coffee, fuel]),
          }),
        ),
      )

      render(<App />)
      expect(await screen.findByText('Corner Store')).toBeInTheDocument()
      expect(within(summaryRegion()).getByText('$45.50')).toBeInTheDocument()

      fireEvent.click(screen.getByRole('button', { name: /delete expense at gas station/i }))

      const summary = within(summaryRegion())
      expect(await summary.findByText('$3.50', { selector: '.summary-card__total-amount' })).toBeInTheDocument()
      expect(summary.queryByText('Gas & Fuel')).not.toBeInTheDocument()
    })
  })
})
