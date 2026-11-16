import { describe, expect, it } from 'vitest'
import { summarizePatterns } from './patterns'
import type { Expense } from './types'

function expense(amount: string, expense_date: string, category = 'Other'): Expense {
  return { id: 1, merchant: 'M', description: '', amount, expense_date, category, confidence: null, category_source: null }
}

function totalsByLabel(buckets: { label: string; totalCents: number }[]) {
  return Object.fromEntries(buckets.map((bucket) => [bucket.label, bucket.totalCents]))
}

describe('summarizePatterns', () => {
  it('always returns Monday-to-Sunday and January-to-December buckets, even with no expenses', () => {
    const patterns = summarizePatterns([], null)

    expect(patterns.byWeekday.map((bucket) => bucket.label)).toEqual(['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'])
    expect(patterns.byMonth.map((bucket) => bucket.label)).toEqual([
      'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
    ])
    expect(patterns.byWeekday.every((bucket) => bucket.totalCents === 0 && bucket.barPercent === 0)).toBe(true)
  })

  it('totals spend by day of week', () => {
    // 2026-09-01 is a Tuesday, 2026-09-05 a Saturday, 2026-09-06 a Sunday.
    const patterns = summarizePatterns(
      [expense('3.50', '2026-09-01'), expense('6.50', '2026-09-01'), expense('20.00', '2026-09-05'), expense('1.25', '2026-09-06')],
      null,
    )

    expect(totalsByLabel(patterns.byWeekday)).toEqual({ Mon: 0, Tue: 1000, Wed: 0, Thu: 0, Fri: 0, Sat: 2000, Sun: 125 })
  })

  it('keeps an expense on its own calendar day, whatever the time zone', () => {
    // 2026-09-07 is a Monday. Parsed naively with new Date('2026-09-07'),
    // it becomes the Sunday evening before anywhere west of UTC.
    const patterns = summarizePatterns([expense('5.00', '2026-09-07')], null)

    expect(totalsByLabel(patterns.byWeekday)).toMatchObject({ Mon: 500, Sun: 0 })
    expect(totalsByLabel(patterns.byMonth)).toMatchObject({ Sep: 500, Aug: 0 })
  })

  it('pools the same month from different years', () => {
    const patterns = summarizePatterns([expense('10.00', '2025-09-15'), expense('5.00', '2026-09-15'), expense('2.00', '2026-01-01')], null)

    expect(totalsByLabel(patterns.byMonth)).toMatchObject({ Jan: 200, Sep: 1500 })
  })

  it('only counts the chosen category', () => {
    const patterns = summarizePatterns(
      [expense('4.00', '2026-09-01', 'Coffee Shops'), expense('40.00', '2026-09-01', 'Gas & Fuel'), expense('3.00', '2026-09-07', 'Coffee Shops')],
      'Coffee Shops',
    )

    expect(totalsByLabel(patterns.byWeekday)).toMatchObject({ Mon: 300, Tue: 400 })
    expect(totalsByLabel(patterns.byMonth)).toMatchObject({ Sep: 700 })
  })

  it('sizes bars relative to the biggest bucket in the same chart', () => {
    const patterns = summarizePatterns([expense('10.00', '2026-09-01'), expense('2.50', '2026-09-05')], null)

    const bars = Object.fromEntries(patterns.byWeekday.map((bucket) => [bucket.label, bucket.barPercent]))
    expect(bars).toMatchObject({ Tue: 100, Sat: 25, Mon: 0 })
  })
})
