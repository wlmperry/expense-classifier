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
  category: "Transportation",
}

describe("ConnectBank", () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    usePlaidLinkMock.mockReset()
  })

  it("fetches a link token on mount", async () => {
    stubUsePlaidLink()
    const fetchMock = stubFetchSequence([
      { ok: true, body: { link_token: "link-sandbox-abc", expiration: "2026-01-01T00:00:00Z" } },
    ])

    render(<ConnectBank onImported={() => {}} />)

    await screen.findByRole("button", { name: /connect bank/i })
    expect(fetchMock).toHaveBeenCalledWith(`${API_BASE_URL}/plaid/link-token`, {
      method: "POST",
      headers: { Authorization: "Bearer " },
    })
  })

  it("exchanges the public token, syncs, and reports imported expenses", async () => {
    stubUsePlaidLink()
    stubFetchSequence([
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
      { ok: true, body: { link_token: "link-sandbox-abc", expiration: "2026-01-01T00:00:00Z" } },
      { ok: true, body: { item_id: "item-abc" } },
      { ok: true, body: { added_count: 0, added: [] } },
      { ok: true, body: { added_count: 1, added: [IMPORTED_EXPENSE] } },
    ])
    const onImported = vi.fn()

    render(<ConnectBank onImported={onImported} />)
    screen.getByRole("button", { name: /connect bank/i }).click()

    await vi.advanceTimersByTimeAsync(2000)

    expect(await screen.findByRole("status")).toHaveTextContent(/imported 1 transaction/i)
    expect(onImported).toHaveBeenCalledWith([IMPORTED_EXPENSE])
    vi.useRealTimers()
  })

  it("shows an error when exchanging the public token fails", async () => {
    stubUsePlaidLink()
    stubFetchSequence([
      { ok: true, body: { link_token: "link-sandbox-abc", expiration: "2026-01-01T00:00:00Z" } },
      { ok: false, status: 500, body: null },
    ])

    render(<ConnectBank onImported={() => {}} />)
    screen.getByRole("button", { name: /connect bank/i }).click()

    expect(await screen.findByRole("alert")).toHaveTextContent(/failed to link bank account: 500/i)
  })
})
