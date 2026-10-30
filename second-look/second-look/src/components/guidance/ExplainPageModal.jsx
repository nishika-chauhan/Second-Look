import { X, Bot, Brain, FlaskConical, BarChart3, LayoutDashboard } from 'lucide-react'
import { useGuidance } from '../../context/GuidanceContext.jsx'

const PAGE_EXPLANATIONS = {
  overview: {
    title: 'Overview & Mission',
    icon: LayoutDashboard,
    color: 'var(--obs)',
    summary: 'Central introduction to Second Look and the fundamental problem of warehouse spatial uncertainty.',
    sections: [
      {
        heading: 'The Core Challenge',
        text: 'Robotic warehouse pickers rely on database coordinates. When items are accidentally moved, conventional automation triggers critical fault stops.',
      },
      {
        heading: 'The Second Look Solution',
        text: 'Maintains probabilistic memory of object locations, updates beliefs via active visual sensing, and calls NVIDIA Nemotron to orchestrate recovery paths.',
      },
    ],
  },
  workstation: {
    title: 'Robot Workstation (Execution View)',
    icon: Bot,
    color: 'var(--obs)',
    summary: 'Live Cartesian gantry simulation showing real-time pick-and-place execution between Table A, Table B, and Shelf C.',
    sections: [
      {
        heading: 'Visual Workspace',
        text: 'The dashed amber ring marks remembered position. The solid teal item marks ground truth. The moving gantry cart illustrates camera scanning cones.',
      },
      {
        heading: 'Controls & Event Log',
        text: 'Initiate picks with Cup, Bottle, or Box SKUs. Every movement, visual scan, slip, and re-planning step is logged with exact timestamps.',
      },
    ],
  },
  memory: {
    title: 'Live Memory & Decisions',
    icon: Brain,
    color: 'var(--mem)',
    summary: 'Deep-dive into Bayesian belief updating and multi-step recovery reasoning.',
    sections: [
      {
        heading: 'Belief Distribution',
        text: 'Probabilities across Table A, B, C, and Out of View. Searching an empty station drops its probability to near zero and redistributes confidence to remaining stations.',
      },
      {
        heading: 'Decision Engine',
        text: 'Displays the selected recovery path: Trust Memory (direct pick), Search Elsewhere (re-localization), Retry (grasp slip), or Help (human escalation).',
      },
    ],
  },
  playground: {
    title: 'Recovery Playground',
    icon: FlaskConical,
    color: 'var(--acc)',
    summary: 'Interactive testing sandbox to stress-test Second Look against real-world perturbations.',
    sections: [
      {
        heading: 'Preloaded Scenarios',
        text: 'Test Nominal Retrieval, Object Moved (spatial displacement), Missing Item (total loss), and Mechanical Slip (grasp failure).',
      },
      {
        heading: 'Before & After Comparison',
        text: 'Observe how the system detects discrepancies between expectations and sensory reality, recovering without operator intervention.',
      },
    ],
  },
  analytics: {
    title: 'Results & Benchmark Analytics',
    icon: BarChart3,
    color: 'var(--ok)',
    summary: 'Statistical evaluation comparing Second Look against a fixed-memory baseline.',
    sections: [
      {
        heading: 'Key Metrics',
        text: 'Success Rate (Second Look achieves near 100% on moved items vs 0% for baseline), Average Recovery Attempts, and Execution Latency.',
      },
      {
        heading: 'Simulation Batches',
        text: 'Click "Run 16 simulated trials" to generate randomized batches across all SKU types and scenarios in seconds.',
      },
    ],
  },
}

export default function ExplainPageModal() {
  const { explainModalOpen, closeExplain, currentView } = useGuidance()

  if (!explainModalOpen) return null

  const page = PAGE_EXPLANATIONS[currentView] || PAGE_EXPLANATIONS.overview
  const Icon = page.icon

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="relative w-full max-w-xl rounded-2xl border border-ln bg-s1 p-6 shadow-2xl shadow-black/80 sm:p-7">
        <button
          onClick={closeExplain}
          className="absolute right-4 top-4 rounded-lg p-2 text-mu transition hover:bg-s2 hover:text-tx"
          aria-label="Close"
        >
          <X size={18} />
        </button>

        <div className="flex items-center gap-3 border-b border-ln/60 pb-3">
          <div
            className="flex h-9 w-9 items-center justify-center rounded-xl"
            style={{ background: `${page.color}20`, color: page.color }}
          >
            <Icon size={19} />
          </div>
          <div>
            <h2 className="text-base font-bold text-tx">{page.title}</h2>
            <p className="text-xs text-mu">{page.summary}</p>
          </div>
        </div>

        <div className="mt-4 space-y-3">
          {page.sections.map((sec, idx) => (
            <div key={idx} className="rounded-xl border border-ln/70 bg-s2/40 p-3.5">
              <h4 className="text-xs font-semibold text-tx mb-1 flex items-center gap-1.5">
                <span className="h-1.5 w-1.5 rounded-full" style={{ background: page.color }} />
                {sec.heading}
              </h4>
              <p className="text-xs text-mu leading-relaxed">{sec.text}</p>
            </div>
          ))}
        </div>

        <div className="mt-5 flex justify-end border-t border-ln/60 pt-3">
          <button
            onClick={closeExplain}
            className="rounded-lg bg-obs px-4 py-1.5 text-xs font-bold text-[#06201c] transition hover:bg-obs/90 shadow-md shadow-obs/20"
          >
            Got it
          </button>
        </div>
      </div>
    </div>
  )
}
