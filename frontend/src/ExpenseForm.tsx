import { useState, type FormEvent } from "react"
import { createExpense } from "./api"
import type { Expense, ExpenseCreate } from "./types"

const EMPTY_FORM: ExpenseCreate = {
  merchant: "",
  description: "",
  amount: "",
  expense_date: "",
}

interface ExpenseFormProps {
  onCreated: (expense: Expense) => void
}

function ExpenseForm({ onCreated }: ExpenseFormProps) {
  const [form, setForm] = useState<ExpenseCreate>(EMPTY_FORM)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [created, setCreated] = useState<Expense | null>(null)

  function updateField(field: keyof ExpenseCreate, value: string) {
    setForm((current) => ({ ...current, [field]: value }))
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSubmitting(true)
    setError(null)
    setCreated(null)
    try {
      const expense = await createExpense(form)
      setCreated(expense)
      setForm(EMPTY_FORM)
      onCreated(expense)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setSubmitting(false)
    }
  }

  // The `required` attributes are only a convenience; the backend is the
  // authority on what a valid Expense is and reports anything else as a 422.
  return (
    <form onSubmit={handleSubmit} aria-label="Add expense">
      <h2>Add expense</h2>
      <label>
        Merchant
        <input
          value={form.merchant}
          onChange={(e) => updateField("merchant", e.target.value)}
          required
        />
      </label>
      <label>
        Description
        <input
          value={form.description}
          onChange={(e) => updateField("description", e.target.value)}
          required
        />
      </label>
      <label>
        Amount
        {/* type="text", not "number": the amount stays an exact string, never a JS float. */}
        <input
          inputMode="decimal"
          placeholder="12.34"
          value={form.amount}
          onChange={(e) => updateField("amount", e.target.value)}
          required
        />
      </label>
      <label>
        Date
        {/* A date input's value is always "YYYY-MM-DD", the format the API expects. */}
        <input
          type="date"
          value={form.expense_date}
          onChange={(e) => updateField("expense_date", e.target.value)}
          required
        />
      </label>
      <button type="submit" disabled={submitting}>
        {submitting ? "Saving..." : "Add expense"}
      </button>
      {error && <p role="alert">Error: {error}</p>}
      {created && (
        <p role="status">
          Saved {created.merchant} ({created.amount}) on {created.expense_date}.
        </p>
      )}
    </form>
  )
}

export default ExpenseForm
