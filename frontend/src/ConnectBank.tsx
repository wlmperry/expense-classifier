import { useEffect, useState } from "react"
import { usePlaidLink } from "react-plaid-link"
import { createPlaidLinkToken, exchangePublicToken, syncPlaidTransactions } from "./api"
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
  const [status, setStatus] = useState<"idle" | "connecting" | "syncing" | "error">("idle")
  const [error, setError] = useState<string | null>(null)
  const [importedCount, setImportedCount] = useState<number | null>(null)

  useEffect(() => {
    createPlaidLinkToken()
      .then((response) => setLinkToken(response.link_token))
      .catch((err: Error) => setError(err.message))
  }, [])

  async function handleSuccess(publicToken: string | null) {
    if (publicToken === null) {
      return
    }
    setStatus("connecting")
    setError(null)
    setImportedCount(null)
    try {
      const { item_id } = await exchangePublicToken(publicToken)

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

  const busy = status === "connecting" || status === "syncing"

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
      <button className="button button--primary" onClick={() => open()} disabled={!ready || busy}>
        {status === "connecting" && "Connecting..."}
        {status === "syncing" && "Importing transactions..."}
        {status === "idle" && "Connect bank"}
        {status === "error" && "Connect bank"}
      </button>
    </div>
  )
}

export default ConnectBank
