import { fireEvent, render, screen, within } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"
import BankAccounts from "./BankAccounts"
import { API_BASE_URL } from "./config"
import type { Expense } from "./types"

// react-plaid-link's usePlaidLink normally injects Plaid's real Link script
// and only calls onSuccess after a person finishes the real widget. These
// tests exercise what our own code does once onSuccess fires, so the hook
// is replaced with a stub whose open() calls onSuccess straight away, with
// the metadata Link would pass (which bank the person picked).
const { usePlaidLinkMock } = vi.hoisted(() => ({ usePlaidLinkMock: vi.fn() }))
vi.mock("react-plaid-link", () => ({
  usePlaidLink: usePlaidLinkMock,
}))

type OnSuccess = (token: string | null, metadata: unknown) => void

function stubUsePlaidLink(institution: { institution_id: string; name: string } | null) {
  usePlaidLinkMock.mockImplementation((config: { onSuccess: OnSuccess }) => ({
    open: () => config.onSuccess("public-sandbox-test", { institution }),
    ready: true,
  }))
}

type Reply = { status?: number; body: unknown }

// A fake fetch that answers by "METHOD /path". A list of replies is used in
// order (the last one repeats), for endpoints called more than once.
function stubApi(routes: Record<string, Reply | Reply[]>) {
  const calls: Record<string, number> = {}
  const fetchMock = vi.fn((url: string, init?: RequestInit) => {
    const key = `${init?.method ?? "GET"} ${url.replace(API_BASE_URL, "")}`
    const route = routes[key]
    if (route === undefined) {
      throw new Error(`Unexpected request in test: ${key}`)
    }
    const replies = Array.isArray(route) ? route : [route]
    const reply = replies[Math.min(calls[key] ?? 0, replies.length - 1)]
    calls[key] = (calls[key] ?? 0) + 1
    const status = reply.status ?? 200
    return Promise.resolve({
      ok: status < 400,
      status,
      json: () => Promise.resolve(reply.body),
    })
  })
  vi.stubGlobal("fetch", fetchMock)
  return fetchMock
}

function requestsTo(fetchMock: ReturnType<typeof stubApi>, method: string, path: string) {
  return fetchMock.mock.calls.filter(
    ([url, init]) => url === `${API_BASE_URL}${path}` && ((init as RequestInit | undefined)?.method ?? "GET") === method,
  )
}

const LINK_TOKEN = { body: { link_token: "link-sandbox-abc", expiration: "2026-01-01T00:00:00Z" } }
const BANK_ONE = { item_id: "item-1", institution_name: "Bank One" }

const IMPORTED_EXPENSE: Expense = {
  id: 9,
  merchant: "Uber",
  description: "Uber 072515 SF**POOL**",
  amount: "6.33",
  expense_date: "2026-10-31",
  category: "Rideshare & Transit",
  confidence: "0.9",
  category_source: "rules",
}

