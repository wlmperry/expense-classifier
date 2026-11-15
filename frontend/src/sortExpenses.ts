import type { Expense } from "./types"

// Each option is a label for the dropdown plus a compare function in the
// shape Array.prototype.sort expects: negative puts `a` first, positive
// puts `b` first. Adding another sort field later means adding one entry.
export const SORT_OPTIONS = {
    "date-desc": {
        label: "Date (newest first)",
        compare: (a: Expense, b: Expense) => b.expense_date.localeCompare(a.expense_date),
    },
    "date-asc": {
        label: "Date (oldest first)",
        compare: (a: Expense, b: Expense) => a.expense_date.localeCompare(b.expense_date),
    },
    "amount-desc": {
        label: "Amount (highest first)",
        compare: (a: Expense, b: Expense) => Number(b.amount) - Number(a.amount),
    },
    "amount-asc": {
        label: "Amount (lowest first)",
        compare: (a: Expense, b: Expense) => Number(a.amount) - Number(b.amount),
    },
} as const

export type SortOption = keyof typeof SORT_OPTIONS

export const DEFAULT_SORT: SortOption = "date-desc"

// Returns a new array and leaves `expenses` untouched, because the input is
// React state and must not be mutated in place. Ties (same date or same
// amount) go to the most recently added expense, i.e. the higher id, so a
// just-added expense is easy to find among others on the same day.
export function sortExpenses(expenses: Expense[], option: SortOption): Expense[] {
    const { compare } = SORT_OPTIONS[option]
    return [...expenses].sort((a, b) => compare(a, b) || b.id - a.id)
}
