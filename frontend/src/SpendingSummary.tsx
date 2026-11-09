import { formatCents, summarizeSpending } from "./summary"
import type { Expense } from "./types"

interface SpendingSummaryProps {
  expenses: Expense[]
}

// Recomputed from the same expense list the table shows, so it stays in step
// with every add, edit, delete, or bank import without its own fetching.
function SpendingSummary({ expenses }: SpendingSummaryProps) {
  const summary = summarizeSpending(expenses)

  return (
    <section className="card summary-card" aria-labelledby="summary-heading">
      <div className="summary-card__header">
        <h2 id="summary-heading">Spending summary</h2>
        <p className="summary-card__total">
          <span className="summary-card__total-label">Total spend</span>
          <span className="summary-card__total-amount">{formatCents(summary.totalCents)}</span>
          <span className="summary-card__total-count">
            across {summary.count} expense{summary.count === 1 ? "" : "s"}
          </span>
        </p>
      </div>

      {summary.byCategory.length === 0 ? (
        <p className="summary-card__message">No spending to summarize yet.</p>
      ) : (
        <ul className="summary-breakdown" aria-label="Spending by category">
          {summary.byCategory.map((row) => (
            <li key={row.category} className="summary-breakdown__row">
              <span className="summary-breakdown__category">{row.category}</span>
              <span className="summary-breakdown__bar" aria-hidden="true">
                <span
                  className="summary-breakdown__bar-fill"
                  style={{ width: `${row.percent}%` }}
                />
              </span>
              <span className="summary-breakdown__amount">{formatCents(row.totalCents)}</span>
              <span className="summary-breakdown__percent">{row.percent}%</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

export default SpendingSummary
