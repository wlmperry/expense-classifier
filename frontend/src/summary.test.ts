import { describe, expect, it } from 'vitest'
import { formatCents, summarizeSpending } from './summary'
import type { Expense } from './types'

let nextId = 1
function expense(amount: string, category: string): Expense {
  return {
    id: nextId++,
    merchant: 'Merchant',
    description: 'Description',
    amount,
    expense_date: '2026-09-01',
    category,
    confidence: null,
  }
}

describe('summarizeSpending', () => {
  it('returns zero totals and no categories for an empty list', () => {
    expect(summarizeSpending([])).toEqual({ totalCents: 0, count: 0, byCategory: [] })
  })

  it('adds amounts exactly, without floating-point drift', () => {
    // 0.1 + 0.2 is 0.30000000000000004 as floats.
    const summary = summarizeSpending([expense('0.10', 'Other'), expense('0.20', 'Other')])

    expect(summary.totalCents).toBe(30)
    expect(formatCents(summary.totalCents)).toBe('$0.30')
  })

  it('accepts amounts with fewer than two decimal places', () => {
    const summary = summarizeSpending([expense('12', 'Other'), expense('0.5', 'Other')])

    expect(summary.totalCents).toBe(1250)
  })

  it('totals each category and sorts highest spend first', () => {
    const summary = summarizeSpending([
      expense('3.50', 'Restaurants & Bars'),
      expense('42.00', 'Rideshare & Transit'),
      expense('6.50', 'Restaurants & Bars'),
      expense('48.00', 'General Merchandise'),
    ])

    expect(summary.totalCents).toBe(10000)
    expect(summary.count).toBe(4)
    expect(summary.byCategory).toEqual([
      { category: 'General Merchandise', totalCents: 4800, count: 1, percent: 48 },
      { category: 'Rideshare & Transit', totalCents: 4200, count: 1, percent: 42 },
      { category: 'Restaurants & Bars', totalCents: 1000, count: 2, percent: 10 },
    ])
  })

  it('leaves out categories with no expenses', () => {
    const summary = summarizeSpending([expense('5.00', 'Movies & Events')])

    expect(summary.byCategory.map((row) => row.category)).toEqual(['Movies & Events'])
  })

  it('breaks ties in spend by category name so the order is stable', () => {
    const summary = summarizeSpending([expense('10.00', 'Movies & Events'), expense('10.00', 'General Merchandise')])

    expect(summary.byCategory.map((row) => row.category)).toEqual(['General Merchandise', 'Movies & Events'])
  })
})

describe('formatCents', () => {
  it('formats as US dollars with thousands separators', () => {
    expect(formatCents(123456)).toBe('$1,234.56')
    expect(formatCents(0)).toBe('$0.00')
  })
})
