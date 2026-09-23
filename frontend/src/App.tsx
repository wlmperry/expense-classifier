import { useEffect, useState } from "react"
import { fetchExpenses } from "./api"
import type { Expense } from "./types"

function App() {
  const [expenses, setExpenses] = useState<Expense[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchExpenses()
      .then(setExpenses)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false))
  }, [])
  return (
    <main>
      <h1>Expense Classifier</h1>
      {loading && <p>Loading expenses...</p>}
      {error && <p role="alert">Error: {error}</p>}
      {!loading && !error && expenses.length === 0 && <p>No expenses found.</p>}
      {!loading && !error && expenses.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>Merchant</th>
              <th>Description</th>
              <th>Amount</th>
              <th>Date</th>
            </tr>
          </thead>
          <tbody>
            {expenses.map((expense) => (
              <tr key={expense.id}>
                <td>{expense.merchant}</td>
                <td>{expense.description}</td>
                <td>{expense.amount}</td>
                <td>{expense.expense_date}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </main>
  )
}

export default App
