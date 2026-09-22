// uses string for amount to force deliberate parsing and reduce floating point errors
export interface Expense{
    id: number
    merchant: string
    description: string
    amount: string
    expense_date: string
}