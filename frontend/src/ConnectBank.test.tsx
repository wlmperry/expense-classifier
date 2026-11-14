import { render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"
import ConnectBank from "./ConnectBank"
import { API_BASE_URL } from "./config"
import type { Expense } from "./types"

// react-plaid-link's usePlaidLink normally injects Plaid's real Link script
// and only calls onSuccess after a person finishes the real widget. These
// tests aren't exercising Plaid's widget -- they're exercising what our own
// code does once onSuccess fires -- so the hook is replaced with a stub that
// hands back a fake "open" plus whatever onSuccess callback we were given,
// letting a test invoke it directly as if a person had just finished Link.
const { usePlaidLinkMock } = vi.hoisted(() => ({ usePlaidLinkMock: vi.fn() }))
vi.mock("react-plaid-link", () => ({
  usePlaidLink: usePlaidLinkMock,
}))

function stubUsePlaidLink() {
  usePlaidLinkMock.mockImplementation((config: { onSuccess: (token: string | null) => void }) => ({
    open: () => config.onSuccess("public-sandbox-test"),
    ready: true,
  }))
}

function stubFetchSequence(responses: { ok: boolean; status?: number; body: unknown }[]) {
  let call = 0
  const fetchMock = vi.fn(() => {
    const response = responses[Math.min(call, responses.length - 1)]
    call += 1
    return Promise.resolve({
      ok: response.ok,
      status: response.status ?? 200,
      json: () => Promise.resolve(response.body),
    })
  })
  vi.stubGlobal("fetch", fetchMock)
  return fetchMock
}

const IMPORTED_EXPENSE: Expense = {
  id: 9,
  merchant: "Uber",
  description: "Uber 072515 SF**POOL**",
  amount: "6.33",
  expense_date: "2026-10-31",
  category: "Rideshare & Transit",
  confidence: "0.9",
}

describe("ConnectBank", () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    usePlaidLinkMock.mockReset()
  })

  it("fetches linked status on mount, and does not fetch a link token until clicked", async () => {
    stubUsePlaidLink()
    const fetchMock = stubFetchSequence([
      { ok: true, body: { item_id: null } },
      { ok: true, body: { link_token: "link-sandbox-abc", expiration: "2026-01-01T00:00:00Z" } },
    ])

    render(<ConnectBank onImported={() => {}} />)

    await screen.findByRole("button", { name: /connect bank/i })
    await vi.waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(`${API_BASE_URL}/plaid/item`, {
        headers: { Authorization: "Bearer " },
      }),
    )
    expect(fetchMock).not.toHaveBeenCalledWith(
      `${API_BASE_URL}/plaid/link-token`,
      expect.anything(),
    )
  })

  it("fetches a link token when Connect bank is clicked", async () => {
    stubUsePlaidLink()
    const fetchMock = stubFetchSequence([
      { ok: true, body: { item_id: null } },
      { ok: true, body: { link_token: "link-sandbox-abc", expiration: "2026-01-01T00:00:00Z" } },
    ])

    render(<ConnectBank onImported={() => {}} />)
    screen.getByRole("button", { name: /connect bank/i }).click()

    await vi.waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(`${API_BASE_URL}/plaid/link-token`, {
        method: "POST",
        headers: { Authorization: "Bearer " },
      }),
    )
  })

  it("disables Connect bank, without fetching a link token, when a bank is already linked", async () => {
    stubUsePlaidLink()
    const fetchMock = stubFetchSequence([{ ok: true, body: { item_id: "item-existing" } }])

    render(<ConnectBank onImported={() => {}} />)

    const button = await screen.findByRole("button", { name: /bank connected/i })
    expect(button).toBeDisabled()

    button.click()
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it("disables Connect bank immediately after a successful link, so it can't be clicked again", async () => {
    stubUsePlaidLink()
    stubFetchSequence([
      { ok: true, body: { item_id: null } },
      { ok: true, body: { link_token: "link-sandbox-abc", expiration: "2026-01-01T00:00:00Z" } },
      { ok: true, body: { item_id: "item-abc" } },
      { ok: true, body: { added_count: 1, added: [IMPORTED_EXPENSE] } },
    ])

    render(<ConnectBank onImported={() => {}} />)
    screen.getByRole("button", { name: /connect bank/i }).click()

    expect(await screen.findByRole("button", { name: /bank connected/i })).toBeDisabled()
  })

  it("shows an error, without a permanent banner before any click, when fetching the link token fails", async () => {
    stubUsePlaidLink()
    stubFetchSequence([
      { ok: true, body: { item_id: null } },
      { ok: false, status: 500, body: null },
    ])

    render(<ConnectBank onImported={() => {}} />)
    expect(screen.queryByRole("alert")).not.toBeInTheDocument()

    screen.getByRole("button", { name: /connect bank/i }).click()

    expect(await screen.findByRole("alert")).toHaveTextContent(
      /failed to create plaid link token: 500/i,
    )
  })

  it("exchanges the public token, syncs, and reports imported expenses", async () => {
    stubUsePlaidLink()
    stubFetchSequence([
      { ok: true, body: { item_id: null } },
      { ok: true, body: { link_token: "link-sandbox-abc", expiration: "2026-01-01T00:00:00Z" } },
      { ok: true, body: { item_id: "item-abc" } },
      { ok: true, body: { added_count: 1, added: [IMPORTED_EXPENSE] } },
    ])
    const onImported = vi.fn()

    render(<ConnectBank onImported={onImported} />)
    screen.getByRole("button", { name: /connect bank/i }).click()

    expect(await screen.findByRole("status")).toHaveTextContent(/imported 1 transaction/i)
    expect(onImported).toHaveBeenCalledWith([IMPORTED_EXPENSE])
  })

  it("retries once when the first sync comes back empty", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    stubUsePlaidLink()
    stubFetchSequence([
      { ok: true, body: { item_id: null } },
      { ok: true, body: { link_token: "link-sandbox-abc", expiration: "2026-01-01T00:00:00Z" } },
      { ok: true, body: { item_id: "item-abc" } },
      { ok: true, body: { added_count: 0, added: [] } },
      { ok: true, body: { added_count: 1, added: [IMPORTED_EXPENSE] } },
    ])
    const onImported = vi.fn()

    render(<ConnectBank onImported={onImported} />)
    screen.getByRole("button", { name: /connect bank/i }).click()

    // Let the click-triggered token fetch, Link open, exchange, and first
    // (empty) sync all settle before advancing the clock, so the full
    // 2000ms retry delay -- not whatever's left of it -- is what gets
    // advanced past.
    await screen.findByText(/importing transactions/i)
    await vi.advanceTimersByTimeAsync(2000)

    expect(await screen.findByRole("status")).toHaveTextContent(/imported 1 transaction/i)
    expect(onImported).toHaveBeenCalledWith([IMPORTED_EXPENSE])
    vi.useRealTimers()
  })

  it("shows an error when exchanging the public token fails", async () => {
    stubUsePlaidLink()
    stubFetchSequence([
      { ok: true, body: { item_id: null } },
      { ok: true, body: { link_token: "link-sandbox-abc", expiration: "2026-01-01T00:00:00Z" } },
      { ok: false, status: 500, body: null },
    ])

    render(<ConnectBank onImported={() => {}} />)
    screen.getByRole("button", { name: /connect bank/i }).click()

    expect(await screen.findByRole("alert")).toHaveTextContent(/failed to link bank account: 500/i)
  })
})
