import { Sparkles, ArrowRight, Cpu, Bot, Brain, FlaskConical, BarChart3 } from 'lucide-react'
import { Panel, Muted } from '../components/ui.jsx'
import { useGuidance } from '../context/GuidanceContext.jsx'

const STEPS = [
  { k: 'workstation', a: 'Start retrieval', b: 'Robot Workstation', icon: Bot, col: 'var(--obs)' },
  { k: 'memory', a: 'Observe memory & decisions', b: 'Memory & Decisions', icon: Brain, col: 'var(--mem)' },
  { k: 'playground', a: 'Trigger recovery scenarios', b: 'Recovery Playground', icon: FlaskConical, col: 'var(--acc)' },
  { k: 'analytics', a: 'Evaluate benchmark outcomes', b: 'Results & Analytics', icon: BarChart3, col: 'var(--ok)' },
]

export default function Overview({ setView }) {
  const { startTour, openArchModal } = useGuidance()

  return (
    <>
      <Panel data-tour="overview-hero" className="border-obs/30 bg-gradient-to-br from-s1 via-s1 to-s2/70 p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="max-w-[70ch]">
            <div className="flex items-center gap-2 mb-2">
              <span className="rounded-full border border-obs/30 bg-obs/10 px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wider text-obs flex items-center gap-1.5">
                <Sparkles size={12} />
                Nebius × NVIDIA AI Hackathon
              </span>
            </div>
            <h2 className="text-xl font-bold tracking-tight text-tx sm:text-2xl">
              Can the robot trust what it remembers?
            </h2>
            <p className="mt-2 text-xs sm:text-sm leading-relaxed text-mu">
              Second Look maintains probabilistic spatial beliefs about warehouse inventory. When an item is moved, missing, or slips from the gripper, it uses Bayesian belief updating and NVIDIA Nemotron reasoning to autonomously recover without halting the warehouse.
            </p>
          </div>

          <div className="flex flex-wrap gap-2.5 flex-none">
            <button
              onClick={() => startTour('welcome')}
              className="flex items-center gap-2 rounded-lg bg-obs px-4 py-2.5 text-xs font-bold text-[#06201c] shadow-md shadow-obs/20 transition hover:bg-obs/90"
            >
              <Sparkles size={14} />
              Start Guided Tour
              <ArrowRight size={13} />
            </button>
            <button
              onClick={openArchModal}
              className="flex items-center gap-2 rounded-lg border border-ln bg-s2 px-3.5 py-2.5 text-xs font-semibold text-tx transition hover:bg-s2/80"
              data-tour="arch-button"
            >
              <Cpu size={14} className="text-obs" />
              Architecture
            </button>
          </div>
        </div>
      </Panel>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {STEPS.map((step, i) => {
          const Icon = step.icon
          return (
            <button
              key={step.k}
              onClick={() => setView(step.k)}
              className="group flex flex-col justify-between rounded-xl border border-ln bg-s1 p-4 text-left transition hover:border-obs hover:bg-s2/50"
            >
              <div>
                <div className="flex items-center justify-between mb-3">
                  <div
                    className="flex h-8 w-8 items-center justify-center rounded-lg"
                    style={{ background: `${step.col}20`, color: step.col }}
                  >
                    <Icon size={17} />
                  </div>
                  <span className="text-[11px] font-mono text-mu">Step 0{i + 1}</span>
                </div>
                <b className="block text-sm text-tx group-hover:text-obs transition">
                  {step.a}
                </b>
                <Muted className="mt-0.5 text-xs">{step.b}</Muted>
              </div>

              <div className="mt-4 flex items-center gap-1 text-[11px] font-semibold text-obs opacity-75 group-hover:opacity-100 transition">
                <span>Explore</span>
                <ArrowRight size={12} className="group-hover:translate-x-0.5 transition-transform" />
              </div>
            </button>
          )
        })}
      </div>
    </>
  )
}
