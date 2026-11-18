import { API_BASE_URL } from "./config"
import { endSession, getSessionToken } from "./session"
import type {
    AuthResponse,
    Credentials,
    Expense,
    ExpenseCreate,
    ExpenseUpdate,
    PlaidExchangePublicTokenResponse,
    PlaidInstitution,
    PlaidItemSummary,
    PlaidLinkTokenResponse,
    PlaidSyncResponse,
    User,
} from "./types"

// Every backend request goes through this wrapper, so the session token is
// added, and an ended session is noticed, in exactly one place.
async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
    const token = getSessionToken()
    const headers = token ? { ...init.headers, Authorization: `Bearer ${token}` } : init.headers
    const response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers })
    // Only a 401 for a request that carried a token means "your session
    // ended". A failed login is also a 401, but it is sent without a token
    // and must show its error on the login form instead.
    if (response.status === 401 && token) {
        endSession()
    }
    return response
}

export async function register(credentials: Credentials): Promise<AuthResponse> {
    return sendCredentials("/auth/register", credentials)
}

export async function login(credentials: Credentials): Promise<AuthResponse> {
    return sendCredentials("/auth/login", credentials)
}

async function sendCredentials(path: string, credentials: Credentials): Promise<AuthResponse> {
    const response = await apiFetch(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(credentials),
    })
    if (!response.ok) {
        throw new Error(await authErrorMessage(response))
    }
    return response.json()
}

export async function logout(): Promise<void> {
    // The caller clears the saved token either way, so a failure here
    // (e.g. the session had already expired) is not reported.
    await apiFetch("/auth/logout", { method: "POST" })
}

export async function fetchCurrentUser(): Promise<User> {
    const response = await apiFetch("/auth/me")
    if (!response.ok) {
        throw new Error(`Failed to check login: ${response.status}`)
    }
    return response.json()
}

export async function fetchExpenses(): Promise<Expense[]> {
    const response = await apiFetch("/expenses")
    if (!response.ok) {
        throw new Error(`Failed to fetch expenses: ${response.status}`)
    }
    return response.json()
}

export async function createExpense(expense: ExpenseCreate): Promise<Expense> {
    const response = await apiFetch("/expenses", {
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
    const response = await apiFetch(`/expenses/${id}`, {
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
    const response = await apiFetch(`/expenses/${id}`, { method: "DELETE" })
    if (!response.ok) {
        throw new Error(`Failed to delete expense: ${response.status}`)
    }
}

export async function getPlaidItems(): Promise<PlaidItemSummary[]> {
    const response = await apiFetch("/plaid/items")
    if (!response.ok) {
        throw new Error(`Failed to load linked banks: ${response.status}`)
    }
    return response.json()
}

export async function createPlaidLinkToken(): Promise<PlaidLinkTokenResponse> {
    const response = await apiFetch("/plaid/link-token", { method: "POST" })
    if (!response.ok) {
        throw new Error(`Failed to create Plaid link token: ${response.status}`)
    }
    return response.json()
}

// institution comes from Link's metadata; the backend uses its id to refuse
// a bank this user has already linked (a 409, whose message is shown as is).
export async function exchangePublicToken(
    publicToken: string,
    institution: PlaidInstitution | null,
): Promise<PlaidExchangePublicTokenResponse> {
    const response = await apiFetch("/plaid/exchange-public-token", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            public_token: publicToken,
            institution_id: institution?.institution_id ?? null,
            institution_name: institution?.name ?? null,
        }),
    })
    if (response.status === 409) {
        const body: { detail?: string } | null = await response.json().catch(() => null)
        throw new Error(body?.detail ?? "This bank is already connected.")
    }
    if (!response.ok) {
        throw new Error(`Failed to link bank account: ${response.status}`)
    }
    return response.json()
}

export async function syncPlaidTransactions(itemId: string): Promise<PlaidSyncResponse> {
    const response = await apiFetch(`/plaid/sync/${itemId}`, { method: "POST" })
    if (!response.ok) {
        throw new Error(`Failed to sync transactions: ${response.status}`)
    }
    return response.json()
}

// FastAPI reports validation failures as 422 with {"detail": [{"loc": [...], "msg": "..."}]}.
interface ValidationErrorBody {
    detail?: { loc: (string | number)[]; msg: string }[]
}

async function authErrorMessage(response: Response): Promise<string> {
    if (response.status === 401) {
        return "Invalid email or password."
    }
    if (response.status === 409) {
        return "An account with this email already exists."
    }
    if (response.status === 422) {
        const body: ValidationErrorBody | null = await response.json().catch(() => null)
        const fields = new Set(body?.detail?.map((item) => item.loc.at(-1)))
        if (fields.has("email")) {
            return "Enter a valid email address."
        }
        if (fields.has("password")) {
            return "Password must be 8 to 128 characters."
        }
    }
    return `Something went wrong (${response.status}). Please try again.`
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
