import { useState } from 'react'
import { Info, Wifi, WifiOff, X, RefreshCw } from 'lucide-react'
import { useGuidance } from '../../context/GuidanceContext.jsx'

export default function DemoModeBanner() {
  const [dismissed, setDismissed] = useState(false)
  const { connStatus, openConnModal, refreshConnection } = useGuidance()

  if (dismissed) return null

  const isLive = connStatus.backend.status === 'connected' && (connStatus.nebius.status === 'verified' || connStatus.nebius.status === 'configured')

  return (
    <div
      className={`flex items-center justify-between gap-3 rounded-lg border px-3.5 py-2 text-xs transition ${
        isLive
          ? 'border-ok/30 bg-ok/5 text-tx'
          : 'border-mem/30 bg-mem/5 text-tx'
      }`}
      data-tour="mode-banner"
    >
      <div className="flex items-center gap-2.5 min-w-0">
        {isLive ? (
          <Wifi size={14} className="text-ok flex-none" />
        ) : (
          <WifiOff size={14} className="text-mem flex-none" />
        )}
        <div className="min-w-0 truncate">
          <span className="font-semibold text-tx">
            {isLive ? 'Live Mode Active: ' : 'Demo Mode Active: '}
          </span>
          <span className="text-mu">
            {isLive
              ? 'Connected to FastAPI backend and Nebius Token Factory.'
              : 'Using client-side simulator stand-in. All belief updates & recovery run in-browser.'}
          </span>
        </div>
      </div>

      <div className="flex items-center gap-2 flex-none">
        <button
          onClick={openConnModal}
          className="rounded px-2 py-1 text-[11px] font-medium text-obs hover:underline flex items-center gap-1"
        >
          <Info size={12} />
          Details
        </button>

        {!isLive && (
          <button
            onClick={() => refreshConnection(true)}
            disabled={connStatus.isChecking}
            className="flex items-center gap-1 rounded bg-s2 px-2 py-1 text-[11px] font-medium text-tx hover:bg-s2/80 disabled:opacity-50"
            title="Check for live backend"
          >
            <RefreshCw size={11} className={connStatus.isChecking ? 'animate-spin' : ''} />
            Check Live
          </button>
        )}

        <button
          onClick={() => setDismissed(true)}
          className="rounded p-1 text-mu hover:text-tx"
          aria-label="Dismiss banner"
        >
          <X size={13} />
        </button>
      </div>
    </div>
  )
}
