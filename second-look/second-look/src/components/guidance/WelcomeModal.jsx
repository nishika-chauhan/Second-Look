import { Sparkles, Bot, Brain, FlaskConical, BarChart3, X, ArrowRight } from 'lucide-react'
import { useGuidance } from '../../context/GuidanceContext.jsx'

const SECTIONS = [
  {
    icon: Bot,
    title: 'Robot Workstation',
    desc: 'Monitor live gantry crane kinematics, spatial zones (Table A, B, C), and operational pick commands.',
    color: 'var(--obs)',
  },
  {
    icon: Brain,
    title: 'Live Memory & Decisions',
    desc: 'Watch Bayesian belief distributions evolve as cameras confirm or refute object presence.',
    color: 'var(--mem)',
  },
  {
    icon: FlaskConical,
    title: 'Recovery Playground',
    desc: 'Trigger real disturbances: shifted items, missing inventory, and mechanical gripper slip.',
    color: 'var(--acc)',
  },
  {
    icon: BarChart3,
    title: 'Results & Analytics',
    desc: 'Compare recovery success rates and search times against fixed-memory baselines.',
    color: 'var(--ok)',
  },
]

export default function WelcomeModal() {
  const { welcomeOpen, handleDismissWelcome } = useGuidance()

  if (!welcomeOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="relative w-full max-w-2xl rounded-2xl border border-ln bg-s1 p-6 shadow-2xl shadow-black/60 sm:p-8">
        <button
          onClick={() => handleDismissWelcome(false)}
          className="absolute right-4 top-4 rounded-lg p-2 text-mu transition hover:bg-s2 hover:text-tx"
          aria-label="Close welcome"
        >
          <X size={20} />
        </button>

        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-obs/15 text-obs">
            <Sparkles size={22} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="rounded-full border border-obs/30 bg-obs/10 px-2 py-0.5 text-[11px] font-medium uppercase tracking-wider text-obs">
                Nebius × NVIDIA Hackathon
              </span>
            </div>
            <h2 className="text-xl font-bold tracking-tight sm:text-2xl">
              Welcome to Second Look
            </h2>
          </div>
        </div>

        <p className="mt-2 text-sm font-medium text-tx/90 sm:text-base">
          An intelligent warehouse system that remembers, reasons, and recovers when the unexpected happens.
        </p>

        <p className="mt-1 text-xs text-mu sm:text-sm">
          Explore how AI-powered warehouse intelligence uses spatial memory and NVIDIA Nemotron reasoning to handle uncertain locations and recover from operational disruptions.
        </p>

        <div className="mt-5 grid gap-3 sm:grid-cols-2">
          {SECTIONS.map((sec) => {
            const Icon = sec.icon
            return (
              <div
                key={sec.title}
                className="flex items-start gap-3 rounded-xl border border-ln/80 bg-s2/60 p-3.5 transition hover:border-ln"
              >
                <div
                  className="flex h-8 w-8 flex-none items-center justify-center rounded-lg"
                  style={{ background: `${sec.color}20`, color: sec.color }}
                >
                  <Icon size={17} />
                </div>
                <div className="min-w-0">
                  <h4 className="text-xs font-semibold text-tx">{sec.title}</h4>
                  <p className="mt-0.5 text-[11px] leading-relaxed text-mu">{sec.desc}</p>
                </div>
              </div>
            )
          })}
        </div>

        <div className="mt-6 flex flex-col-reverse gap-2.5 sm:flex-row sm:items-center sm:justify-between">
          <button
            onClick={() => handleDismissWelcome(false)}
            className="text-center text-xs font-medium text-mu transition hover:text-tx py-2"
          >
            Skip Introduction & Explore Freely
          </button>
          <div className="flex gap-2">
            <button
              onClick={() => handleDismissWelcome(false)}
              className="flex-1 rounded-lg border border-ln bg-s2 px-4 py-2.5 text-xs font-semibold text-tx transition hover:bg-s2/80 sm:flex-none"
            >
              Explore Workspace
            </button>
            <button
              onClick={() => handleDismissWelcome(true)}
              className="flex flex-1 items-center justify-center gap-2 rounded-lg bg-obs px-5 py-2.5 text-xs font-bold text-[#06201c] shadow-lg shadow-obs/20 transition hover:bg-obs/90 sm:flex-none"
            >
              Start Guided Tour
              <ArrowRight size={15} />
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
