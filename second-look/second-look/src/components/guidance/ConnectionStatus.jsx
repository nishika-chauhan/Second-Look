import { Server, Activity } from 'lucide-react'
import { useGuidance } from '../../context/GuidanceContext.jsx'

export default function ConnectionStatus() {
  const { connStatus, openConnModal } = useGuidance()

  // Determine overall aggregate health color and label
  const backendOk = connStatus.backend.status === 'connected'
  const nebiusOk = connStatus.nebius.status === 'verified' || connStatus.nebius.status === 'configured'
  const nemotronReady = connStatus.nemotron.status === 'ready'

  let dotColor = 'var(--ok)'
  let label = 'Live Systems'
  let sub = 'Connected'

  if (connStatus.isChecking) {
    dotColor = 'var(--mem)'
    label = 'Checking'
    sub = 'Verifying services...'
  } else if (!backendOk) {
    dotColor = 'var(--mem)'
    label = 'Stand-in Simulator'
    sub = 'Local Mode'
  } else if (!nebiusOk || !nemotronReady) {
    dotColor = 'var(--acc)'
    label = 'Backend Online'
    sub = 'Local Planner Active'
  }

  return (
    <button
      onClick={openConnModal}
      className="group flex items-center gap-2.5 rounded-full border border-ln bg-s1/90 px-3 py-1.5 text-left text-xs transition hover:border-obs/60 hover:bg-s2 shadow-sm"
      title="Click to view detailed service connectivity"
      data-tour="connection-pill"
    >
      <span className="relative flex h-2.5 w-2.5 flex-none items-center justify-center">
        <span
          className="absolute inline-flex h-full w-full animate-ping rounded-full opacity-40"
          style={{ background: dotColor }}
        />
        <span
          className="relative inline-flex h-2 w-2 rounded-full"
          style={{ background: dotColor }}
        />
      </span>

      <span className="flex items-center gap-1.5 font-medium text-tx">
        <Server size={12} className="text-mu group-hover:text-obs transition" />
        <span>{label}</span>
      </span>

      <span className="hidden text-[11px] text-mu sm:inline-block border-l border-ln pl-2">
        {sub}
      </span>

      <Activity size={12} className="text-mu opacity-50 group-hover:opacity-100 transition" />
    </button>
  )
}
