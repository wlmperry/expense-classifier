import { useEffect, useRef, useState } from "react"
import { usePlaidLink, type PlaidLinkOnSuccessMetadata } from "react-plaid-link"
import { createPlaidLinkToken, exchangePublicToken, getPlaidItems, syncPlaidTransactions } from "./api"
import type { Expense, PlaidItemSummary } from "./types"

// Plaid Sandbox populates a newly linked item's transaction history
// asynchronously, so the very first sync can legitimately come back empty.
// One retry after a short wait covers that without the user having to
// click anything twice.
const EMPTY_SYNC_RETRY_DELAY_MS = 2000

interface BankAccountsProps {
  onImported: (expenses: Expense[]) => void
}

function bankName(bank: PlaidItemSummary): string {
  return bank.institution_name ?? "Linked bank"
}

// The linked banks, a Sync now button for each, and Connect a bank
// (Issue #60). A user can link several banks; the backend refuses the same
// bank twice, because Plaid would hand it new transaction ids and every
// transaction would be imported again.
function BankAccounts({ onImported }: BankAccountsProps) {
  const [banks, setBanks] = useState<PlaidItemSummary[]>([])
  const [loadError, setLoadError] = useState<string | null>(null)
  const [linkToken, setLinkToken] = useState<string | null>(null)
  const [fetchingToken, setFetchingToken] = useState(false)
  const [connecting, setConnecting] = useState(false)
  // Which bank is syncing right now, so only its button shows progress.
  const [syncingItemId, setSyncingItemId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  // Set after a fresh link token is fetched, so the effect below opens Link
  // as soon as usePlaidLink reports ready -- which only happens once it's
  // re-initialized with a real (non-empty) token. A ref, not state: it's
  // only ever read/cleared from the effect that reacts to `ready`, so it
  // doesn't need to trigger a render itself.
  const pendingOpenRef = useRef(false)

  useEffect(() => {
    getPlaidItems()
      .then(setBanks)
      .catch((err: Error) => setLoadError(err.message))
  }, [])

  // The link token is fetched lazily, on click, rather than on mount: a
  // backend with no Plaid credentials configured would otherwise show every
  // visitor an error, even one who never intends to connect a bank.
  async function handleConnectClick() {
    if (linkToken !== null) {
      open()
      return
    }
    setError(null)
    setFetchingToken(true)
    try {
      const response = await createPlaidLinkToken()
      pendingOpenRef.current = true
      setLinkToken(response.link_token)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setFetchingToken(false)
    }
  }

  async function syncBank(bank: PlaidItemSummary, retryIfEmpty: boolean) {
    setSyncingItemId(bank.item_id)
    setError(null)
    setMessage(null)
    try {
      let result = await syncPlaidTransactions(bank.item_id)
      if (retryIfEmpty && result.added_count === 0) {
        await new Promise((resolve) => setTimeout(resolve, EMPTY_SYNC_RETRY_DELAY_MS))
        result = await syncPlaidTransactions(bank.item_id)
      }
      onImported(result.added)
      setMessage(
        result.added_count === 0
          ? `${bankName(bank)} is up to date.`
          : `Imported ${result.added_count} transaction${result.added_count === 1 ? "" : "s"} from ${bankName(bank)}.`,
      )
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setSyncingItemId(null)
    }
  }

  async function handleSuccess(publicToken: string | null, metadata?: PlaidLinkOnSuccessMetadata) {
    if (publicToken === null) {
      return
    }
    // Each successful link uses up this token; the next Connect click
    // fetches a fresh one, so every Link session starts clean.
    setLinkToken(null)
    setConnecting(true)
    setError(null)
    setMessage(null)
    try {
      const institution = metadata?.institution ?? null
      const { item_id } = await exchangePublicToken(publicToken, institution)
      const bank = { item_id, institution_name: institution?.name ?? null }
      // The backend returns an existing item_id when the same Item is
      // linked again, so only add it if it isn't listed yet.
      setBanks((current) => (current.some((b) => b.item_id === item_id) ? current : [...current, bank]))
      setConnecting(false)
      await syncBank(bank, true)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setConnecting(false)
    }
  }

  const { open, ready } = usePlaidLink({
    token: linkToken ?? "",
    onSuccess: handleSuccess,
  })

  useEffect(() => {
    if (pendingOpenRef.current && ready) {
      pendingOpenRef.current = false
      open()
    }
  }, [ready, open])

  const busy = connecting || fetchingToken || syncingItemId !== null

  return (
    <section className="card bank-card" aria-labelledby="bank-heading">
      <div className="bank-card__header">
        <h2 id="bank-heading">Bank accounts</h2>
        <button className="button button--primary" type="button" onClick={handleConnectClick} disabled={busy}>
          {connecting ? "Connecting..." : banks.length === 0 ? "Connect a bank" : "Connect another bank"}
        </button>
      </div>

      {error && (
        <p role="alert" className="message message--error">
          {error}
        </p>
      )}
      {message && (
        <p role="status" className="message message--success">
          {message}
        </p>
      )}

      {loadError ? (
        <p className="bank-card__empty">Couldn't load your linked banks ({loadError}).</p>
      ) : banks.length === 0 ? (
        <p className="bank-card__empty">No banks connected yet. Connect one to import its transactions.</p>
      ) : (
        <ul className="bank-list">
          {banks.map((bank) => (
            <li key={bank.item_id} className="bank-list__row">
              <span className="bank-list__name">{bankName(bank)}</span>
              <button
                className="button button--secondary button--small"
                type="button"
                aria-label={`Sync ${bankName(bank)}`}
                onClick={() => syncBank(bank, false)}
                disabled={busy}
              >
                {syncingItemId === bank.item_id ? "Syncing..." : "Sync now"}
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

export default BankAccounts
