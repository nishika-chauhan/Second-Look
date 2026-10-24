import { Play, Pause, RotateCcw } from 'lucide-react'
import { useRobot } from '../RobotContext.jsx'
import { OBJ, SCN } from '../lib/constants.js'

export const Panel = ({ className = '', style, children }) => (
  <div className={`min-w-0 rounded-[10px] border border-ln bg-s1 p-4 ${className}`} style={style}>{children}</div>
)
export const H = ({ children, className = '' }) => <h3 className={`mb-2 text-[15px] font-semibold ${className}`}>{children}</h3>
export const Muted = ({ children, className = '' }) => <p className={`text-[13px] text-mu ${className}`}>{children}</p>

export const Chip = ({ on, className = '', ...p }) => (
  <button className={`rounded-full border px-3 py-1.5 text-sm disabled:cursor-not-allowed disabled:opacity-40 ${on ? 'border-obs text-obs' : 'border-ln bg-s2 text-mu'} ${className}`} {...p} />
)
export const Btn = ({ primary, icon: Icon, children, ...p }) => (
  <button className={`inline-flex items-center gap-2 rounded-lg border px-3.5 py-2 disabled:cursor-not-allowed disabled:opacity-40 ${primary ? 'border-obs bg-obs font-semibold text-[#06201c]' : 'border-ln bg-s2 text-tx'}`} {...p}>
    {Icon && <Icon size={16} aria-hidden />}{children}
  </button>
)
export const Banner = ({ outcome }) =>
  outcome ? <div className={`mt-2.5 rounded-[10px] border px-4 py-3 ${outcome.ok ? 'border-ok text-ok' : 'border-bad text-bad'}`}>{outcome.text}</div> : null

export function ObjectChips() {
  const { s, a } = useRobot()
  return <div className="mt-3 flex flex-wrap gap-2">{Object.entries(OBJ).map(([k, n]) => <Chip key={k} on={s.obj === k} disabled={s.running} onClick={() => a.setObj(k)}>{n}</Chip>)}</div>
}
export function ScenarioChips() {
  const { s, a } = useRobot()
  return <div className="flex flex-wrap gap-2">{Object.entries(SCN).map(([k, n]) => <Chip key={k} on={s.scn === k} onClick={() => a.scenario(k)}>{n}</Chip>)}</div>
}
export function Controls() {
  const { s, a } = useRobot()
  return (
    <div className="mt-3 flex flex-wrap gap-2">
      <Btn primary icon={Play} onClick={a.start} disabled={s.running}>Start Task</Btn>
      <Btn icon={Pause} onClick={a.pause} disabled={!s.running}>{s.paused ? 'Resume' : 'Pause'}</Btn>
      <Btn icon={RotateCcw} onClick={a.reset}>Reset</Btn>
    </div>
  )
}
export function LogList() {
  const { s } = useRobot()
  return (
    <ul className="max-h-72 space-y-1.5 overflow-auto text-[13.5px]">
      {s.log.length ? s.log.map((x, i) => <li key={i} className="border-l-2 border-ln py-1 pl-2.5"><span className="text-mu">{x.time.toFixed(1)}s</span> {x.text}</li>)
        : <li className="border-l-2 border-ln py-1 pl-2.5 text-mu">Actions appear here as the robot works.</li>}
    </ul>
  )
}
