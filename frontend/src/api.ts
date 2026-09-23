import { API_BASE_URL } from "./config"
import type { Expense, ExpenseCreate } from "./types"

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
        throw new Error(await createErrorMessage(response))
    }
    return response.json()
}

// FastAPI reports validation failures as 422 with {"detail": [{"loc": [...], "msg": "..."}]}.
interface ValidationErrorBody {
    detail?: { loc: (string | number)[]; msg: string }[]
}

async function createErrorMessage(response: Response): Promise<string> {
    if (response.status === 422) {
        const body: ValidationErrorBody | null = await response.json().catch(() => null)
        if (Array.isArray(body?.detail)) {
            const problems = body.detail.map((item) => `${item.loc.at(-1)}: ${item.msg}`)
            return `Could not save expense: ${problems.join("; ")}`
        }
    }
    return `Failed to create expense: ${response.status}`
}
