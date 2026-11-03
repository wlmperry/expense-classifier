// uses string for amount to force deliberate parsing and reduce floating point errors
export interface Expense {
    id: number
    merchant: string
    description: string
    amount: string
    expense_date: string
    category: string
}

// The shape sent to POST /expenses: the backend owns `id`, and category is
// optional (the backend's baseline classifier fills it in when omitted).
export type ExpenseCreate = Omit<Expense, "id" | "category">

export interface PlaidLinkTokenResponse {
    link_token: string
    expiration: string
}

export interface PlaidExchangePublicTokenResponse {
    item_id: string
}

export interface PlaidSyncResponse {
    added_count: number
    added: Expense[]
}
