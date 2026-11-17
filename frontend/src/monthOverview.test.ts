import { describe, expect, it } from 'vitest'
import {
  daysInMonth,
  drillDown,
  drillInto,
  drillUp,
  formatMonth,
  groupOf,
  latestMonth,
  shiftMonth,
  summarizeMonth,
} from './monthOverview'
import type { Expense } from './types'

let nextId = 1
function expense(
  amount: string,
  expense_date: string,
  category = 'Other',
  merchant = 'M',
  category_source: Expense['category_source'] = null,
): Expense {
  return { id: nextId++, merchant, description: '', amount, expense_date, category, confidence: null, category_source }
}

describe('months', () => {
  it('steps across a year boundary in both directions', () => {
    expect(shiftMonth('2026-01', -1)).toBe('2025-12')
    expect(shiftMonth('2025-12', 1)).toBe('2026-01')
    expect(shiftMonth('2026-11', 0)).toBe('2026-11')
  })

  it('knows month lengths, including leap years', () => {
    expect(daysInMonth('2026-11')).toBe(30)
    expect(daysInMonth('2026-02')).toBe(28)
    expect(daysInMonth('2028-02')).toBe(29)
  })

  it('formats a month without shifting it', () => {
    expect(formatMonth('2026-11')).toBe('November 2026')
    expect(formatMonth('2026-01')).toBe('January 2026')
  })

  it('finds the month of the most recent expense', () => {
    expect(latestMonth([])).toBeNull()
    expect(latestMonth([expense('1.00', '2026-09-30'), expense('1.00', '2026-11-01'), expense('1.00', '2026-10-15')])).toBe('2026-11')
  })
})

describe('summarizeMonth', () => {
  it('totals only the chosen month, in cents', () => {
    const all = [expense('0.10', '2026-11-01'), expense('0.20', '2026-11-30'), expense('99.00', '2026-10-31')]

    const overview = summarizeMonth(all, '2026-11', '2026-12-05')

    expect(overview.totalCents).toBe(30)
    expect(overview.expenses).toHaveLength(2)
  })

  it('compares a month in progress with the same days of the month before', () => {
    // Today is Nov 16: compare Nov 1-16 with Oct 1-16, not all of October.
    const all = [
      expense('50.00', '2026-11-03'),
      expense('20.00', '2026-10-10'),
      expense('500.00', '2026-10-20'),
    ]

    const overview = summarizeMonth(all, '2026-11', '2026-11-16')

    expect(overview.daysSoFar).toBe(16)
    expect(overview.previousSameDaysCents).toBe(2000)
    expect(overview.averagePerDayCents).toBe(Math.round(5000 / 16))
  })

  it('uses the whole month for a month that is over', () => {
    const overview = summarizeMonth([expense('31.00', '2026-10-31'), expense('9.00', '2026-09-30')], '2026-10', '2026-11-16')

    expect(overview.daysSoFar).toBe(31)
    expect(overview.averagePerDayCents).toBe(100)
    expect(overview.previousSameDaysCents).toBe(900)
  })

  it('finds the top category, the largest expense, and the automatic share', () => {
    const big = expense('40.00', '2026-11-02', 'Groceries', 'Kroger', 'rules')
    const all = [
      big,
      expense('5.00', '2026-11-03', 'Coffee Shops', 'Starbucks', 'model'),
      expense('5.00', '2026-11-04', 'Coffee Shops', 'Starbucks', null),
      expense('30.00', '2026-11-05', 'Groceries', 'Publix', null),
    ]

    const overview = summarizeMonth(all, '2026-11', '2026-11-30')

    expect(overview.topCategory).toEqual({ category: 'Groceries', totalCents: 7000 })
    expect(overview.largest).toBe(big)
    expect(overview.autoPercent).toBe(50)
  })

  it('handles a month with no expenses', () => {
    const overview = summarizeMonth([], '2026-11', '2026-11-16')

    expect(overview.totalCents).toBe(0)
    expect(overview.topCategory).toBeNull()
    expect(overview.largest).toBeNull()
    expect(overview.autoPercent).toBeNull()
  })
})

describe('drill-down', () => {
  const month = [
    expense('10.00', '2026-11-01', 'Coffee Shops', 'Starbucks'),
    expense('5.00', '2026-11-02', 'Coffee Shops', 'Starbucks'),
    expense('40.00', '2026-11-03', 'Groceries', 'Kroger'),
    expense('25.00', '2026-11-04', 'Gas & Fuel', 'Shell'),
    expense('20.00', '2026-11-05', 'Other', 'Venmo'),
  ]

  it('starts with one row per broad group, biggest first', () => {
    const level = drillDown(month, [])

    expect(level.totalCents).toBe(10000)
    expect(level.rows?.map((r) => [r.key, r.totalCents, r.percent])).toEqual([
      ['Food & Dining', 5500, 55],
      ['Transportation', 2500, 25],
      ['Other', 2000, 20],
    ])
  })

  it('goes group, then category, then merchant, then expenses', () => {
    expect(drillDown(month, ['Food & Dining']).rows?.map((r) => r.key)).toEqual(['Groceries', 'Coffee Shops'])
    expect(drillDown(month, ['Food & Dining', 'Coffee Shops']).rows).toEqual([
      { key: 'Starbucks', totalCents: 1500, count: 2, percent: 100 },
    ])

    const last = drillDown(month, ['Food & Dining', 'Coffee Shops', 'Starbucks'])
    expect(last.rows).toBeNull()
    expect(last.expenses).toHaveLength(2)
    expect(last.totalCents).toBe(1500)
  })

  it('skips the one-category level for Other in both directions', () => {
    const into = drillInto([], 'Other')
    expect(into).toEqual(['Other', 'Other'])
    expect(drillDown(month, into).rows?.map((r) => r.key)).toEqual(['Venmo'])

    expect(drillUp(['Other', 'Other', 'Venmo'])).toEqual(['Other', 'Other'])
    expect(drillUp(['Other', 'Other'])).toEqual([])
  })

  it('goes back one level at a time for normal groups', () => {
    const path = drillInto(drillInto(drillInto([], 'Food & Dining'), 'Coffee Shops'), 'Starbucks')
    expect(path).toEqual(['Food & Dining', 'Coffee Shops', 'Starbucks'])
    expect(drillUp(path)).toEqual(['Food & Dining', 'Coffee Shops'])
    expect(drillUp(drillUp(path))).toEqual(['Food & Dining'])
    expect(drillUp(drillUp(drillUp(path)))).toEqual([])
  })

  it('puts a category it does not know under Other', () => {
    expect(groupOf('Pet Supplies')).toBe('Other')
  })
})
