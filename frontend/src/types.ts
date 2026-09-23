// uses string for amount to force deliberate parsing and reduce floating point errors
export interface Expense {
    id: number
    merchant: string
    description: string
    amount: string
    expense_date: string
}

// The shape sent to POST /expenses: the backend owns `id`, so the client never sends one.
export type ExpenseCreate = Omit<Expense, "id">
