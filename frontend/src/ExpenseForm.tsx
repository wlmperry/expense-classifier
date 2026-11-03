import { useState, type FormEvent } from "react"
import { createExpense, updateExpense } from "./api"
import { CATEGORIES } from "./types"
import type { Category, Expense, ExpenseCreate, ExpenseUpdate } from "./types"

const EMPTY_FORM: ExpenseCreate = {
  merchant: "",
  description: "",
  amount: "",
  expense_date: "",
}

function formValuesFor(expense: Expense | null | undefined): ExpenseCreate {
  if (!expense) {
    return EMPTY_FORM
  }
  return {
    merchant: expense.merchant,
    description: expense.description,
    amount: expense.amount,
    expense_date: expense.expense_date,
  }
}

// Only the fields that actually differ from the row being edited are sent,
// matching PATCH /expenses/{id}'s "an omitted field means unchanged" contract.
// Fixed to these four keys (not all of ExpenseCreate): category isn't
// editable here, and formValuesFor() never puts one in `current` anyway.
const EDITABLE_FIELDS = ["merchant", "description", "amount", "expense_date"] as const

function changedFields(initial: ExpenseCreate, current: ExpenseCreate): ExpenseUpdate {
  const changes: ExpenseUpdate = {}
  for (const key of EDITABLE_FIELDS) {
    if (current[key] !== initial[key]) {
      changes[key] = current[key]
    }
  }
  return changes
}

interface ExpenseFormProps {
  // Non-null switches the form into editing that Expense, prefilled.
  // Render with key={expenseToEdit?.id ?? "create"} so switching rows (or
  // back to create mode) remounts the form with fresh initial values.
  expenseToEdit?: Expense | null
  onCreated: (expense: Expense) => void
  onUpdated: (expense: Expense) => void
  onCancelEdit: () => void
}

function ExpenseForm({ expenseToEdit, onCreated, onUpdated, onCancelEdit }: ExpenseFormProps) {
  const isEditing = expenseToEdit != null
  const initialValues = formValuesFor(expenseToEdit)
  const [form, setForm] = useState<ExpenseCreate>(initialValues)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [created, setCreated] = useState<Expense | null>(null)
  // Create mode only -- editing a category isn't in scope here yet. "" means
  // "auto-detect": left off the request entirely so the backend's classifier
  // picks one, same as never touching this dropdown at all.
  const [category, setCategory] = useState<Category | "">("")

  function updateField(field: keyof ExpenseCreate, value: string) {
    setForm((current) => ({ ...current, [field]: value }))
  }

  async function handleUpdateSubmit(expense: Expense) {
    const changes = changedFields(initialValues, form)
    if (Object.keys(changes).length === 0) {
      // Nothing actually changed -- there's nothing to PATCH, and sending an
      // empty body would just get a 422 back for no reason.
      onCancelEdit()
      return
    }
    setSubmitting(true)
    setError(null)
    try {
      const updated = await updateExpense(expense.id, changes)
      onUpdated(updated)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setSubmitting(false)
    }
  }

  async function handleCreateSubmit() {
    setSubmitting(true)
    setError(null)
    setCreated(null)
    try {
      const payload: ExpenseCreate = category ? { ...form, category } : form
      const expense = await createExpense(payload)
      setCreated(expense)
      setForm(EMPTY_FORM)
      setCategory("")
      onCreated(expense)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setSubmitting(false)
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (isEditing && expenseToEdit) {
      void handleUpdateSubmit(expenseToEdit)
    } else {
      void handleCreateSubmit()
    }
  }

  // The `required` attributes are only a convenience; the backend is the
  // authority on what a valid Expense is and reports anything else as a 422.
  return (
    <form onSubmit={handleSubmit} aria-label={isEditing ? "Edit expense" : "Add expense"}>
      <h2>{isEditing ? "Edit expense" : "Add expense"}</h2>
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
      {!isEditing && (
        <label>
          Category
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value as Category | "")}
          >
            <option value="">Auto-detect</option>
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </label>
      )}
      <button type="submit" disabled={submitting}>
        {submitting ? "Saving..." : isEditing ? "Save" : "Add expense"}
      </button>
      {isEditing && (
        <button type="button" onClick={onCancelEdit} disabled={submitting}>
          Cancel
        </button>
      )}
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
