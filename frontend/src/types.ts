// Mirrors app/categorize.py's CATEGORIES -- keep these two lists in sync by hand;
// there's no endpoint exposing the list, since it's small and rarely changes.
export const CATEGORIES = [
    "Food & Dining",
    "Transportation",
    "Housing & Utilities",
    "Shopping",
    "Entertainment",
    "Health & Fitness",
    "Other",
] as const

export type Category = (typeof CATEGORIES)[number]

// uses string for amount to force deliberate parsing and reduce floating point errors
export interface Expense {
    id: number
    merchant: string
    description: string
    amount: string
    expense_date: string
    category: string
    // Null means category wasn't auto-classified (a human supplied or
    // changed it), so there's no classifier guess to show.
    confidence: string | null
}

// The shape sent to POST /expenses: the backend owns `id` and `confidence`
// (the latter is only ever a classifier output, never client-supplied), and
// category is optional (the backend's baseline classifier fills it in when
// omitted).
export type ExpenseCreate = Omit<Expense, "id" | "category" | "confidence"> & {
  category?: Category
}

// The shape sent to PATCH /expenses/{id}: only the fields the editing UI
// actually changed. category isn't editable here yet -- that's a separate,
// not-yet-built dropdown -- so it's left out entirely rather than typed as
// always-optional-but-unused. confidence is never client-supplied, same as
// ExpenseCreate.
export type ExpenseUpdate = Partial<Omit<Expense, "id" | "category" | "confidence">>

export interface PlaidItemStatusResponse {
    item_id: string | null
}

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
