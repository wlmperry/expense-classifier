import { API_BASE_URL } from "./config"
import type { Expense } from "./types"

export async function fetchExpenses(): Promise<Expense[]> {
    const response = await fetch(`${API_BASE_URL}/expenses`)
    if (!response.ok) {
        throw new Error(`Failed to fetch expenses: ${response.status}`)
    }
    return response.json()
}
