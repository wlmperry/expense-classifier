import { toCents } from "./summary"
import type { Expense } from "./types"

export const WEEKDAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"] as const
export const MONTH_LABELS = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
] as const

export interface PatternBucket {
    label: string
    totalCents: number
    // Bar length, 0-100, relative to the biggest bucket in the same chart
    // (not a share of total spend), so the busiest day or month is a full bar.
    barPercent: number
}

export interface SpendingPatterns {
    // Always 7 buckets, Monday first.
    byWeekday: PatternBucket[]
    // Always 12 buckets, January first. Every year is pooled together, so
    // this shows which months spending tends to happen in, not a timeline.
    byMonth: PatternBucket[]
}

// Weekday (0 = Monday ... 6 = Sunday) and month (0 = January) of an
// expense_date like "2026-09-07".
//
// The date is split by hand rather than passed to `new Date("2026-09-07")`:
// that parses as midnight UTC, which is still the previous evening anywhere
// west of UTC, so getDay() would report Sunday for a Monday expense. Building
// the date with Date.UTC and reading it back with getUTCDay keeps the whole
// calculation in UTC, where the calendar date can't shift.
function weekdayAndMonth(expenseDate: string): { weekday: number; month: number } {
    const [year, month, day] = expenseDate.split("-").map(Number)
    const sundayFirst = new Date(Date.UTC(year, month - 1, day)).getUTCDay()
    return { weekday: (sundayFirst + 6) % 7, month: month - 1 }
}

function toBuckets(labels: readonly string[], totals: number[]): PatternBucket[] {
    const biggest = Math.max(...totals)
    return labels.map((label, index) => ({
        label,
        totalCents: totals[index],
        barPercent: biggest === 0 ? 0 : Math.round((totals[index] / biggest) * 100),
    }))
}

// Total spend by day of week and by month of year. category limits it to
// that one category's expenses; null means all spending.
export function summarizePatterns(expenses: Expense[], category: string | null): SpendingPatterns {
    const weekdayTotals = new Array<number>(WEEKDAY_LABELS.length).fill(0)
    const monthTotals = new Array<number>(MONTH_LABELS.length).fill(0)

    for (const expense of expenses) {
        if (category !== null && expense.category !== category) {
            continue
        }
        const cents = toCents(expense.amount)
        const { weekday, month } = weekdayAndMonth(expense.expense_date)
        weekdayTotals[weekday] += cents
        monthTotals[month] += cents
    }

    return {
        byWeekday: toBuckets(WEEKDAY_LABELS, weekdayTotals),
        byMonth: toBuckets(MONTH_LABELS, monthTotals),
    }
}
