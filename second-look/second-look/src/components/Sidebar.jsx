import { LayoutDashboard, Bot, Brain, FlaskConical, BarChart3 } from 'lucide-react'
import { useRobot, LIVE } from '../RobotContext.jsx'
import { MODE } from '../lib/constants.js'
import { Chip, Muted } from './ui.jsx'

export const NAV = [
  ['overview', 'Overview', LayoutDashboard], ['workstation', 'Robot Workstation', Bot], ['memory', 'Memory & Decisions', Brain],
  ['playground', 'Recovery Playground', FlaskConical], ['analytics', 'Results & Analytics', BarChart3],
]
const CONN = { simulated: ['var(--ok)', 'System Online', 'Simulated event stream'], live: ['var(--ok)', 'System Online', 'Backend stream connected'],
  connecting: ['var(--mem)', 'Connecting', 'Reaching the backend'], offline: ['var(--bad)', 'Offline', 'Reconnecting to the backend'] }

export default function Sidebar({ view, setView }) {
  const { s, a } = useRobot()
  const [c, t1, t2] = CONN[s.conn]
  return (
    <aside className="flex flex-col gap-1.5 border-b border-ln bg-s1 p-4 lg:sticky lg:top-0 lg:h-screen lg:overflow-auto lg:border-b-0 lg:border-r lg:px-3.5 lg:py-5">
      <div><h1 className="text-[22px] font-bold tracking-tight">Second Look</h1><Muted>Intelligent robot retrieval and recovery</Muted></div>
      <div className="my-3 flex items-center gap-2 text-[13px]" role="status">
        <i className="h-2.5 w-2.5 flex-none rounded-full" style={{ background: c }} />
        <span>{t1}<br /><span className="text-mu">{t2}</span></span>
      </div>
      <nav className="flex gap-1 overflow-x-auto lg:flex-col">
        {NAV.map(([k, n, Icon]) => (
          <button key={k} onClick={() => setView(k)} aria-current={view === k ? 'page' : undefined}
            className={`flex items-center gap-2.5 whitespace-nowrap rounded-lg px-3 py-2 text-left ${view === k ? 'bg-s2 text-tx shadow-[inset_3px_0_var(--mem)]' : 'text-mu hover:text-tx'}`}>
            <Icon size={17} aria-hidden />{n}
          </button>
        ))}
      </nav>
      <div className="hidden flex-1 lg:block" />
      {!LIVE && (<>
        <Muted className="mt-3">Robot mode</Muted>
        <div className="mb-2.5 flex flex-wrap gap-2">{Object.entries(MODE).map(([k, n]) => <Chip key={k} on={s.mode === k} disabled={s.running} onClick={() => a.setMode(k)}>{n}</Chip>)}</div>
      </>)}
      <Muted>Conceptual mockup. Sample values only, not live robot data.</Muted>
    </aside>
  )
}
