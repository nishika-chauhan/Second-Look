import { LayoutDashboard, Bot, Brain, FlaskConical, BarChart3, Cpu, HelpCircle } from 'lucide-react'
import { useRobot, LIVE } from '../RobotContext.jsx'
import { MODE } from '../lib/constants.js'
import { Chip, Muted } from './ui.jsx'
import ConnectionStatus from './guidance/ConnectionStatus.jsx'
import { useGuidance } from '../context/GuidanceContext.jsx'

export const NAV = [
  ['overview', 'Overview', LayoutDashboard],
  ['workstation', 'Robot Workstation', Bot],
  ['memory', 'Memory & Decisions', Brain],
  ['playground', 'Recovery Playground', FlaskConical],
  ['analytics', 'Results & Analytics', BarChart3],
]

export default function Sidebar({ view, setView }) {
  const { s, a } = useRobot()
  const { openHelp, openArchModal } = useGuidance()

  return (
    <aside className="flex flex-col gap-2 border-b border-ln bg-s1 p-4 lg:sticky lg:top-0 lg:h-screen lg:overflow-auto lg:border-b-0 lg:border-r lg:px-4 lg:py-5">
      <div>
        <div className="flex items-center gap-1.5 mb-1">
          <span className="h-2 w-2 rounded-full bg-obs" />
          <span className="text-[10px] font-bold uppercase tracking-wider text-obs">
            Warehouse Intelligence
          </span>
        </div>
        <h1 className="text-[22px] font-bold tracking-tight text-tx">Second Look</h1>
        <Muted className="text-xs">Intelligent robot retrieval & failure recovery</Muted>
      </div>

      <div className="my-2">
        <ConnectionStatus />
      </div>

      <nav data-tour="sidebar-nav" className="flex gap-1 overflow-x-auto lg:flex-col py-1">
        {NAV.map(([k, n, Icon]) => (
          <button
            key={k}
            onClick={() => setView(k)}
            aria-current={view === k ? 'page' : undefined}
            className={`flex items-center gap-2.5 whitespace-nowrap rounded-lg px-3 py-2 text-left text-xs font-medium transition ${
              view === k
                ? 'bg-s2 text-tx shadow-[inset_3px_0_var(--mem)] font-semibold'
                : 'text-mu hover:bg-s2/50 hover:text-tx'
            }`}
          >
            <Icon size={16} aria-hidden className={view === k ? 'text-obs' : 'text-mu'} />
            {n}
          </button>
        ))}
      </nav>

      <div className="hidden flex-1 lg:block" />

      <div className="mt-2 space-y-2 border-t border-ln/60 pt-3">
        {!LIVE && (
          <div data-tour="robot-mode">
            <Muted className="mb-1 text-[11px] font-semibold uppercase tracking-wider">
              Operating Mode
            </Muted>
            <div className="mb-2 flex flex-wrap gap-1.5">
              {Object.entries(MODE).map(([k, n]) => (
                <Chip
                  key={k}
                  on={s.mode === k}
                  disabled={s.running}
                  onClick={() => a.setMode(k)}
                  className="text-xs px-2.5 py-1"
                >
                  {n}
                </Chip>
              ))}
            </div>
          </div>
        )}

        <div className="space-y-1">
          <button
            onClick={openArchModal}
            className="flex w-full items-center gap-2 rounded-lg border border-ln/70 bg-s2/40 px-2.5 py-1.5 text-left text-[11px] text-mu transition hover:border-obs hover:text-tx"
            data-tour="arch-button"
          >
            <Cpu size={13} className="text-obs flex-none" />
            <span className="truncate">Nebius + NVIDIA Architecture</span>
          </button>

          <button
            onClick={openHelp}
            className="flex w-full items-center gap-2 rounded-lg border border-ln/70 bg-s2/40 px-2.5 py-1.5 text-left text-[11px] text-mu transition hover:border-obs hover:text-tx"
            data-tour="sidebar-help"
          >
            <HelpCircle size={13} className="text-mem flex-none" />
            <span className="truncate">Help & Guided Tour</span>
          </button>
        </div>

        <p className="text-[10px] text-mu/80 leading-relaxed pt-1">
          Developed for the Nebius × NVIDIA AI Hackathon. Physics-grounded simulation & Bayesian reasoning.
        </p>
      </div>
    </aside>
  )
}
