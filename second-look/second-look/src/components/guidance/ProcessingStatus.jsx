import { Cpu, CheckCircle2, Clock, AlertTriangle } from 'lucide-react'
import { useRobot } from '../../RobotContext.jsx'
import { PATH } from '../../lib/constants.js'

export default function ProcessingStatus({ className = '' }) {
  const { s } = useRobot()

  if (!s.running && !s.decision && !s.evidence.length) return null

  // Determine stage based on actual state
  const isMoving = s.status === 'moving'
  const isScanning = s.status === 'searching'
  const isGrasping = s.status === 'retrieving'
  const isDone = s.status === 'completed'
  const isFailed = s.status === 'failed'

  const stages = [
    {
      label: 'Context Preparation',
      sub: `SKU: ${s.obj.toUpperCase()} | Prior: ${s.last}`,
      done: true,
      active: false,
    },
    {
      label: 'Workspace Perception',
      sub: s.obs ? (s.obs.seen ? `Detected at ${s.obs.loc}` : `Not at ${s.obs.loc}`) : 'Scanning cameras...',
      done: isScanning || isGrasping || isDone || isFailed,
      active: isScanning,
    },
    {
      label: 'Nebius Inference & Nemotron Reasoning',
      sub: s.decision ? `Policy: ${PATH[s.decision.path]?.[0] || 'Selected'}` : 'Evaluating spatial beliefs...',
      done: !!s.decision,
      active: isScanning && !s.decision,
    },
    {
      label: 'Decision Output & Execution',
      sub: isDone ? 'Retrieval completed' : isFailed ? 'Recovery escalated' : isGrasping ? 'Grasping object...' : isMoving ? `Navigating to ${s.at}...` : 'Executing action',
      done: isDone || isFailed,
      active: isMoving || isGrasping,
    },
  ]

  return (
    <div className={`rounded-xl border border-ln bg-s1 p-4 shadow-sm ${className}`}>
      <div className="flex items-center justify-between border-b border-ln/60 pb-2.5 mb-3">
        <div className="flex items-center gap-2">
          <Cpu size={15} className="text-obs" />
          <h4 className="text-xs font-bold text-tx">AI Inference & Execution Pipeline</h4>
        </div>
        <span className="rounded-full bg-s2 px-2 py-0.5 text-[10px] font-mono text-mu border border-ln">
          {s.running ? 'Live Processing' : isDone ? 'Complete' : 'Idle'}
        </span>
      </div>

      <div className="grid gap-2 sm:grid-cols-4">
        {stages.map((st, i) => (
          <div
            key={i}
            className={`rounded-lg border p-2.5 transition ${
              st.active
                ? 'border-obs bg-obs/10 shadow-sm'
                : st.done
                ? 'border-ln bg-s2/40'
                : 'border-ln/40 bg-s2/20 opacity-50'
            }`}
          >
            <div className="flex items-center justify-between mb-1">
              <span className="text-[10px] font-bold uppercase tracking-wider text-mu">
                Step 0{i + 1}
              </span>
              {st.done ? (
                <CheckCircle2 size={13} className="text-ok" />
              ) : st.active ? (
                <span className="relative flex h-2 w-2">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-obs opacity-75" />
                  <span className="relative inline-flex h-2 w-2 rounded-full bg-obs" />
                </span>
              ) : (
                <Clock size={12} className="text-mu/60" />
              )}
            </div>
            <div className="text-xs font-semibold text-tx leading-tight">{st.label}</div>
            <div className="mt-0.5 truncate text-[10.5px] text-mu">{st.sub}</div>
          </div>
        ))}
      </div>

      {s.decision && (
        <div className="mt-3 rounded-lg border border-ln/80 bg-s2/60 p-2.5 flex items-start gap-2">
          {isFailed ? (
            <AlertTriangle size={15} className="text-bad mt-0.5 flex-none" />
          ) : (
            <CheckCircle2 size={15} className="text-ok mt-0.5 flex-none" />
          )}
          <div className="min-w-0 text-[11.5px]">
            <span className="font-semibold text-tx">Result: </span>
            <span className="text-tx/90">{s.decision.text}</span>
          </div>
        </div>
      )}
    </div>
  )
}
