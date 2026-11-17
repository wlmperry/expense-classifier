import { toCents } from "./summary"
import type { Category, Expense } from "./types"

// The 7 broad groups the drill-down starts from. They are the categories the
// app had before Issue #50 split them up; this mirrors NEW_TO_OLD in
// migration 3c86f19d4985. Typing it as Record<Category, ...> makes the build
// fail if a category is ever added to CATEGORIES without a group here.
export const CATEGORY_GROUPS: Record<Category, string> = {
    "Groceries": "Food & Dining",
    "Restaurants & Bars": "Food & Dining",
    "Coffee Shops": "Food & Dining",
    "Food Delivery": "Food & Dining",
    "Gas & Fuel": "Transportation",
    "Rideshare & Transit": "Transportation",
    "Travel": "Transportation",
    "Rent & Mortgage": "Housing & Utilities",
    "Utilities": "Housing & Utilities",
    "Online Shopping": "Shopping",
    "General Merchandise": "Shopping",
    "Electronics": "Shopping",
    "Clothing": "Shopping",
    "Streaming & Subscriptions": "Entertainment",
    "Movies & Events": "Entertainment",
    "Gaming": "Entertainment",
    "Pharmacy": "Health & Fitness",
    "Gym & Fitness": "Health & Fitness",
    "Medical": "Health & Fitness",
    "Other": "Other",
}

// A category the frontend doesn't know (e.g. the backend added one first)
// still shows up, under Other, rather than disappearing from the totals.
export function groupOf(category: string): string {
    return CATEGORY_GROUPS[category as Category] ?? "Other"
}

// ---------- Months ----------
//
// A month is a "YYYY-MM" string, which is exactly how every expense_date
// ("YYYY-MM-DD") starts. Working with these strings instead of Date objects
// means no time-zone conversion can move an expense into the wrong month.

export function monthOf(isoDate: string): string {
    return isoDate.slice(0, 7)
}

function dayOf(isoDate: string): number {
    return Number(isoDate.slice(8, 10))
}

function splitMonth(month: string): { year: number; monthIndex: number } {
    const [year, monthNumber] = month.split("-").map(Number)
    return { year, monthIndex: monthNumber - 1 }
}

// The month `delta` months away, e.g. shiftMonth("2026-01", -1) is "2025-12".
export function shiftMonth(month: string, delta: number): string {
    const { year, monthIndex } = splitMonth(month)
    const total = year * 12 + monthIndex + delta
    const newYear = Math.floor(total / 12)
    const newMonth = (total % 12) + 1
    return `${newYear}-${String(newMonth).padStart(2, "0")}`
}

export function daysInMonth(month: string): number {
    const { year, monthIndex } = splitMonth(month)
    // Day 0 of the next month is the last day of this one.
    return new Date(Date.UTC(year, monthIndex + 1, 0)).getUTCDate()
}

// "November 2026". Built and formatted in UTC so the label can't shift.
export function formatMonth(month: string): string {
    const { year, monthIndex } = splitMonth(month)
    return new Date(Date.UTC(year, monthIndex, 1)).toLocaleDateString("en-US", {
        month: "long",
        year: "numeric",
        timeZone: "UTC",
    })
}

// The month of the most recent expense, or null if there are none.
// ISO dates sort correctly as plain strings, so no parsing is needed.
export function latestMonth(expenses: Expense[]): string | null {
    let latest: string | null = null
    for (const expense of expenses) {
        if (latest === null || expense.expense_date > latest) {
            latest = expense.expense_date
        }
    }
    return latest === null ? null : monthOf(latest)
}

// Today's date as "YYYY-MM-DD" in the user's own time zone. Only App calls
// this; everything else takes `today` as an argument so tests can pin it.
export function localToday(): string {
    const now = new Date()
    const month = String(now.getMonth() + 1).padStart(2, "0")
    const day = String(now.getDate()).padStart(2, "0")
    return `${now.getFullYear()}-${month}-${day}`
}

// ---------- The month's numbers ----------

export interface MonthOverview {
    month: string
    expenses: Expense[]
    totalCents: number
    // Days of the month that have happened so far: all of them for a past
    // month, up to today for the current month.
    daysSoFar: number
    averagePerDayCents: number
    // The previous month's spend over the same days (1 to daysSoFar), so a
    // half-finished month is compared fairly with half of the month before.
    previousSameDaysCents: number
    topCategory: { category: string; totalCents: number } | null
    largest: Expense | null
    // Share of the month's expenses the rules or the ML model categorized
    // (category_source is set), 0-100. Null when the month has no expenses.
    autoPercent: number | null
}

