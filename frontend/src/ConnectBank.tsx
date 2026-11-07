import { useEffect, useRef, useState } from "react"
import { usePlaidLink } from "react-plaid-link"
import {
  createPlaidLinkToken,
  exchangePublicToken,
  getPlaidItemStatus,
  syncPlaidTransactions,
} from "./api"
import type { Expense } from "./types"

// Plaid Sandbox populates a newly linked item's transaction history
// asynchronously, so the very first sync can legitimately come back empty.
// One retry after a short wait covers that without the user having to
// click anything twice.
const EMPTY_SYNC_RETRY_DELAY_MS = 2000

interface ConnectBankProps {
  onImported: (expenses: Expense[]) => void
}

function ConnectBank({ onImported }: ConnectBankProps) {
  const [linkToken, setLinkToken] = useState<string | null>(null)
  const [fetchingToken, setFetchingToken] = useState(false)
  // Set after a fresh link token is fetched, so the effect below opens Link
  // as soon as usePlaidLink reports ready -- which only happens once it's
  // re-initialized with a real (non-empty) token. A ref, not state: it's
  // only ever read/cleared from the effect that reacts to `ready`, so it
  // doesn't need to trigger a render itself.
  const pendingOpenRef = useRef(false)
  const [status, setStatus] = useState<"idle" | "connecting" | "syncing" | "error">("idle")
  const [error, setError] = useState<string | null>(null)
  const [importedCount, setImportedCount] = useState<number | null>(null)
  // Only one Item is ever expected for this project's single demo user (see
  // create_plaid_link_token's hardcoded client_user_id). Once one exists --
  // from an earlier session or from this one -- Connect bank is disabled:
  // a second Link session mints a brand-new item_id with its own fresh
  // transaction_ids, so neither exchange_public_token's same-item_id check
  // nor the sync endpoint's dedup-by-transaction_id can catch a second
  // linking of the same bank the way they catch a repeat of the same Item.
  const [linkedItemId, setLinkedItemId] = useState<string | null>(null)

  useEffect(() => {
    getPlaidItemStatus()
      .then((result) => setLinkedItemId(result.item_id))
      .catch(() => {
        // Leave linkedItemId as null: Connect bank stays clickable, same as
        // before this status check existed.
      })
  }, [])

  // The link token is fetched lazily, on click, rather than on mount: a
  // backend with no Plaid credentials configured would otherwise show every
  // visitor a permanent error banner, even one who never intends to connect
  // a bank.
  async function handleConnectClick() {
    if (linkedItemId !== null) {
      return
    }
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
      setStatus("error")
    } finally {
      setFetchingToken(false)
    }
  }

  async function handleSuccess(publicToken: string | null) {
    if (publicToken === null) {
      return
    }
    setStatus("connecting")
    setError(null)
    setImportedCount(null)
    try {
      const { item_id } = await exchangePublicToken(publicToken)
      setLinkedItemId(item_id)

      setStatus("syncing")
      let result = await syncPlaidTransactions(item_id)
      if (result.added_count === 0) {
        await new Promise((resolve) => setTimeout(resolve, EMPTY_SYNC_RETRY_DELAY_MS))
        result = await syncPlaidTransactions(item_id)
      }

      onImported(result.added)
      setImportedCount(result.added_count)
      setStatus("idle")
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
      setStatus("error")
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

  const busy = status === "connecting" || status === "syncing"
  const alreadyLinked = linkedItemId !== null

  return (
    <div className="connect-bank">
      {error && (
        <p role="alert" className="message message--error">
          {error}
        </p>
      )}
      {importedCount !== null && (
        <p role="status" className="message message--success">
          Imported {importedCount} transaction{importedCount === 1 ? "" : "s"}.
        </p>
      )}
      <button
        className="button button--primary"
        onClick={handleConnectClick}
        disabled={busy || fetchingToken || alreadyLinked}
      >
        {status === "connecting" && "Connecting..."}
        {status === "syncing" && "Importing transactions..."}
        {status === "idle" && (alreadyLinked ? "Bank connected" : "Connect bank")}
        {status === "error" && "Connect bank"}
      </button>
    </div>
  )
}

export default ConnectBank
