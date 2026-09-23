import { fireEvent, render, screen } from '@testing-library/react'
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
    render(<ExpenseForm onCreated={() => {}} />)

    expect(screen.getByLabelText(/merchant/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/description/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/amount/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/date/i)).toBeInTheDocument()
    expect(screen.queryByLabelText(/^id$/i)).not.toBeInTheDocument()
  })

  it('POSTs the expense with amount as a JSON string and no id', async () => {
    const fetchMock = stubFetch({ ok: true, body: SAVED_EXPENSE })
    render(<ExpenseForm onCreated={() => {}} />)

    fillAndSubmit()
    await screen.findByRole('status')

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit]
    expect(url).toBe(`${API_BASE_URL}/expenses`)
    expect(init.method).toBe('POST')
    expect(init.headers).toEqual({ 'Content-Type': 'application/json' })
    // Compare the raw JSON text so a number (3.5) could not sneak past as equal to "3.50".
    expect(init.body).toBe(
      '{"merchant":"Corner Store","description":"Coffee","amount":"3.50","expense_date":"2026-09-01"}',
    )
  })

  it('shows progress while saving, then acknowledges the saved expense', async () => {
    stubFetch({ ok: true, body: SAVED_EXPENSE })
    const onCreated = vi.fn()
    render(<ExpenseForm onCreated={onCreated} />)

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
    render(<ExpenseForm onCreated={onCreated} />)

    fillAndSubmit()

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(/amount: value error, amount must have no more than two decimal places/i)
    expect(onCreated).not.toHaveBeenCalled()
    expect(screen.getByLabelText(/merchant/i)).toHaveValue('Corner Store')
  })

  it('shows an error when the request fails without a validation body', async () => {
    stubFetch({ ok: false, status: 500, body: null })
    render(<ExpenseForm onCreated={() => {}} />)

    fillAndSubmit()

    expect(await screen.findByRole('alert')).toHaveTextContent(/failed to create expense: 500/i)
  })

  it('shows an error when the network request itself fails', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new TypeError('Failed to fetch'))))
    render(<ExpenseForm onCreated={() => {}} />)

    fillAndSubmit()

    expect(await screen.findByRole('alert')).toHaveTextContent(/failed to fetch/i)
  })
})
