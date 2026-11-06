import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import ExpenseForm from './ExpenseForm'
import { API_BASE_URL } from './config'

const SAVED_EXPENSE = {
  id: 7,
  merchant: 'Corner Store',
  description: 'Coffee',
  amount: '3.50',
  expense_date: '2026-09-01',
}

const EXISTING_EXPENSE = {
  id: 9,
  merchant: 'Gas Station',
  description: 'Fuel',
  amount: '42.00',
  expense_date: '2026-09-02',
  category: 'Transportation',
}

const noop = {
  onCreated: () => {},
  onUpdated: () => {},
  onCancelEdit: () => {},
}

function stubFetch(response: { ok: boolean; status?: number; body: unknown }) {
  const fetchMock = vi.fn(() =>
    Promise.resolve({
      ok: response.ok,
      status: response.status ?? 201,
      json: () => Promise.resolve(response.body),
    }),
  )
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function fillAndSubmit() {
  fireEvent.change(screen.getByLabelText(/merchant/i), { target: { value: 'Corner Store' } })
  fireEvent.change(screen.getByLabelText(/description/i), { target: { value: 'Coffee' } })
  fireEvent.change(screen.getByLabelText(/amount/i), { target: { value: '3.50' } })
  fireEvent.change(screen.getByLabelText(/date/i), { target: { value: '2026-09-01' } })
  fireEvent.click(screen.getByRole('button', { name: /add expense/i }))
}

describe('ExpenseForm', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('renders an input for each creation field and no id field', () => {
    render(<ExpenseForm {...noop} />)

    expect(screen.getByLabelText(/merchant/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/description/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/amount/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/date/i)).toBeInTheDocument()
    expect(screen.queryByLabelText(/^id$/i)).not.toBeInTheDocument()
  })

  it('POSTs the expense with amount as a JSON string and no id', async () => {
    const fetchMock = stubFetch({ ok: true, body: SAVED_EXPENSE })
    render(<ExpenseForm {...noop} />)

    fillAndSubmit()
    await screen.findByRole('status')

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit]
    expect(url).toBe(`${API_BASE_URL}/expenses`)
    expect(init.method).toBe('POST')
    expect(init.headers).toEqual({
      'Content-Type': 'application/json',
      Authorization: 'Bearer ',
    })
    // Compare the raw JSON text so a number (3.5) could not sneak past as equal to "3.50".
    expect(init.body).toBe(
      '{"merchant":"Corner Store","description":"Coffee","amount":"3.50","expense_date":"2026-09-01"}',
    )
  })

  it('shows progress while saving, then acknowledges the saved expense', async () => {
    stubFetch({ ok: true, body: SAVED_EXPENSE })
    const onCreated = vi.fn()
    render(<ExpenseForm {...noop} onCreated={onCreated} />)

    fillAndSubmit()

    expect(screen.getByRole('button', { name: /saving/i })).toBeDisabled()
    expect(await screen.findByRole('status')).toHaveTextContent(/saved corner store \(3\.50\)/i)
    expect(onCreated).toHaveBeenCalledWith(SAVED_EXPENSE)
    expect(screen.getByRole('button', { name: /add expense/i })).toBeEnabled()
    expect(screen.getByLabelText(/merchant/i)).toHaveValue('')
  })

  it('shows the backend validation message when the API rejects the expense', async () => {
    stubFetch({
      ok: false,
      status: 422,
      body: {
        detail: [
          {
            loc: ['body', 'amount'],
            msg: 'Value error, amount must have no more than two decimal places',
          },
        ],
      },
    })
    const onCreated = vi.fn()
    render(<ExpenseForm {...noop} onCreated={onCreated} />)

    fillAndSubmit()

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(/amount: value error, amount must have no more than two decimal places/i)
    expect(onCreated).not.toHaveBeenCalled()
    expect(screen.getByLabelText(/merchant/i)).toHaveValue('Corner Store')
  })

  it('shows an error when the request fails without a validation body', async () => {
    stubFetch({ ok: false, status: 500, body: null })
    render(<ExpenseForm {...noop} />)

    fillAndSubmit()

    expect(await screen.findByRole('alert')).toHaveTextContent(/failed to save expense: 500/i)
  })

  it('shows an error when the network request itself fails', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new TypeError('Failed to fetch'))))
    render(<ExpenseForm {...noop} />)

    fillAndSubmit()

    expect(await screen.findByRole('alert')).toHaveTextContent(/failed to fetch/i)
  })

  it('offers exactly the seven allowed categories plus auto-detect, defaulting to auto-detect', () => {
    render(<ExpenseForm {...noop} />)

    const select = screen.getByLabelText(/category/i) as HTMLSelectElement
    const options = Array.from(select.options).map((o) => o.value)

    expect(options).toEqual([
      '',
      'Food & Dining',
      'Transportation',
      'Housing & Utilities',
      'Shopping',
      'Entertainment',
      'Health & Fitness',
      'Other',
    ])
    expect(select).toHaveValue('')
  })

  it('omits category from the request when left on auto-detect', async () => {
    const fetchMock = stubFetch({ ok: true, body: SAVED_EXPENSE })
    render(<ExpenseForm {...noop} />)

    fillAndSubmit()
    await screen.findByRole('status')

    const [, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit]
    const body = JSON.parse(init.body as string)
    expect(body).not.toHaveProperty('category')
  })

  it('includes the chosen category in the request when one is selected', async () => {
    const fetchMock = stubFetch({ ok: true, body: SAVED_EXPENSE })
    render(<ExpenseForm {...noop} />)

    fireEvent.change(screen.getByLabelText(/category/i), { target: { value: 'Entertainment' } })
    fillAndSubmit()
    await screen.findByRole('status')

    const [, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit]
    const body = JSON.parse(init.body as string)
    expect(body.category).toBe('Entertainment')
  })

  it('resets the category dropdown back to auto-detect after a successful save', async () => {
    stubFetch({ ok: true, body: SAVED_EXPENSE })
    render(<ExpenseForm {...noop} />)

    fireEvent.change(screen.getByLabelText(/category/i), { target: { value: 'Shopping' } })
    fillAndSubmit()
    await screen.findByRole('status')

    expect(screen.getByLabelText(/category/i)).toHaveValue('')
  })
})

