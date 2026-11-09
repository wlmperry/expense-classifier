import type { Expense } from "./types"

export interface CategoryTotal {
    category: string
    totalCents: number
    count: number
    // Share of the overall total, 0-100, rounded to a whole percent for
    // display. Rounded shares are not guaranteed to add up to exactly 100.
    percent: number
}

export interface SpendingSummary {
    totalCents: number
    count: number
    // Only categories with at least one expense, highest spend first.
    byCategory: CategoryTotal[]
}

// Amounts arrive as decimal strings with at most two decimal places (the
// backend enforces this), so rounding to whole cents is exact. Summing
// integer cents instead of floats avoids totals like 42.300000000000004.
function toCents(amount: string): number {
    return Math.round(Number(amount) * 100)
}

export function summarizeSpending(expenses: Expense[]): SpendingSummary {
    const totals = new Map<string, { totalCents: number; count: number }>()
    let totalCents = 0

    for (const expense of expenses) {
        const cents = toCents(expense.amount)
        totalCents += cents
        const current = totals.get(expense.category) ?? { totalCents: 0, count: 0 }
        totals.set(expense.category, {
            totalCents: current.totalCents + cents,
            count: current.count + 1,
        })
    }

    const byCategory = [...totals.entries()]
        .map(([category, { totalCents: categoryCents, count }]) => ({
            category,
            totalCents: categoryCents,
            count,
            percent: totalCents === 0 ? 0 : Math.round((categoryCents / totalCents) * 100),
        }))
        // Ties broken by name so the order is stable between renders.
        .sort((a, b) => b.totalCents - a.totalCents || a.category.localeCompare(b.category))

    return { totalCents, count: expenses.length, byCategory }
}

const currencyFormat = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" })

export function formatCents(cents: number): string {
    return currencyFormat.format(cents / 100)
}
