import { describe, expect, it } from 'vitest'
import { sortExpenses } from './sortExpenses'
import type { Expense } from './types'

function expense(id: number, expense_date: string, amount: string): Expense {
  return { id, merchant: `M${id}`, description: '', amount, expense_date, category: 'Other', confidence: null }
}

// 9.00 vs 42.00 catches amounts being compared as text, where "9.00" > "42.00".
const expenses = [
  expense(1, '2026-09-02', '9.00'),
  expense(2, '2026-09-01', '42.00'),
  expense(3, '2026-09-03', '15.50'),
]

function ids(list: Expense[]) {
  return list.map((e) => e.id)
}

describe('sortExpenses', () => {
  it('sorts by date, newest first', () => {
    expect(ids(sortExpenses(expenses, 'date-desc'))).toEqual([3, 1, 2])
  })

  it('sorts by date, oldest first', () => {
    expect(ids(sortExpenses(expenses, 'date-asc'))).toEqual([2, 1, 3])
  })

  it('sorts by amount numerically, highest first', () => {
    expect(ids(sortExpenses(expenses, 'amount-desc'))).toEqual([2, 3, 1])
  })

  it('sorts by amount numerically, lowest first', () => {
    expect(ids(sortExpenses(expenses, 'amount-asc'))).toEqual([1, 3, 2])
  })

  it('breaks ties by putting the most recently added expense (higher id) first', () => {
    const sameDay = [expense(4, '2026-09-01', '5.00'), expense(7, '2026-09-01', '5.00'), expense(5, '2026-09-01', '5.00')]
    expect(ids(sortExpenses(sameDay, 'date-desc'))).toEqual([7, 5, 4])
    expect(ids(sortExpenses(sameDay, 'date-asc'))).toEqual([7, 5, 4])
    expect(ids(sortExpenses(sameDay, 'amount-asc'))).toEqual([7, 5, 4])
  })

  it('does not mutate the input array', () => {
    const input = [...expenses]
    sortExpenses(input, 'amount-desc')
    expect(ids(input)).toEqual([1, 2, 3])
  })
})