describe("BankAccounts", () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    usePlaidLinkMock.mockReset()
  })

  it("lists the linked banks on load, without fetching a link token", async () => {
    stubUsePlaidLink(null)
    const fetchMock = stubApi({
      "GET /plaid/items": { body: [BANK_ONE, { item_id: "item-2", institution_name: "Bank Two" }] },
    })

    render(<BankAccounts onImported={() => {}} />)

    const list = await screen.findByRole("list")
    expect(within(list).getAllByRole("listitem").map((row) => row.textContent)).toEqual([
      "Bank OneSync now",
      "Bank TwoSync now",
    ])
    expect(screen.getByRole("button", { name: "Connect another bank" })).toBeEnabled()
    expect(requestsTo(fetchMock, "POST", "/plaid/link-token")).toHaveLength(0)
  })

  it("invites the user to connect a bank when none is linked", async () => {
    stubUsePlaidLink(null)
    stubApi({ "GET /plaid/items": { body: [] } })

    render(<BankAccounts onImported={() => {}} />)

    expect(await screen.findByText(/no banks connected yet/i)).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Connect a bank" })).toBeInTheDocument()
  })

  it("links a second bank, sending which bank it is, then imports its transactions", async () => {
    stubUsePlaidLink({ institution_id: "ins_2", name: "Bank Two" })
    const fetchMock = stubApi({
      "GET /plaid/items": { body: [BANK_ONE] },
      "POST /plaid/link-token": LINK_TOKEN,
      "POST /plaid/exchange-public-token": { status: 201, body: { item_id: "item-2" } },
      "POST /plaid/sync/item-2": { status: 201, body: { added_count: 1, added: [IMPORTED_EXPENSE] } },
    })
    const onImported = vi.fn()

    render(<BankAccounts onImported={onImported} />)
    fireEvent.click(await screen.findByRole("button", { name: "Connect another bank" }))

    expect(await screen.findByRole("status")).toHaveTextContent("Imported 1 transaction from Bank Two.")
    expect(onImported).toHaveBeenCalledWith([IMPORTED_EXPENSE])
    const [, exchangeInit] = requestsTo(fetchMock, "POST", "/plaid/exchange-public-token")[0]
    expect(JSON.parse((exchangeInit as RequestInit).body as string)).toEqual({
      public_token: "public-sandbox-test",
      institution_id: "ins_2",
      institution_name: "Bank Two",
    })
    expect(screen.getByRole("button", { name: "Sync Bank Two" })).toBeInTheDocument()
  })

  it("explains a bank that is already connected, without syncing anything", async () => {
    stubUsePlaidLink({ institution_id: "ins_1", name: "Bank One" })
    const fetchMock = stubApi({
      "GET /plaid/items": { body: [BANK_ONE] },
      "POST /plaid/link-token": LINK_TOKEN,
      "POST /plaid/exchange-public-token": {
        status: 409,
        body: { detail: "This bank is already connected to your account" },
      },
    })

    render(<BankAccounts onImported={() => {}} />)
    fireEvent.click(await screen.findByRole("button", { name: "Connect another bank" }))

    expect(await screen.findByRole("alert")).toHaveTextContent("This bank is already connected to your account")
    expect(screen.getAllByRole("listitem")).toHaveLength(1)
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes("/plaid/sync/"))).toBe(false)
  })

  it("syncs only the bank whose Sync now button was clicked", async () => {
    stubUsePlaidLink(null)
    const fetchMock = stubApi({
      "GET /plaid/items": { body: [BANK_ONE, { item_id: "item-2", institution_name: "Bank Two" }] },
      "POST /plaid/sync/item-2": { status: 201, body: { added_count: 1, added: [IMPORTED_EXPENSE] } },
    })
    const onImported = vi.fn()

    render(<BankAccounts onImported={onImported} />)
    fireEvent.click(await screen.findByRole("button", { name: "Sync Bank Two" }))

    expect(await screen.findByRole("status")).toHaveTextContent("Imported 1 transaction from Bank Two.")
    expect(onImported).toHaveBeenCalledWith([IMPORTED_EXPENSE])
    expect(requestsTo(fetchMock, "POST", "/plaid/sync/item-1")).toHaveLength(0)
  })

  it("says a bank is up to date when Sync now finds nothing new, without retrying", async () => {
    stubUsePlaidLink(null)
    const fetchMock = stubApi({
      "GET /plaid/items": { body: [BANK_ONE] },
      "POST /plaid/sync/item-1": { status: 201, body: { added_count: 0, added: [] } },
    })

    render(<BankAccounts onImported={() => {}} />)
    fireEvent.click(await screen.findByRole("button", { name: "Sync Bank One" }))

    expect(await screen.findByRole("status")).toHaveTextContent("Bank One is up to date.")
    expect(requestsTo(fetchMock, "POST", "/plaid/sync/item-1")).toHaveLength(1)
  })

  it("retries once when the first sync after linking comes back empty", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    stubUsePlaidLink({ institution_id: "ins_1", name: "Bank One" })
    stubApi({
      "GET /plaid/items": { body: [] },
      "POST /plaid/link-token": LINK_TOKEN,
      "POST /plaid/exchange-public-token": { status: 201, body: { item_id: "item-1" } },
      "POST /plaid/sync/item-1": [
        { status: 201, body: { added_count: 0, added: [] } },
        { status: 201, body: { added_count: 1, added: [IMPORTED_EXPENSE] } },
      ],
    })
    const onImported = vi.fn()

    render(<BankAccounts onImported={onImported} />)
    fireEvent.click(await screen.findByRole("button", { name: "Connect a bank" }))

    // Let the token fetch, Link, exchange and first (empty) sync settle
    // before advancing the clock past the full retry delay.
    await screen.findByText("Syncing...")
    await vi.advanceTimersByTimeAsync(2000)

    expect(await screen.findByRole("status")).toHaveTextContent("Imported 1 transaction from Bank One.")
    expect(onImported).toHaveBeenCalledWith([IMPORTED_EXPENSE])
    vi.useRealTimers()
  })

  it("fetches a fresh link token for each new bank", async () => {
    stubUsePlaidLink({ institution_id: "ins_1", name: "Bank One" })
    const fetchMock = stubApi({
      "GET /plaid/items": { body: [] },
      "POST /plaid/link-token": LINK_TOKEN,
      "POST /plaid/exchange-public-token": { status: 201, body: { item_id: "item-1" } },
      "POST /plaid/sync/item-1": { status: 201, body: { added_count: 1, added: [IMPORTED_EXPENSE] } },
    })

    render(<BankAccounts onImported={() => {}} />)
    fireEvent.click(await screen.findByRole("button", { name: "Connect a bank" }))
    await screen.findByRole("status")
    stubUsePlaidLink({ institution_id: "ins_2", name: "Bank Two" })
    fireEvent.click(screen.getByRole("button", { name: "Connect another bank" }))

    await vi.waitFor(() => expect(requestsTo(fetchMock, "POST", "/plaid/link-token")).toHaveLength(2))
  })

  it("shows an error only after a click, when fetching the link token fails", async () => {
    stubUsePlaidLink(null)
    stubApi({
      "GET /plaid/items": { body: [] },
      "POST /plaid/link-token": { status: 500, body: null },
    })

    render(<BankAccounts onImported={() => {}} />)
    const button = await screen.findByRole("button", { name: "Connect a bank" })
    expect(screen.queryByRole("alert")).not.toBeInTheDocument()

    fireEvent.click(button)

    expect(await screen.findByRole("alert")).toHaveTextContent(/failed to create plaid link token: 500/i)
  })

  it("says so when the linked banks can't be loaded", async () => {
    stubUsePlaidLink(null)
    stubApi({ "GET /plaid/items": { status: 500, body: null } })

    render(<BankAccounts onImported={() => {}} />)

    expect(await screen.findByText(/couldn't load your linked banks/i)).toBeInTheDocument()
  })
})