export function summarizeMonth(allExpenses: Expense[], month: string, today: string): MonthOverview {
    const expenses = allExpenses.filter((e) => monthOf(e.expense_date) === month)
    const totalCents = expenses.reduce((sum, e) => sum + toCents(e.amount), 0)

    const isCurrentMonth = monthOf(today) === month
    const daysSoFar = isCurrentMonth ? dayOf(today) : daysInMonth(month)

    const previousMonth = shiftMonth(month, -1)
    const previousSameDaysCents = allExpenses
        .filter((e) => monthOf(e.expense_date) === previousMonth && dayOf(e.expense_date) <= daysSoFar)
        .reduce((sum, e) => sum + toCents(e.amount), 0)

    const byCategory = new Map<string, number>()
    for (const e of expenses) {
        byCategory.set(e.category, (byCategory.get(e.category) ?? 0) + toCents(e.amount))
    }
    let topCategory: MonthOverview["topCategory"] = null
    for (const [category, cents] of byCategory) {
        // Ties go to the alphabetically first name, so the answer is stable.
        if (
            topCategory === null ||
            cents > topCategory.totalCents ||
            (cents === topCategory.totalCents && category < topCategory.category)
        ) {
            topCategory = { category, totalCents: cents }
        }
    }

    let largest: Expense | null = null
    for (const e of expenses) {
        if (largest === null || toCents(e.amount) > toCents(largest.amount)) {
            largest = e
        }
    }

    const autoCount = expenses.filter((e) => e.category_source !== null).length

    return {
        month,
        expenses,
        totalCents,
        daysSoFar,
        averagePerDayCents: daysSoFar > 0 ? Math.round(totalCents / daysSoFar) : 0,
        previousSameDaysCents,
        topCategory,
        largest,
        autoPercent: expenses.length > 0 ? Math.round((autoCount / expenses.length) * 100) : null,
    }
}

// ---------- "Where it went" drill-down ----------
//
// The path says how deep the user has clicked:
//   []                                  all spending, one row per group
//   ["Food & Dining"]                   one row per category in that group
//   ["Food & Dining", "Coffee Shops"]   one row per merchant
//   ["Food & Dining", "Coffee Shops", "Starbucks"]   that merchant's expenses

export interface DrillRow {
    key: string
    totalCents: number
    count: number
    // Share of the current level's total, 0-100.
    percent: number
}

export interface DrillLevel {
    // Everything inside the current path, and its total.
    expenses: Expense[]
    totalCents: number
    // The rows to click into, biggest first. Null at the last level, where
    // the expenses themselves are listed instead.
    rows: DrillRow[] | null
}

function rowKey(expense: Expense, depth: number): string {
    if (depth === 0) return groupOf(expense.category)
    if (depth === 1) return expense.category
    return expense.merchant
}

export function drillDown(monthExpenses: Expense[], path: string[]): DrillLevel {
    const [group, category, merchant] = path
    const expenses = monthExpenses.filter(
        (e) =>
            (group === undefined || groupOf(e.category) === group) &&
            (category === undefined || e.category === category) &&
            (merchant === undefined || e.merchant === merchant),
    )
    const totalCents = expenses.reduce((sum, e) => sum + toCents(e.amount), 0)

    if (path.length >= 3) {
        return { expenses, totalCents, rows: null }
    }

    const totals = new Map<string, { totalCents: number; count: number }>()
    for (const e of expenses) {
        const key = rowKey(e, path.length)
        const current = totals.get(key) ?? { totalCents: 0, count: 0 }
        totals.set(key, { totalCents: current.totalCents + toCents(e.amount), count: current.count + 1 })
    }
    const rows = [...totals.entries()]
        .map(([key, { totalCents: cents, count }]) => ({
            key,
            totalCents: cents,
            count,
            percent: totalCents === 0 ? 0 : Math.round((cents / totalCents) * 100),
        }))
        .sort((a, b) => b.totalCents - a.totalCents || a.key.localeCompare(b.key))

    return { expenses, totalCents, rows }
}

function categoriesIn(group: string): string[] {
    return Object.entries(CATEGORY_GROUPS)
        .filter(([, g]) => g === group)
        .map(([category]) => category)
}

// The path after clicking `key`. A group with only one category (Other)
// skips straight to its merchants, since a one-row list is a wasted click.
export function drillInto(path: string[], key: string): string[] {
    if (path.length === 0) {
        const categories = categoriesIn(key)
        if (categories.length === 1) {
            return [key, categories[0]]
        }
    }
    return [...path, key]
}

// The path after pressing Back; it skips the same one-row level on the way up.
export function drillUp(path: string[]): string[] {
    const up = path.slice(0, -1)
    if (up.length === 1 && categoriesIn(up[0]).length === 1) {
        return []
    }
    return up
}
