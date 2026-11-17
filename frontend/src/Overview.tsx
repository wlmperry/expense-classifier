import { useState } from "react"
import {
    drillDown,
    drillInto,
    drillUp,
    formatMonth,
    latestMonth,
    monthOf,
    shiftMonth,
    summarizeMonth,
} from "./monthOverview"
import { formatCents, toCents } from "./summary"
import type { Expense } from "./types"

interface OverviewProps {
    expenses: Expense[]
    // Today's date as "YYYY-MM-DD"; passed in so tests can pin it.
    today: string
}

// "Nov 3" for an expense_date like "2026-11-03", formatted in UTC so the
// day can't shift (see patterns.ts for why).
function shortDate(isoDate: string): string {
    const [year, month, day] = isoDate.split("-").map(Number)
    return new Date(Date.UTC(year, month - 1, day)).toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        timeZone: "UTC",
    })
}

// Up to two capital letters for the round icon beside each row.
function initials(name: string): string {
    return name
        .replace(/[^A-Za-z0-9 ]/g, "")
        .split(/\s+/)
        .filter(Boolean)
        .slice(0, 2)
        .map((word) => word[0].toUpperCase())
        .join("")
}

function plural(count: number, word: string): string {
    return `${count} ${word}${count === 1 ? "" : "s"}`
}