describe('ExpenseForm editing', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('opens prefilled with the expense being edited', () => {
    render(<ExpenseForm {...noop} expenseToEdit={EXISTING_EXPENSE} />)

    expect(screen.getByRole('heading', { name: /edit expense/i })).toBeInTheDocument()
    expect(screen.getByLabelText(/merchant/i)).toHaveValue('Gas Station')
    expect(screen.getByLabelText(/description/i)).toHaveValue('Fuel')
    expect(screen.getByLabelText(/amount/i)).toHaveValue('42.00')
    expect(screen.getByLabelText(/date/i)).toHaveValue('2026-09-02')
    expect(screen.queryByLabelText(/category/i)).not.toBeInTheDocument()
  })

  it('PATCHes only the fields that were actually changed', async () => {
    const fetchMock = stubFetch({ ok: true, body: { ...EXISTING_EXPENSE, amount: '50.00' } })
    render(<ExpenseForm {...noop} expenseToEdit={EXISTING_EXPENSE} />)

    fireEvent.change(screen.getByLabelText(/amount/i), { target: { value: '50.00' } })
    fireEvent.click(screen.getByRole('button', { name: /^save$/i }))
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))

    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit]
    expect(url).toBe(`${API_BASE_URL}/expenses/9`)
    expect(init.method).toBe('PATCH')
    expect(init.body).toBe('{"amount":"50.00"}')
  })

  it('calls onUpdated with the saved expense on success', async () => {
    const updated = { ...EXISTING_EXPENSE, amount: '50.00' }
    stubFetch({ ok: true, body: updated })
    const onUpdated = vi.fn()
    render(<ExpenseForm {...noop} expenseToEdit={EXISTING_EXPENSE} onUpdated={onUpdated} />)

    fireEvent.change(screen.getByLabelText(/amount/i), { target: { value: '50.00' } })
    fireEvent.click(screen.getByRole('button', { name: /^save$/i }))

    await waitFor(() => expect(onUpdated).toHaveBeenCalledWith(updated))
  })

  it('cancels without saving when nothing was actually changed', () => {
    const fetchMock = stubFetch({ ok: true, body: EXISTING_EXPENSE })
    const onCancelEdit = vi.fn()
    render(<ExpenseForm {...noop} expenseToEdit={EXISTING_EXPENSE} onCancelEdit={onCancelEdit} />)

    fireEvent.click(screen.getByRole('button', { name: /^save$/i }))

    expect(fetchMock).not.toHaveBeenCalled()
    expect(onCancelEdit).toHaveBeenCalledTimes(1)
  })

  it('discards changes and exits editing when Cancel is clicked', () => {
    const onCancelEdit = vi.fn()
    render(<ExpenseForm {...noop} expenseToEdit={EXISTING_EXPENSE} onCancelEdit={onCancelEdit} />)

    fireEvent.change(screen.getByLabelText(/amount/i), { target: { value: '999.99' } })
    fireEvent.click(screen.getByRole('button', { name: /cancel/i }))

    expect(onCancelEdit).toHaveBeenCalledTimes(1)
  })

  it('shows the backend validation message when an update is rejected', async () => {
    stubFetch({
      ok: false,
      status: 422,
      body: {
        detail: [{ loc: ['body', 'amount'], msg: 'Value error, amount must be greater than 0' }],
      },
    })
    const onUpdated = vi.fn()
    render(<ExpenseForm {...noop} expenseToEdit={EXISTING_EXPENSE} onUpdated={onUpdated} />)

    fireEvent.change(screen.getByLabelText(/amount/i), { target: { value: '0.00' } })
    fireEvent.click(screen.getByRole('button', { name: /^save$/i }))

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(/amount: value error, amount must be greater than 0/i)
    expect(onUpdated).not.toHaveBeenCalled()
  })
})
