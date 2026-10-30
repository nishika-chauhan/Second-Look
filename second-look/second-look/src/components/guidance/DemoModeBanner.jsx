import { useState, useEffect } from 'react'
import { Info, Wifi, WifiOff, X, RefreshCw, CheckCircle2 } from 'lucide-react'
import { useGuidance } from '../../context/GuidanceContext.jsx'

export default function DemoModeBanner() {
  const [dismissed, setDismissed] = useState(() => {
    try {
      return sessionStorage.getItem('second_look_demo_dismissed') === 'true'
    } catch {
      return false
    }
  })
  const [detailsOpen, setDetailsOpen] = useState(false)
  const { connStatus, refreshConnection } = useGuidance()

  const isLive = connStatus.backend.status === 'connected' &&
    (connStatus.nebius.status === 'verified' || connStatus.nebius.status === 'configured')

  const handleDismiss = (e) => {
    e?.stopPropagation()
    setDismissed(true)
    try {
      sessionStorage.setItem('second_look_demo_dismissed', 'true')
    } catch {}
  }

  if (dismissed) {
    // When dismissed, provide a tiny inline button to reopen details without taking vertical space
    return (
      <div className="flex justify-end -mb-2">
        <button
          onClick={() => setDetailsOpen(true)}
          className="text-[11px] text-mu hover:text-obs transition flex items-center gap-1 px-1"
          title="View Operating Mode & Connectivity"
        >
          <span className={`inline-block h-1.5 w-1.5 rounded-full ${isLive ? 'bg-ok' : 'bg-mem'}`} />
          <span>{isLive ? 'Live Mode' : 'Demo Mode'}</span>
        </button>

        {detailsOpen && (
          <DemoModeDetailsDialog
            isLive={isLive}
            connStatus={connStatus}
            onClose={() => setDetailsOpen(false)}
            onRefresh={refreshConnection}
          />
        )}
      </div>
    )
  }

  return (
    <>
      <div
        className={`flex items-center justify-between gap-2.5 rounded-md border px-3 py-1.5 text-xs transition-opacity duration-200 ${
          isLive
            ? 'border-ok/30 bg-ok/5 text-tx'
            : 'border-mem/25 bg-mem/5 text-tx'
        }`}
        data-tour="mode-banner"
      >
        <div className="flex items-center gap-2 min-w-0">
          <span
            className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider ${
              isLive ? 'bg-ok/20 text-ok' : 'bg-mem/20 text-mem'
            }`}
          >
            {isLive ? <Wifi size={11} /> : <WifiOff size={11} />}
            {isLive ? 'Live Mode' : 'Demo Mode'}
          </span>
          <span className="truncate text-mu text-[11.5px]">
            {isLive
              ? 'Connected to FastAPI backend and Nebius Token Factory.'
              : 'Running with local simulator stand-in. All warehouse recovery runs in-browser.'}
          </span>
        </div>

        <div className="flex items-center gap-2 flex-none">
          <button
            onClick={() => setDetailsOpen(true)}
            className="text-[11px] font-medium text-obs hover:underline flex items-center gap-0.5"
          >
            <Info size={12} />
            Details
          </button>

          <button
            onClick={handleDismiss}
            className="rounded p-1 text-mu hover:text-tx transition"
            aria-label="Dismiss banner"
            title="Dismiss indicator (reopen via sidebar anytime)"
          >
            <X size={13} />
          </button>
        </div>
      </div>

      {detailsOpen && (
        <DemoModeDetailsDialog
          isLive={isLive}
          connStatus={connStatus}
          onClose={() => setDetailsOpen(false)}
          onRefresh={refreshConnection}
        />
      )}
    </>
  )
}

function DemoModeDetailsDialog({ isLive, connStatus, onClose, onRefresh }) {
  useEffect(() => {
    const handleKey = (e) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [onClose])

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-xs animate-in fade-in duration-150"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-md rounded-xl border border-ln bg-s1 p-5 shadow-2xl shadow-black/80"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-ln/60 pb-3">
          <div className="flex items-center gap-2">
            <span
              className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${
                isLive ? 'bg-ok/20 text-ok' : 'bg-mem/20 text-mem'
              }`}
            >
              {isLive ? 'Live Mode' : 'Demo Mode'}
            </span>
            <h3 className="text-sm font-bold text-tx">Operating Mode & Environment</h3>
          </div>
          <button onClick={onClose} className="rounded p-1 text-mu hover:text-tx">
            <X size={15} />
          </button>
        </div>

        <div className="mt-3 space-y-2.5 text-xs">
          <div className="rounded-lg border border-ln/60 bg-s2/50 p-3">
            <h4 className="font-semibold text-tx mb-1">
              {isLive ? 'Full Stack Connected' : 'What Demo Mode Means'}
            </h4>
            <p className="text-mu leading-relaxed text-[11.5px]">
              {isLive
                ? 'Your session is communicating with the live Python FastAPI backend and configured cloud AI models.'
                : 'Second Look is running with its integrated browser-side physics simulator and deterministic Bayesian belief tracker. All interactive features, picks, and recovery scenarios function locally without needing an active server.'}
            </p>
          </div>

          <div className="grid grid-cols-2 gap-2 text-[11px]">
            <div className="rounded-lg border border-ln/50 bg-s2/30 p-2.5">
              <span className="font-semibold text-tx block mb-1">Runs Locally</span>
              <ul className="text-mu space-y-0.5">
                <li>• MuJoCo scenario emulation</li>
                <li>• Bayesian belief updates</li>
                <li>• Recovery state machine</li>
                <li>• Comparative analytics</li>
              </ul>
            </div>
            <div className="rounded-lg border border-ln/50 bg-s2/30 p-2.5">
              <span className="font-semibold text-tx block mb-1">Requires Backend</span>
              <ul className="text-mu space-y-0.5">
                <li>• Live MuJoCo C-native sim</li>
                <li>• WebSocket telemetry stream</li>
                <li>• Nebius Token Factory API</li>
                <li>• NVIDIA Nemotron reasoning</li>
              </ul>
            </div>
          </div>
        </div>

        <div className="mt-4 flex items-center justify-between border-t border-ln/60 pt-3 text-xs">
          <span className="text-[11px] text-mu font-mono">
            Backend: {connStatus.backend.status}
          </span>
          <div className="flex gap-2">
            <button
              onClick={() => onRefresh(true)}
              disabled={connStatus.isChecking}
              className="flex items-center gap-1 rounded-md border border-ln bg-s2 px-2.5 py-1 text-[11px] font-medium text-tx hover:bg-s2/80 disabled:opacity-50"
            >
              <RefreshCw size={11} className={connStatus.isChecking ? 'animate-spin' : ''} />
              {connStatus.isChecking ? 'Checking...' : 'Check Live'}
            </button>
            <button
              onClick={onClose}
              className="rounded-md bg-obs px-3 py-1 text-[11px] font-bold text-[#06201c] hover:bg-obs/90"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
