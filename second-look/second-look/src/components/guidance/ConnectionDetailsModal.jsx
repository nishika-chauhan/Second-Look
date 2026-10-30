import { X, RefreshCw, CheckCircle2, AlertCircle, Cpu, Server, Database, ShieldCheck } from 'lucide-react'
import { useGuidance } from '../../context/GuidanceContext.jsx'

export default function ConnectionDetailsModal() {
  const { connModalOpen, closeConnModal, connStatus, refreshConnection } = useGuidance()

  if (!connModalOpen) return null

  const services = [
    {
      id: 'backend',
      icon: Server,
      name: 'Python FastAPI Backend',
      status: connStatus.backend.status,
      desc: 'Central telemetry and WebSocket coordinator bridging UI to robotics.',
      details: connStatus.backend.detail || `Uptime: ${connStatus.backend.uptime_s || 0}s | v${connStatus.backend.version || '2.1.0'}`,
      isOk: connStatus.backend.status === 'connected',
    },
    {
      id: 'nebius',
      icon: Cpu,
      name: 'Nebius Token Factory',
      status: connStatus.nebius.status,
      desc: 'High-throughput cloud inference API gateway hosting NVIDIA models.',
      details: connStatus.nebius.detail || (connStatus.nebius.status === 'configured' ? 'API Key configured' : 'Unconfigured - using local planner fallback'),
      isOk: connStatus.nebius.status === 'verified' || connStatus.nebius.status === 'configured',
    },
    {
      id: 'nemotron',
      icon: Cpu,
      name: 'NVIDIA Nemotron-4 Reasoner',
      status: connStatus.nemotron.status,
      desc: 'Instruction LLM generating structured JSON recovery actions under spatial uncertainty.',
      details: connStatus.nemotron.model || 'nvidia/nemotron-4-340b-instruct',
      isOk: connStatus.nemotron.status === 'ready',
    },
    {
      id: 'simulator',
      icon: Database,
      name: 'Simulation Environment',
      status: connStatus.simulator.status,
      desc: 'Physics-grounded MuJoCo environment (or client-side stand-in emulator).',
      details: connStatus.simulator.detail || 'MuJoCo SecondLookEnv',
      isOk: connStatus.simulator.status === 'connected' || connStatus.simulator.status === 'standby',
    },
  ]

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="relative w-full max-w-xl rounded-2xl border border-ln bg-s1 p-6 shadow-2xl shadow-black/80 sm:p-7">
        <button
          onClick={closeConnModal}
          className="absolute right-4 top-4 rounded-lg p-2 text-mu transition hover:bg-s2 hover:text-tx"
          aria-label="Close"
        >
          <X size={18} />
        </button>

        <div className="flex items-center justify-between border-b border-ln/60 pb-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="inline-block h-2.5 w-2.5 rounded-full bg-obs animate-pulse" />
              <h2 className="text-lg font-bold text-tx">System & AI Infrastructure Health</h2>
            </div>
            <p className="mt-0.5 text-xs text-mu">
              Real-time connectivity status across backend, simulation, and cloud AI services.
            </p>
          </div>
        </div>

        <div className="mt-4 space-y-3">
          {services.map((s) => {
            const Icon = s.icon
            return (
              <div
                key={s.id}
                className="flex items-start justify-between gap-3 rounded-xl border border-ln/80 bg-s2/50 p-3.5 transition hover:border-ln"
              >
                <div className="flex items-start gap-3">
                  <div
                    className={`mt-0.5 flex h-8 w-8 flex-none items-center justify-center rounded-lg ${
                      s.isOk ? 'bg-ok/10 text-ok' : 'bg-mem/10 text-mem'
                    }`}
                  >
                    <Icon size={17} />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h4 className="text-xs font-bold text-tx">{s.name}</h4>
                      <span
                        className={`rounded-full px-2 py-0.2 text-[10px] font-semibold uppercase ${
                          s.isOk
                            ? 'bg-ok/15 text-ok border border-ok/30'
                            : 'bg-mem/15 text-mem border border-mem/30'
                        }`}
                      >
                        {s.status}
                      </span>
                    </div>
                    <p className="mt-0.5 text-[11px] text-mu">{s.desc}</p>
                    <p className="mt-1 text-[11px] font-mono text-tx/80">{s.details}</p>
                  </div>
                </div>

                <div className="flex-none pt-1">
                  {s.isOk ? (
                    <CheckCircle2 size={16} className="text-ok" />
                  ) : (
                    <AlertCircle size={16} className="text-mem" />
                  )}
                </div>
              </div>
            )
          })}
        </div>

        <div className="mt-4 rounded-lg border border-ln/50 bg-s2/30 p-2.5 text-[11px] text-mu flex items-center gap-2">
          <ShieldCheck size={16} className="text-ok flex-none" />
          <span>
            API tokens and backend secrets are securely isolated on the server. No credentials are leaked to the client.
          </span>
        </div>

        <div className="mt-5 flex items-center justify-between border-t border-ln/60 pt-4">
          <span className="text-[11px] text-mu">
            {connStatus.lastCheck ? `Last checked: ${connStatus.lastCheck}` : 'Checking services...'}
          </span>

          <div className="flex gap-2">
            <button
              onClick={() => refreshConnection(true)}
              disabled={connStatus.isChecking}
              className="flex items-center gap-1.5 rounded-lg border border-ln bg-s2 px-3 py-1.5 text-xs font-semibold text-tx transition hover:bg-s2/80 disabled:opacity-50"
            >
              <RefreshCw size={13} className={connStatus.isChecking ? 'animate-spin' : ''} />
              {connStatus.isChecking ? 'Verifying...' : 'Re-check Services'}
            </button>
            <button
              onClick={closeConnModal}
              className="rounded-lg bg-obs px-4 py-1.5 text-xs font-bold text-[#06201c] transition hover:bg-obs/90"
            >
              Done
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
