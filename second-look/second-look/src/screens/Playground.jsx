import { useState } from 'react'
import { Play, Pause, RotateCcw, ChevronDown, ChevronUp, CheckCircle2, AlertCircle, Sparkles, Activity } from 'lucide-react'
import { useRobot } from '../RobotContext.jsx'
import { L, PATH, OBJ, SCN, ST, pc } from '../lib/constants.js'
import Scene from '../components/Scene.jsx'
import { Panel, H, Muted, Banner, ObjectChips, Btn } from '../components/ui.jsx'
import { PRELOADED_EXAMPLES } from '../config/guidance/examples.js'
import InfoTooltip from '../components/guidance/InfoTooltip.jsx'
import { useGuidance } from '../context/GuidanceContext.jsx'

export default function Playground() {
  const { s, a } = useRobot()
  const { connStatus } = useGuidance()
  const [detailsExpanded, setDetailsExpanded] = useState(false)

  // Current active scenario example info
  const activeEx = PRELOADED_EXAMPLES.find((ex) => ex.scenario === s.scn) || PRELOADED_EXAMPLES[1]
  const O = OBJ[s.obj], d = s.decision
  const isLive = connStatus.backend.status === 'connected'

  const selectScenario = (sc) => {
    a.scenario(sc)
    const ex = PRELOADED_EXAMPLES.find((e) => e.scenario === sc)
    if (ex && ex.obj !== s.obj && !s.running) {
      a.setObj(ex.obj)
    }
  }

  // Derive meaningful processing state from actual application state
  const isExecuting = s.running
  const isScanning = s.status === 'searching'
  const isDone = s.status === 'completed'
  const isFailed = s.status === 'failed'

  let currentProcessState = 'Ready to Run'
  let processBadgeCol = 'var(--mu)'

  if (isExecuting) {
    if (isScanning) {
      currentProcessState = 'Evaluating Warehouse State'
      processBadgeCol = 'var(--mem)'
    } else if (d) {
      currentProcessState = 'Recovery Decision Generated'
      processBadgeCol = 'var(--acc)'
    } else {
      currentProcessState = 'Executing Retrieval'
      processBadgeCol = 'var(--obs)'
    }
  } else if (isDone) {
    currentProcessState = 'Completed'
    processBadgeCol = 'var(--ok)'
  } else if (isFailed) {
    currentProcessState = 'Failed / Escalated'
    processBadgeCol = 'var(--bad)'
  }

  return (
    <div className="space-y-3.5">
      {/* A. Compact Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 border-b border-ln/60 pb-2.5">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold tracking-tight text-tx">Recovery Playground</h1>
            <span
              className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${
                isLive ? 'bg-ok/15 text-ok border border-ok/30' : 'bg-mem/15 text-mem border border-mem/30'
              }`}
            >
              {isLive ? 'Live AI Mode' : 'Simulation Mode'}
            </span>
          </div>
          <p className="text-xs text-mu mt-0.5">
            Explore how Second Look handles uncertain warehouse locations, unexpected events, and failed retrieval attempts.
          </p>
        </div>

        <div className="flex items-center gap-2 self-start sm:self-auto">
          {s.outcome && (
            <button
              onClick={a.reset}
              className="flex items-center gap-1.5 rounded-lg border border-ln bg-s2 px-2.5 py-1 text-xs font-medium text-tx hover:bg-s2/80 transition"
            >
              <RotateCcw size={12} />
              Reset State
            </button>
          )}
        </div>
      </div>

      {/* B. Compact Scenario Selector */}
      <div data-tour="playground-scenarios">
        <div className="flex items-center justify-between mb-1.5">
          <span className="text-[11px] font-bold uppercase tracking-wider text-mu">
            1. Select Disturbance Scenario
          </span>
          <span className="text-[11px] text-mu">
            Active: <strong className="text-tx">{SCN[s.scn]}</strong>
          </span>
        </div>

        <div className="grid gap-2 grid-cols-2 lg:grid-cols-4">
          {PRELOADED_EXAMPLES.map((ex) => {
            const isSelected = s.scn === ex.scenario
            return (
              <button
                key={ex.id}
                onClick={() => selectScenario(ex.scenario)}
                className={`flex flex-col justify-between rounded-xl border p-2.5 text-left transition ${
                  isSelected
                    ? 'border-obs bg-s2 shadow-sm ring-1 ring-obs'
                    : 'border-ln/70 bg-s1/80 hover:border-ln hover:bg-s2/50'
                }`}
              >
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <span
                      className="rounded px-1.5 py-0.2 text-[9.5px] font-bold uppercase"
                      style={{ background: `${ex.badgeCol}20`, color: ex.badgeCol }}
                    >
                      {ex.badge}
                    </span>
                    {isSelected && <CheckCircle2 size={13} className="text-obs" />}
                  </div>
                  <h4 className="text-xs font-bold text-tx leading-tight">{ex.title}</h4>
                  <p className="mt-1 line-clamp-1 text-[11px] text-mu">{ex.desc}</p>
                </div>

                <div className="mt-2 flex items-center justify-between border-t border-ln/40 pt-1.5 text-[10.5px]">
                  <span className="text-mu">Path: <strong className="text-tx">{ex.expectedDecision}</strong></span>
                  <span className={`font-semibold ${isSelected ? 'text-obs' : 'text-mu'}`}>
                    {isSelected ? 'Active' : 'Select'}
                  </span>
                </div>
              </button>
            )
          })}
        </div>
      </div>

      {/* C. Interactive Simulation Workspace (Main Visual Focus) */}
      <div className="grid gap-3.5 lg:grid-cols-[1.65fr_1fr]">
        <Panel data-tour="playground-scene" className="p-3.5 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold text-tx">Warehouse Gantry Workspace</span>
                <span className="rounded bg-s2 px-1.5 py-0.5 text-[10.5px] font-mono text-mu border border-ln">
                  {SCN[s.scn]}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[11px] text-mu">
                  Actual: <strong className="text-tx">{s.actual ? L[s.actual].n : 'Removed'}</strong>
                </span>
                <InfoTooltip
                  title="Perceptual Coordinates"
                  body="Dashed amber ring = remembered position. Solid teal item = physical simulated coordinate."
                />
              </div>
            </div>

            <Scene />

            <div className="mt-2 flex items-center justify-between text-[11px]">
              <span className="text-mem font-medium">Dashed ring: remembered</span>
              <span className="text-obs font-medium">Solid item: ground truth</span>
            </div>
          </div>

          {/* Integrated Simulation Controls & SKU Selection */}
          <div className="mt-3 border-t border-ln/60 pt-3 flex flex-wrap items-center justify-between gap-2.5">
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold text-mu">Target SKU:</span>
              <ObjectChips />
            </div>

            <div className="flex items-center gap-2">
              <Btn
                primary
                icon={Play}
                onClick={a.start}
                disabled={s.running}
                className="py-1.5 px-3.5 text-xs shadow-md shadow-obs/20 font-bold"
              >
                {s.running ? 'Running...' : 'Run Simulation'}
              </Btn>

              <Btn
                icon={Pause}
                onClick={a.pause}
                disabled={!s.running}
                className="py-1.5 px-3 text-xs"
              >
                {s.paused ? 'Resume' : 'Pause'}
              </Btn>

              <Btn
                icon={RotateCcw}
                onClick={a.reset}
                className="py-1.5 px-3 text-xs"
              >
                Reset
              </Btn>
            </div>
          </div>
        </Panel>

        {/* D. Processing & Live Recovery Status Column */}
        <Panel className="p-3.5 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between border-b border-ln/60 pb-2 mb-2.5">
              <div className="flex items-center gap-1.5">
                <Activity size={14} className="text-obs" />
                <H className="mb-0 text-xs">Execution & Recovery Telemetry</H>
              </div>
              <span
                className="rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider"
                style={{ background: `${processBadgeCol}20`, color: processBadgeCol }}
              >
                {currentProcessState}
              </span>
            </div>

            {/* Task Progress Bar */}
            <div className="mb-3">
              <div className="flex justify-between text-[11px] mb-1">
                <span className="text-mu">Task Lifecycle</span>
                <span className="font-mono text-tx">{s.progress}%</span>
              </div>
              <div className="h-1.5 overflow-hidden rounded bg-s2">
                <div
                  className="h-full bg-obs transition-all duration-300"
                  style={{ width: `${s.progress}%` }}
                />
              </div>
              <p className="mt-1.5 text-xs text-tx font-medium">{s.msg}</p>
            </div>

            {/* Processing Pipeline Stages */}
            <div className="space-y-1.5 text-xs">
              <div className={`rounded-lg border p-2 flex items-center justify-between ${
                s.running ? 'border-obs/50 bg-obs/10' : 'border-ln/60 bg-s2/30'
              }`}>
                <span className="text-tx font-medium">1. Approach Target</span>
                <span className="font-mono text-[11px] text-mu">{L[s.last].n} (Prior)</span>
              </div>

              <div className={`rounded-lg border p-2 flex items-center justify-between ${
                isScanning ? 'border-mem/50 bg-mem/10 text-mem' : 'border-ln/60 bg-s2/30'
              }`}>
                <span className="text-tx font-medium">2. Visual Scan</span>
                <span className="text-[11px] text-mu">
                  {s.obs ? (s.obs.seen ? `Detected at ${s.obs.loc}` : `Not at ${s.obs.loc}`) : 'Awaiting Scan'}
                </span>
              </div>

              <div className={`rounded-lg border p-2 flex items-center justify-between ${
                d ? 'border-acc/50 bg-acc/10' : 'border-ln/60 bg-s2/30'
              }`}>
                <span className="text-tx font-medium">3. Nemotron Decision</span>
                <span className="text-[11px] font-bold text-acc">
                  {d ? PATH[d.path][0] : 'Standby'}
                </span>
              </div>
            </div>

            {s.outcome && <Banner outcome={s.outcome} />}
          </div>

          {/* Quick Active Decision Callout */}
          {d && (
            <div className="mt-3 rounded-lg border border-acc/40 bg-s2/70 p-2.5 text-[11.5px]">
              <span className="font-bold text-acc">{PATH[d.path][0]}: </span>
              <span className="text-tx/90">{d.text}</span>
            </div>
          )}
        </Panel>
      </div>

      {/* E. Results Section: Remembered vs Observed vs Decided & 4 Paths */}
      <div className="space-y-3">
        <div className="grid gap-3 lg:grid-cols-3">
          <Panel style={{ borderTop: '3px solid var(--mem)' }} className="p-3">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold uppercase tracking-wider text-mu">Prior Memory</span>
              <span className="font-mono text-xs text-mem">{pc(s.beliefs[s.last])}</span>
            </div>
            <p className="mt-1 text-xs text-tx font-medium">
              {O} last seen on {L[s.last].n}.
            </p>
          </Panel>

          <Panel style={{ borderTop: '3px solid var(--obs)' }} className="p-3">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold uppercase tracking-wider text-mu">Sensory Feedback</span>
              <span className="text-[11px] font-mono text-obs">{s.obs?.seen ? 'Verified' : 'Absent'}</span>
            </div>
            <p className="mt-1 text-xs text-tx font-medium">
              {s.obs ? s.obs.text : 'Awaiting sensor feedback.'}
            </p>
          </Panel>

          <Panel style={{ borderTop: '3px solid var(--acc)' }} className="p-3">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold uppercase tracking-wider text-mu">Recovery Directive</span>
              <span className="text-[11px] font-bold text-acc">{d ? PATH[d.path][0] : 'Idle'}</span>
            </div>
            <p className="mt-1 text-xs text-tx font-medium">
              {d ? d.text : 'Waiting for scenario execution.'}
            </p>
          </Panel>
        </div>

        {/* Four Recovery Paths Highlight */}
        <div data-tour="recovery-paths" className="grid gap-2.5 grid-cols-2 lg:grid-cols-4">
          {Object.entries(PATH).map(([k, [n, t]]) => {
            const isActive = d?.path === k
            return (
              <div
                key={k}
                className={`rounded-lg border p-2.5 transition ${
                  isActive
                    ? 'border-acc bg-s2 text-tx shadow-sm ring-1 ring-acc'
                    : 'border-ln/70 bg-s1/60 opacity-60'
                }`}
              >
                <div className="flex items-center justify-between mb-0.5">
                  <b className="text-xs text-tx">{n}</b>
                  {isActive && (
                    <span className="rounded bg-acc/20 px-1 py-0.2 text-[9px] font-bold text-acc uppercase">
                      Active
                    </span>
                  )}
                </div>
                <p className="text-[11px] text-mu line-clamp-2">{t}</p>
              </div>
            )
          })}
        </div>
      </div>

      {/* F. Detailed Scenario Explanation (Collapsible) */}
      {activeEx && (
        <div className="rounded-xl border border-ln/80 bg-s1/90 overflow-hidden">
          <button
            onClick={() => setDetailsExpanded((v) => !v)}
            className="w-full flex items-center justify-between p-3 text-left hover:bg-s2/40 transition"
          >
            <div className="flex items-center gap-2">
              <Sparkles size={14} className="text-obs" />
              <span className="text-xs font-bold text-tx">
                Understand this scenario: {activeEx.title}
              </span>
            </div>
            <div className="flex items-center gap-1.5 text-xs text-mu">
              <span>{detailsExpanded ? 'Hide details' : 'Show details'}</span>
              {detailsExpanded ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
            </div>
          </button>

          {detailsExpanded && (
            <div className="border-t border-ln/60 p-4 bg-s2/30 grid gap-3 sm:grid-cols-2 text-xs">
              <div>
                <h5 className="font-semibold text-tx mb-1">What to observe during execution:</h5>
                <ul className="space-y-1 text-mu text-[11.5px]">
                  {activeEx.whatToObserve.map((pt, i) => (
                    <li key={i} className="flex items-start gap-1.5">
                      <span className="text-obs font-bold">›</span>
                      <span>{pt}</span>
                    </li>
                  ))}
                </ul>
              </div>

              <div className="space-y-2">
                <div className="rounded-lg border border-ln/50 bg-s1/60 p-2.5">
                  <span className="font-semibold text-tx block text-[11px] mb-0.5">State Transition:</span>
                  <p className="text-mu text-[11px]">
                    Before: <strong className="text-tx">{activeEx.beforeState}</strong>
                  </p>
                  <p className="text-mu text-[11px] mt-0.5">
                    Expected After: <strong className="text-tx">{activeEx.afterState}</strong>
                  </p>
                </div>

                <div className="rounded-lg border border-ln/50 bg-s1/60 p-2.5">
                  <span className="font-semibold text-tx block text-[11px] mb-0.5">Key Takeaway:</span>
                  <p className="text-mu text-[11px] leading-relaxed">{activeEx.takeaway}</p>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