// The landing tab: one month at a glance, then "Where it went" to click
// down from broad groups to individual expenses.
function Overview({ expenses, today }: OverviewProps) {
    // null until the user picks a month; until then, show the newest month
    // with spending (or this month if there's nothing at all yet).
    const [chosenMonth, setChosenMonth] = useState<string | null>(null)
    const [path, setPath] = useState<string[]>([])

    const newestMonth = latestMonth(expenses) ?? monthOf(today)
    const month = chosenMonth ?? newestMonth
    const oldestMonth = expenses.reduce(
        (oldest, e) => (monthOf(e.expense_date) < oldest ? monthOf(e.expense_date) : oldest),
        newestMonth,
    )
    const lastPickableMonth = monthOf(today) > newestMonth ? monthOf(today) : newestMonth

    const overview = summarizeMonth(expenses, month, today)
    const level = drillDown(overview.expenses, path)
    const isCurrentMonth = month === monthOf(today)
    const previousMonthName = formatMonth(shiftMonth(month, -1)).split(" ")[0]

    function changeMonth(delta: number) {
        setChosenMonth(shiftMonth(month, delta))
        setPath([])
    }

    let comparison: string
    if (overview.previousSameDaysCents === 0) {
        comparison = `No spending in ${previousMonthName} to compare with.`
    } else {
        const difference = overview.totalCents - overview.previousSameDaysCents
        const period = isCurrentMonth
            ? `${previousMonthName.slice(0, 3)} 1–${overview.daysSoFar}`
            : `all of ${previousMonthName}`
        comparison =
            difference === 0
                ? `The same as ${period}.`
                : `${formatCents(Math.abs(difference))} ${difference < 0 ? "less" : "more"} than ${period}.`
    }

    const levelTitle = path.length === 0 ? "All spending" : path[path.length - 1]
    // Back goes where drillUp says, so its label names that level.
    const pathAfterBack = drillUp(path)
    const backTitle = pathAfterBack.length === 0 ? "All spending" : pathAfterBack[pathAfterBack.length - 1]

    return (
        <div className="overview">
            <section className="overview-sheet" aria-labelledby="overview-total">
                <div className="month-picker" role="group" aria-label="Month">
                    <button
                        type="button"
                        aria-label="Previous month"
                        disabled={month <= oldestMonth}
                        onClick={() => changeMonth(-1)}
                    >
                        ‹
                    </button>
                    <span aria-live="polite">{formatMonth(month)}</span>
                    <button
                        type="button"
                        aria-label="Next month"
                        disabled={month >= lastPickableMonth}
                        onClick={() => changeMonth(1)}
                    >
                        ›
                    </button>
                </div>

                <p className="overview-sheet__kicker">
                    {isCurrentMonth ? `So far in ${formatMonth(month)}` : `Spent in ${formatMonth(month)}`}
                </p>
                <p className="overview-sheet__big" id="overview-total">
                    {formatCents(overview.totalCents)}
                </p>
                <p className="overview-sheet__status">
                    {overview.expenses.length === 0
                        ? "No expenses this month."
                        : `${plural(overview.expenses.length, "expense")}. ${comparison}`}
                </p>

                {overview.expenses.length > 0 && (
                    <dl className="kpi-grid">
                        <div className="kpi">
                            <dt>Average per day</dt>
                            <dd>{formatCents(overview.averagePerDayCents)}</dd>
                            <dd className="kpi__sub">over {plural(overview.daysSoFar, "day")}</dd>
                        </div>
                        <div className="kpi">
                            <dt>Top category</dt>
                            <dd className="kpi__text">{overview.topCategory?.category}</dd>
                            <dd className="kpi__sub">{formatCents(overview.topCategory?.totalCents ?? 0)}</dd>
                        </div>
                        <div className="kpi">
                            <dt>Largest expense</dt>
                            <dd>{formatCents(toCents(overview.largest?.amount ?? "0"))}</dd>
                            <dd className="kpi__sub">
                                {overview.largest &&
                                    `${overview.largest.merchant}, ${shortDate(overview.largest.expense_date)}`}
                            </dd>
                        </div>
                        <div className="kpi">
                            <dt>Sorted automatically</dt>
                            <dd>{overview.autoPercent}%</dd>
                            <dd className="kpi__sub">by the rules or the ML model</dd>
                        </div>
                    </dl>
                )}
            </section>

            <section className="card drill-card" aria-labelledby="drill-heading">
                <div className="drill-card__header">
                    {path.length > 0 && (
                        <button type="button" className="drill-back" onClick={() => setPath(drillUp(path))}>
                            ‹ {backTitle}
                        </button>
                    )}
                    <h2 id="drill-heading">{path.length === 0 ? "Where it went" : levelTitle}</h2>
                    <p className="drill-card__total">
                        {formatCents(level.totalCents)}
                        {path.length > 0 && overview.totalCents > 0 && (
                            <span> · {Math.round((level.totalCents / overview.totalCents) * 100)}% of the month</span>
                        )}
                    </p>
                </div>

                {level.expenses.length === 0 ? (
                    <p className="drill-card__empty">Nothing to show for {formatMonth(month)}.</p>
                ) : level.rows ? (
                    <ul className="drill-list">
                        {level.rows.map((row) => (
                            <li key={row.key}>
                                <button
                                    type="button"
                                    className="drill-row"
                                    onClick={() => setPath(drillInto(path, row.key))}
                                >
                                    <span className="drill-row__icon" aria-hidden="true">
                                        {initials(row.key)}
                                    </span>
                                    <span className="drill-row__text">
                                        <b>{row.key}</b>
                                        <small>
                                            {plural(row.count, "expense")} · {row.percent}%
                                        </small>
                                    </span>
                                    <span className="drill-row__amount">{formatCents(row.totalCents)}</span>
                                    <span className="drill-row__chevron" aria-hidden="true">
                                        ›
                                    </span>
                                </button>
                            </li>
                        ))}
                    </ul>
                ) : (
                    <ul className="drill-list">
                        {[...level.expenses]
                            .sort((a, b) => b.expense_date.localeCompare(a.expense_date) || b.id - a.id)
                            .map((expense) => (
                                <li key={expense.id} className="drill-expense">
                                    <span className="drill-expense__date">{shortDate(expense.expense_date)}</span>
                                    <span className="drill-row__text">
                                        <b>{expense.description || expense.merchant}</b>
                                        <small>{expense.category}</small>
                                    </span>
                                    <span className="drill-row__amount">{formatCents(toCents(expense.amount))}</span>
                                </li>
                            ))}
                    </ul>
                )}
            </section>
        </div>
    )
}

export default Overview
