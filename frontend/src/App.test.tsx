import { fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'

const testUser = { id: 1, email: 'test-user@example.com' }

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

// The app opens on the Overview tab. The expense table and form are on
// Transactions, and the summary and patterns cards are on Insights.
function showTab(name: 'Overview' | 'Transactions' | 'Insights') {
  fireEvent.click(screen.getByRole('button', { name }))
}

describe('App', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('opens on the Overview tab', () => {
    stubFetch({ ok: true, body: [] })
    render(<App user={testUser} onLogout={() => {}} />)
    expect(screen.getByRole('heading', { level: 1, name: /your spending/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Overview' })).toHaveAttribute('aria-current', 'page')
  })

  it('shows a loading state before the fetch resolves', () => {
    vi.stubGlobal('fetch', vi.fn(() => new Promise(() => {})))
    render(<App user={testUser} onLogout={() => {}} />)
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

    render(<App user={testUser} onLogout={() => {}} />)
    showTab('Transactions')

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

    render(<App user={testUser} onLogout={() => {}} />)
    showTab('Transactions')

    expect(await screen.findByText('90%')).toBeInTheDocument()
    expect(screen.getByText('—')).toBeInTheDocument()
  })

  it('labels whether the rules or the ML model picked each category', async () => {
    stubFetch({
      ok: true,
      body: [
        { id: 1, merchant: 'Starbucks', description: 'Latte', amount: '5.00', expense_date: '2026-09-01', category: 'Coffee Shops', confidence: '0.75', category_source: 'rules' },
        { id: 2, merchant: 'Valley Petro', description: 'Diesel', amount: '40.00', expense_date: '2026-09-02', category: 'Gas & Fuel', confidence: '0.81', category_source: 'model' },
        { id: 3, merchant: 'Corner Store', description: 'Snacks', amount: '3.00', expense_date: '2026-09-03', category: 'Other', confidence: null, category_source: null },
      ],
    })

    render(<App user={testUser} onLogout={() => {}} />)
    showTab('Transactions')

    const rowFor = async (merchant: string) => (await screen.findByRole('cell', { name: merchant })).closest('tr')!
    expect(within(await rowFor('Starbucks')).getByText('Rules')).toBeInTheDocument()
    expect(within(await rowFor('Valley Petro')).getByText('ML')).toBeInTheDocument()
    const personRow = within(await rowFor('Corner Store'))
    expect(personRow.queryByText('ML')).not.toBeInTheDocument()
    expect(personRow.queryByText('Rules')).not.toBeInTheDocument()
  })

  it('shows an empty state when the API returns no expenses', async () => {
    stubFetch({ ok: true, body: [] })

    render(<App user={testUser} onLogout={() => {}} />)
    showTab('Transactions')

    expect(await screen.findByText(/no expenses found/i)).toBeInTheDocument()
  })

  it('shows an error state when the request fails', async () => {
    stubFetch({ ok: false, status: 500, body: null })

    render(<App user={testUser} onLogout={() => {}} />)

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

    render(<App user={testUser} onLogout={() => {}} />)
    showTab('Transactions')
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

    render(<App user={testUser} onLogout={() => {}} />)

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

    render(<App user={testUser} onLogout={() => {}} />)
    showTab('Transactions')
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

    render(<App user={testUser} onLogout={() => {}} />)
    showTab('Transactions')
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

    render(<App user={testUser} onLogout={() => {}} />)
    showTab('Transactions')
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

    render(<App user={testUser} onLogout={() => {}} />)
    showTab('Transactions')
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

    render(<App user={testUser} onLogout={() => {}} />)
    showTab('Transactions')
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

    render(<App user={testUser} onLogout={() => {}} />)
    showTab('Transactions')
    expect(await screen.findByText('Corner Store')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /delete/i }))

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(/failed to delete/i)
    expect(screen.getByText('Corner Store')).toBeInTheDocument()
  })

  describe('sorting', () => {
    const older = { id: 1, merchant: 'Corner Store', description: 'Coffee', amount: '3.50', expense_date: '2026-09-01', category: 'Coffee Shops', confidence: null }
    const newer = { id: 2, merchant: 'Gas Station', description: 'Fuel', amount: '42.00', expense_date: '2026-09-05', category: 'Gas & Fuel', confidence: null }
    const middle = { id: 3, merchant: 'Book Shop', description: 'Novel', amount: '9.00', expense_date: '2026-09-03', category: 'Other', confidence: null }

    // Merchant names in the order the table currently shows them.
    function displayedMerchants() {
      return screen
        .getAllByRole('row')
        .slice(1) // skip the header row
        .map((row) => within(row).getAllByRole('cell')[0].textContent)
    }

    it('shows expenses newest first by default', async () => {
      stubFetch({ ok: true, body: [older, newer, middle] })

      render(<App user={testUser} onLogout={() => {}} />)
      showTab('Transactions')
      expect(await screen.findByText('Corner Store')).toBeInTheDocument()

      expect(screen.getByLabelText(/sort by/i)).toHaveValue('date-desc')
      expect(displayedMerchants()).toEqual(['Gas Station', 'Book Shop', 'Corner Store'])
    })

    it('reorders the list when a different sort option is chosen', async () => {
      stubFetch({ ok: true, body: [older, newer, middle] })

      render(<App user={testUser} onLogout={() => {}} />)
      showTab('Transactions')
      expect(await screen.findByText('Corner Store')).toBeInTheDocument()

      fireEvent.change(screen.getByLabelText(/sort by/i), { target: { value: 'amount-desc' } })
      expect(displayedMerchants()).toEqual(['Gas Station', 'Book Shop', 'Corner Store'])

      fireEvent.change(screen.getByLabelText(/sort by/i), { target: { value: 'amount-asc' } })
      expect(displayedMerchants()).toEqual(['Corner Store', 'Book Shop', 'Gas Station'])

      fireEvent.change(screen.getByLabelText(/sort by/i), { target: { value: 'date-asc' } })
      expect(displayedMerchants()).toEqual(['Corner Store', 'Book Shop', 'Gas Station'])
    })

    it('places a newly added expense according to the current sort', async () => {
      const added = { id: 4, merchant: 'Nike Store', description: 'Shoes', amount: '80.00', expense_date: '2026-09-04', category: 'Clothing', confidence: '1' }
      vi.stubGlobal(
        'fetch',
        vi.fn((url: string, init?: RequestInit) =>
          stubPlaidLinkToken(url) ??
          Promise.resolve({
            ok: true,
            status: init?.method === 'POST' ? 201 : 200,
            json: () => Promise.resolve(init?.method === 'POST' ? added : [older, newer, middle]),
          }),
        ),
      )

      render(<App user={testUser} onLogout={() => {}} />)
      showTab('Transactions')
      expect(await screen.findByText('Corner Store')).toBeInTheDocument()

      fireEvent.change(screen.getByLabelText(/merchant/i), { target: { value: 'Nike Store' } })
      fireEvent.change(screen.getByLabelText(/description/i), { target: { value: 'Shoes' } })
      fireEvent.change(screen.getByLabelText(/amount/i), { target: { value: '80.00' } })
      fireEvent.change(screen.getByLabelText(/^date$/i), { target: { value: '2026-09-04' } })
      fireEvent.click(screen.getByRole('button', { name: /add expense/i }))

      expect(await screen.findByRole('cell', { name: 'Nike Store' })).toBeInTheDocument()
      // 2026-09-04 sits between Gas Station (09-05) and Book Shop (09-03), not at the bottom.
      expect(displayedMerchants()).toEqual(['Gas Station', 'Nike Store', 'Book Shop', 'Corner Store'])
    })
  })

  describe('spending summary', () => {
    const coffee = { ...oneExpense, category: 'Coffee Shops', confidence: null }
    const fuel = { id: 2, merchant: 'Gas Station', description: 'Fuel', amount: '42.00', expense_date: '2026-09-02', category: 'Gas & Fuel', confidence: null }

    function summaryRegion() {
      showTab('Insights')
      return screen.getByRole('region', { name: /spending summary/i })
    }

    it('shows the total and a per-category breakdown of the loaded expenses', async () => {
      stubFetch({ ok: true, body: [coffee, fuel] })

      render(<App user={testUser} onLogout={() => {}} />)
      showTab('Transactions')
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

      render(<App user={testUser} onLogout={() => {}} />)
      showTab('Transactions')
      expect(await screen.findByText(/no expenses found/i)).toBeInTheDocument()

      const summary = within(summaryRegion())
      expect(summary.getByText('$0.00')).toBeInTheDocument()
      expect(summary.getByText(/no spending to summarize yet/i)).toBeInTheDocument()
    })

    it('is not shown while expenses are loading or when loading fails', async () => {
      stubFetch({ ok: false, status: 500, body: null })

      render(<App user={testUser} onLogout={() => {}} />)
      showTab('Insights')
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

      render(<App user={testUser} onLogout={() => {}} />)
      showTab('Transactions')
      expect(await screen.findByText('Corner Store')).toBeInTheDocument()
      expect(within(summaryRegion()).getByText('$3.50', { selector: '.summary-card__total-amount' })).toBeInTheDocument()

      showTab('Transactions')

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

      render(<App user={testUser} onLogout={() => {}} />)
      showTab('Transactions')
      expect(await screen.findByText('Corner Store')).toBeInTheDocument()
      expect(within(summaryRegion()).getByText('$45.50')).toBeInTheDocument()

      showTab('Transactions')

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

      render(<App user={testUser} onLogout={() => {}} />)
      showTab('Transactions')
      expect(await screen.findByText('Corner Store')).toBeInTheDocument()
      expect(within(summaryRegion()).getByText('$45.50')).toBeInTheDocument()

      showTab('Transactions')

      fireEvent.click(screen.getByRole('button', { name: /delete expense at gas station/i }))

      const summary = within(summaryRegion())
      expect(await summary.findByText('$3.50', { selector: '.summary-card__total-amount' })).toBeInTheDocument()
      expect(summary.queryByText('Gas & Fuel')).not.toBeInTheDocument()
    })
  })

  describe('spending patterns', () => {
    // 2026-09-01 is a Tuesday, 2026-09-02 a Wednesday.
    const coffee = { ...oneExpense, category: 'Coffee Shops', confidence: null, category_source: null }
    const fuel = { id: 2, merchant: 'Gas Station', description: 'Fuel', amount: '42.00', expense_date: '2026-09-02', category: 'Gas & Fuel', confidence: null, category_source: null }

    function patternsRegion() {
      showTab('Insights')
      return within(screen.getByRole('region', { name: /spending patterns/i }))
    }

    // The amount shown for one day or month, e.g. amountFor('day of week', 'Tue').
    function amountFor(chart: 'day of week' | 'month', label: string) {
      const list = patternsRegion().getByRole('list', { name: new RegExp(`spending by ${chart}`, 'i') })
      const row = within(list)
        .getAllByRole('listitem')
        .find((item) => item.querySelector('.patterns-chart__label')?.textContent === label)
      return row?.querySelector('.patterns-chart__amount')?.textContent
    }

    it('shows spend by day of week and by month for all spending', async () => {
      stubFetch({ ok: true, body: [coffee, fuel] })

      render(<App user={testUser} onLogout={() => {}} />)
      showTab('Transactions')
      expect(await screen.findByText('Corner Store')).toBeInTheDocument()

      expect(patternsRegion().getByLabelText('Category')).toHaveValue('')
      expect(amountFor('day of week', 'Tue')).toBe('$3.50')
      expect(amountFor('day of week', 'Wed')).toBe('$42.00')
      expect(amountFor('day of week', 'Mon')).toBe('$0.00')
      expect(amountFor('month', 'Sep')).toBe('$45.50')
    })

    it('offers only categories that have spending, and shows one category when chosen', async () => {
      stubFetch({ ok: true, body: [coffee, fuel] })

      render(<App user={testUser} onLogout={() => {}} />)
      showTab('Transactions')
      expect(await screen.findByText('Corner Store')).toBeInTheDocument()

      const select = patternsRegion().getByLabelText('Category') as HTMLSelectElement
      expect(Array.from(select.options).map((option) => option.textContent)).toEqual([
        'All categories',
        'Coffee Shops',
        'Gas & Fuel',
      ])

      fireEvent.change(select, { target: { value: 'Gas & Fuel' } })

      expect(amountFor('day of week', 'Tue')).toBe('$0.00')
      expect(amountFor('day of week', 'Wed')).toBe('$42.00')
      expect(amountFor('month', 'Sep')).toBe('$42.00')
    })

    it('updates when an expense is added', async () => {
      vi.stubGlobal(
        'fetch',
        vi.fn((url: string, init?: RequestInit) =>
          stubPlaidLinkToken(url) ??
          Promise.resolve({
            ok: true,
            status: init?.method === 'POST' ? 201 : 200,
            json: () => Promise.resolve(init?.method === 'POST' ? fuel : [coffee]),
          }),
        ),
      )

      render(<App user={testUser} onLogout={() => {}} />)
      showTab('Transactions')
      expect(await screen.findByText('Corner Store')).toBeInTheDocument()
      expect(amountFor('month', 'Sep')).toBe('$3.50')

      showTab('Transactions')

      fireEvent.change(screen.getByLabelText(/merchant/i), { target: { value: 'Gas Station' } })
      fireEvent.change(screen.getByLabelText(/description/i), { target: { value: 'Fuel' } })
      fireEvent.change(screen.getByLabelText(/amount/i), { target: { value: '42.00' } })
      fireEvent.change(screen.getByLabelText(/^date$/i), { target: { value: '2026-09-02' } })
      fireEvent.click(screen.getByRole('button', { name: /add expense/i }))

      expect(await screen.findByText('Gas Station')).toBeInTheDocument()
      expect(amountFor('month', 'Sep')).toBe('$45.50')
      expect(amountFor('day of week', 'Wed')).toBe('$42.00')
    })

    it('goes back to all categories when the chosen category has no expenses left', async () => {
      vi.stubGlobal('confirm', vi.fn(() => true))
      vi.stubGlobal(
        'fetch',
        vi.fn((url: string, init?: RequestInit) =>
          stubPlaidLinkToken(url) ??
          Promise.resolve({
            ok: true,
            status: init?.method === 'DELETE' ? 204 : 200,
            json: () => Promise.resolve(init?.method === 'DELETE' ? undefined : [coffee, fuel]),
          }),
        ),
      )

      render(<App user={testUser} onLogout={() => {}} />)
      showTab('Transactions')
      expect(await screen.findByText('Corner Store')).toBeInTheDocument()
      fireEvent.change(patternsRegion().getByLabelText('Category'), { target: { value: 'Gas & Fuel' } })

      // Since Issue #58, deleting happens on the Transactions tab, and leaving
      // Insights unmounts the card, so it comes back on All categories anyway.
      // This now checks the end result, not SpendingPatterns' own fallback.
      showTab('Transactions')
      fireEvent.click(screen.getByRole('button', { name: /delete expense at gas station/i }))

      await vi.waitFor(() => expect(screen.queryByText('Gas Station')).not.toBeInTheDocument())
      expect(patternsRegion().getByLabelText('Category')).toHaveValue('')
      expect(amountFor('month', 'Sep')).toBe('$3.50')
    })

    it('shows an empty message when there are no expenses', async () => {
      stubFetch({ ok: true, body: [] })

      render(<App user={testUser} onLogout={() => {}} />)
      showTab('Transactions')
      expect(await screen.findByText(/no expenses found/i)).toBeInTheDocument()

      expect(patternsRegion().getByText(/no spending to show patterns for yet/i)).toBeInTheDocument()
      expect(patternsRegion().queryByLabelText('Category')).not.toBeInTheDocument()
    })

    it('is not shown when loading fails', async () => {
      stubFetch({ ok: false, status: 500, body: null })

      render(<App user={testUser} onLogout={() => {}} />)
      showTab('Insights')
      await screen.findByRole('alert')

      expect(screen.queryByRole('region', { name: /spending patterns/i })).not.toBeInTheDocument()
    })
  })

  describe('overview tab', () => {
    const kroger = { id: 3, merchant: 'Kroger', description: 'Groceries', amount: '10.00', expense_date: '2026-08-01', category: 'Groceries', confidence: null, category_source: null }
    const coffee = { ...oneExpense, category: 'Coffee Shops', confidence: null, category_source: 'rules' }
    const fuel = { id: 2, merchant: 'Gas Station', description: 'Fuel', amount: '42.00', expense_date: '2026-09-02', category: 'Gas & Fuel', confidence: null, category_source: null }

    function bigTotal() {
      return screen.getByText(/^\$/, { selector: '.overview-sheet__big' }).textContent
    }

    it('shows the newest month with spending, compared with the month before', async () => {
      stubFetch({ ok: true, body: [kroger, coffee, fuel] })

      render(<App user={testUser} onLogout={() => {}} />)

      expect(await screen.findByText('September 2026')).toBeInTheDocument()
      expect(bigTotal()).toBe('$45.50')
      expect(screen.getByText(/2 expenses\. \$35\.50 more than all of August\./)).toBeInTheDocument()
      expect(screen.getByText('Gas & Fuel', { selector: 'dd' })).toBeInTheDocument()
      expect(screen.getByText('50%', { selector: 'dd' })).toBeInTheDocument()
    })

    it('moves between months and stops at the oldest one', async () => {
      stubFetch({ ok: true, body: [kroger, coffee, fuel] })

      render(<App user={testUser} onLogout={() => {}} />)
      expect(await screen.findByText('September 2026')).toBeInTheDocument()

      fireEvent.click(screen.getByRole('button', { name: /previous month/i }))

      expect(screen.getByText('August 2026')).toBeInTheDocument()
      expect(bigTotal()).toBe('$10.00')
      expect(screen.getByRole('button', { name: /previous month/i })).toBeDisabled()
    })

    it('drills down from a group to a single expense, and back up one level at a time', async () => {
      stubFetch({ ok: true, body: [kroger, coffee, fuel] })

      render(<App user={testUser} onLogout={() => {}} />)
      expect(await screen.findByRole('heading', { name: 'Where it went' })).toBeInTheDocument()

      fireEvent.click(screen.getByRole('button', { name: /^Transportation/ }))
      expect(screen.getByRole('heading', { name: 'Transportation' })).toBeInTheDocument()
      fireEvent.click(screen.getByRole('button', { name: /^Gas & Fuel/ }))
      fireEvent.click(screen.getByRole('button', { name: /^Gas Station/ }))

      expect(screen.getByRole('heading', { name: 'Gas Station' })).toBeInTheDocument()
      expect(screen.getByText('Fuel')).toBeInTheDocument()

      fireEvent.click(screen.getByRole('button', { name: /gas & fuel/i }))
      expect(screen.getByRole('heading', { name: 'Gas & Fuel' })).toBeInTheDocument()
      fireEvent.click(screen.getByRole('button', { name: /transportation/i }))
      fireEvent.click(screen.getByRole('button', { name: /all spending/i }))
      expect(screen.getByRole('heading', { name: 'Where it went' })).toBeInTheDocument()
    })

    it('updates after an expense is added on the Transactions tab', async () => {
      vi.stubGlobal(
        'fetch',
        vi.fn((url: string, init?: RequestInit) =>
          stubPlaidLinkToken(url) ??
          Promise.resolve({
            ok: true,
            status: init?.method === 'POST' ? 201 : 200,
            json: () => Promise.resolve(init?.method === 'POST' ? fuel : [coffee]),
          }),
        ),
      )

      render(<App user={testUser} onLogout={() => {}} />)
      expect(await screen.findByText('September 2026')).toBeInTheDocument()
      expect(bigTotal()).toBe('$3.50')

      showTab('Transactions')
      fireEvent.change(screen.getByLabelText(/merchant/i), { target: { value: 'Gas Station' } })
      fireEvent.change(screen.getByLabelText(/description/i), { target: { value: 'Fuel' } })
      fireEvent.change(screen.getByLabelText(/amount/i), { target: { value: '42.00' } })
      fireEvent.change(screen.getByLabelText(/^date$/i), { target: { value: '2026-09-02' } })
      fireEvent.click(screen.getByRole('button', { name: /add expense/i }))
      expect(await screen.findByRole('cell', { name: 'Gas Station' })).toBeInTheDocument()

      showTab('Overview')
      expect(bigTotal()).toBe('$45.50')
    })

    it('shows an error instead of the overview when loading fails', async () => {
      stubFetch({ ok: false, status: 500, body: null })

      render(<App user={testUser} onLogout={() => {}} />)

      expect(await screen.findByRole('alert')).toHaveTextContent(/failed to fetch expenses: 500/i)
      expect(screen.queryByRole('heading', { name: 'Where it went' })).not.toBeInTheDocument()
    })
  })
})
