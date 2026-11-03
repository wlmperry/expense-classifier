import { API_BASE_URL } from "./config"
import type {
    Expense,
    ExpenseCreate,
    ExpenseUpdate,
    PlaidExchangePublicTokenResponse,
    PlaidLinkTokenResponse,
    PlaidSyncResponse,
} from "./types"

export async function fetchExpenses(): Promise<Expense[]> {
    const response = await fetch(`${API_BASE_URL}/expenses`)
    if (!response.ok) {
        throw new Error(`Failed to fetch expenses: ${response.status}`)
    }
    return response.json()
}

export async function createExpense(expense: ExpenseCreate): Promise<Expense> {
    const response = await fetch(`${API_BASE_URL}/expenses`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(expense),
    })
    if (!response.ok) {
        throw new Error(await expenseErrorMessage(response))
    }
    return response.json()
}

export async function updateExpense(id: number, changes: ExpenseUpdate): Promise<Expense> {
    const response = await fetch(`${API_BASE_URL}/expenses/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(changes),
    })
    if (!response.ok) {
        throw new Error(await expenseErrorMessage(response))
    }
    return response.json()
}

export async function deleteExpense(id: number): Promise<void> {
    const response = await fetch(`${API_BASE_URL}/expenses/${id}`, { method: "DELETE" })
    if (!response.ok) {
        throw new Error(`Failed to delete expense: ${response.status}`)
    }
}

export async function createPlaidLinkToken(): Promise<PlaidLinkTokenResponse> {
    const response = await fetch(`${API_BASE_URL}/plaid/link-token`, { method: "POST" })
    if (!response.ok) {
        throw new Error(`Failed to create Plaid link token: ${response.status}`)
    }
    return response.json()
}

export async function exchangePublicToken(
    publicToken: string,
): Promise<PlaidExchangePublicTokenResponse> {
    const response = await fetch(`${API_BASE_URL}/plaid/exchange-public-token`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ public_token: publicToken }),
    })
    if (!response.ok) {
        throw new Error(`Failed to link bank account: ${response.status}`)
    }
    return response.json()
}

export async function syncPlaidTransactions(itemId: string): Promise<PlaidSyncResponse> {
    const response = await fetch(`${API_BASE_URL}/plaid/sync/${itemId}`, { method: "POST" })
    if (!response.ok) {
        throw new Error(`Failed to sync transactions: ${response.status}`)
    }
    return response.json()
}

// FastAPI reports validation failures as 422 with {"detail": [{"loc": [...], "msg": "..."}]}.
interface ValidationErrorBody {
    detail?: { loc: (string | number)[]; msg: string }[]
}

async function expenseErrorMessage(response: Response): Promise<string> {
    if (response.status === 422) {
        const body: ValidationErrorBody | null = await response.json().catch(() => null)
        if (Array.isArray(body?.detail)) {
            const problems = body.detail.map((item) => `${item.loc.at(-1)}: ${item.msg}`)
            return `Could not save expense: ${problems.join("; ")}`
        }
    }
    return `Failed to save expense: ${response.status}`
}
