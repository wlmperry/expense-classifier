import { useEffect, useState } from "react"
import { deleteExpense, fetchExpenses } from "./api"
import ConnectBank from "./ConnectBank"
import ExpenseForm from "./ExpenseForm"
import type { Expense } from "./types"

function App() {
  const [expenses, setExpenses] = useState<Expense[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const [editingExpense, setEditingExpense] = useState<Expense | null>(null)

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

  // Same append reasoning as handleCreated: Plaid-imported expenses are
  // newly inserted, so they always carry the highest ids so far.
  function handleImported(imported: Expense[]) {
    setExpenses((current) => [...current, ...imported])
  }

  function handleUpdated(updated: Expense) {
    setExpenses((current) => current.map((e) => (e.id === updated.id ? updated : e)))
    setEditingExpense(null)
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
    <>
      <header className="site-header">
        <div className="site-header__inner">
          <span className="brand">
            <span className="brand__mark" aria-hidden="true">
              <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="#ffffff" strokeWidth="2.6" strokeLinecap="round">
                <path d="M5 5l10 10M15 5L5 15" />
              </svg>
            </span>
            <span>
              Xpense<span className="brand__accent">C</span>
            </span>
          </span>
          <ConnectBank onImported={handleImported} />
        </div>
      </header>

      <main className="page">
        <div className="page-title">
          <p className="page-title__eyebrow">Your ledger</p>
          <h1>Expense Classifier</h1>
        </div>

        <div className="page-columns">
          <section className="card expenses-card" aria-labelledby="expenses-heading">
            <div className="expenses-card__header">
              <h2 id="expenses-heading">All expenses</h2>
            </div>
            {loading && <p className="expenses-card__message">Loading expenses...</p>}
            {error && (
              <p role="alert" className="message message--error">
                Error: {error}
              </p>
            )}
            {deleteError && (
              <p role="alert" className="message message--error">
                {deleteError}
              </p>
            )}
            {!loading && !error && expenses.length === 0 && (
              <p className="expenses-card__message">No expenses found.</p>
            )}
            {!loading && !error && expenses.length > 0 && (
              <div className="table-scroll">
                <table className="expenses-table">
                  <thead>
                    <tr>
                      <th>Merchant</th>
                      <th>Description</th>
                      <th className="col-amount">Amount</th>
                      <th>Date</th>
                      <th>Category</th>
                      <th className="col-actions">
                        <span className="visually-hidden">Actions</span>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {expenses.map((expense) => (
                      <tr key={expense.id}>
                        <td className="col-merchant">{expense.merchant}</td>
                        <td>{expense.description}</td>
                        <td className="col-amount">{expense.amount}</td>
                        <td className="col-date">{expense.expense_date}</td>
                        <td>
                          <span className="category-tag">{expense.category}</span>
                        </td>
                        <td className="col-actions">
                          <span className="row-actions">
                            <button
                              className="button button--secondary button--small"
                              aria-label={`Edit expense at ${expense.merchant}`}
                              onClick={() => setEditingExpense(expense)}
                            >
                              Edit
                            </button>
                            <button
                              className="button button--secondary button--small button--danger"
                              aria-label={`Delete expense at ${expense.merchant}`}
                              onClick={() => handleDelete(expense)}
                            >
                              Delete
                            </button>
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <ExpenseForm
            key={editingExpense?.id ?? "create"}
            expenseToEdit={editingExpense}
            onCreated={handleCreated}
            onUpdated={handleUpdated}
            onCancelEdit={() => setEditingExpense(null)}
          />
        </div>
      </main>
    </>
  )
}

export default App
