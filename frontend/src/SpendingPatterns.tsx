import { useState } from "react"
import { summarizePatterns, type PatternBucket } from "./patterns"
import { formatCents } from "./summary"
import { CATEGORIES, type Expense } from "./types"

interface SpendingPatternsProps {
  expenses: Expense[]
}

// "" is the dropdown value for all spending combined.
const ALL_CATEGORIES = ""

// When spending tends to happen: total spend by day of week and by month,
// for all spending or one chosen category. Like SpendingSummary, it is
// recomputed from the same expense list the table shows, so it stays in step
// with every add, edit, delete, or bank import.
function SpendingPatterns({ expenses }: SpendingPatternsProps) {
  const [selectedCategory, setSelectedCategory] = useState(ALL_CATEGORIES)

  // Only categories that have spending, in the app's usual category order.
  const categoriesWithSpending = CATEGORIES.filter((category) =>
    expenses.some((expense) => expense.category === category),
  )

  // If the chosen category's last expense was deleted or recategorized, fall
  // back to all spending rather than showing a choice that's no longer listed.
  if (
    selectedCategory !== ALL_CATEGORIES &&
    !(categoriesWithSpending as string[]).includes(selectedCategory)
  ) {
    setSelectedCategory(ALL_CATEGORIES)
  }

  const patterns = summarizePatterns(
    expenses,
    selectedCategory === ALL_CATEGORIES ? null : selectedCategory,
  )

  return (
    <section className="card patterns-card" aria-labelledby="patterns-heading">
      <div className="patterns-card__header">
        <h2 id="patterns-heading">Spending patterns</h2>
        {expenses.length > 0 && (
          <label className="patterns-card__filter">
            Category
            <select
              value={selectedCategory}
              onChange={(event) => setSelectedCategory(event.target.value)}
            >
              <option value={ALL_CATEGORIES}>All categories</option>
              {categoriesWithSpending.map((category) => (
                <option key={category} value={category}>
                  {category}
                </option>
              ))}
            </select>
          </label>
        )}
      </div>

      {expenses.length === 0 ? (
        <p className="summary-card__message">No spending to show patterns for yet.</p>
      ) : (
        <div className="patterns-card__charts">
          <PatternChart title="By day of week" buckets={patterns.byWeekday} />
          <PatternChart title="By month" buckets={patterns.byMonth} />
        </div>
      )}
    </section>
  )
}

interface PatternChartProps {
  title: string
  buckets: PatternBucket[]
}

function PatternChart({ title, buckets }: PatternChartProps) {
  return (
    <div className="patterns-chart">
      <h3>{title}</h3>
      <ul className="patterns-chart__list" aria-label={`Spending ${title.toLowerCase()}`}>
        {buckets.map((bucket) => (
          <li key={bucket.label} className="patterns-chart__row">
            <span className="patterns-chart__label">{bucket.label}</span>
            <span className="summary-breakdown__bar" aria-hidden="true">
              <span
                className="summary-breakdown__bar-fill"
                style={{ width: `${bucket.barPercent}%` }}
              />
            </span>
            <span className="patterns-chart__amount">{formatCents(bucket.totalCents)}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

export default SpendingPatterns
