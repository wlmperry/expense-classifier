import { useEffect, useState } from "react"
import { deleteExpense, fetchExpenses } from "./api"
import ExpenseForm from "./ExpenseForm"
import type { Expense } from "./types"

function App() {
  const [expenses, setExpenses] = useState<Expense[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  useEffect(() => {
    fetchExpenses()
      .then(setExpenses)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  // The list is ordered by id and a new Expense always gets the highest id,
  // so appending matches what a fresh GET /expenses would return.
  function handleCreated(expense: Expense) {
    setExpenses((current) => [...current, expense])
  }

  async function handleDelete(expense: Expense) {
    if (!window.confirm(`Delete the expense at ${expense.merchant}?`)) {
      return
    }
    setDeleteError(null)
    try {
      await deleteExpense(expense.id)
      setExpenses((current) => current.filter((e) => e.id !== expense.id))
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : String(err))
    }
  }

  return (
    <main>
      <h1>Expense Classifier</h1>
      <ExpenseForm onCreated={handleCreated} />
      {loading && <p>Loading expenses...</p>}
      {error && <p role="alert">Error: {error}</p>}
      {deleteError && <p role="alert">{deleteError}</p>}
      {!loading && !error && expenses.length === 0 && <p>No expenses found.</p>}
      {!loading && !error && expenses.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>Merchant</th>
              <th>Description</th>
              <th>Amount</th>
              <th>Date</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {expenses.map((expense) => (
              <tr key={expense.id}>
                <td>{expense.merchant}</td>
                <td>{expense.description}</td>
                <td>{expense.amount}</td>
                <td>{expense.expense_date}</td>
                <td>
                  <button
                    aria-label={`Delete expense at ${expense.merchant}`}
                    onClick={() => handleDelete(expense)}
                  >
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </main>
  )
}

export default App
