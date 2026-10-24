import { useRobot } from '../RobotContext.jsx'
import { L, ST, best, pc } from '../lib/constants.js'

export default function StatusStrip() {
  const { s } = useRobot()
  const bl = best(s.beliefs), idle = !s.running && !s.log.length, d = s.decision?.path
  const rl = d === 'search' ? 'Searching elsewhere' : d === 'retry' ? 'Retrying' : d === 'help' ? 'Help requested' : 'Standby'
  const col = { completed: 'var(--ok)', failed: 'var(--bad)', idle: 'var(--mu)' }[s.status] || 'var(--obs)'
  const cells = [
    ['Current Task', `Retrieve ${{ cup: 'Cup', bottle: 'Bottle', box: 'Box' }[s.obj]}`, s.msg],
    ['Robot State', <><i className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: col }} />{s.paused ? 'Paused' : ST[s.status]}</>, idle ? 'Awaiting command' : s.msg],
    ['Memory Confidence', pc(s.beliefs[bl]), idle ? 'Illustrative value' : `Best match: ${L[bl].n}`],
    ['Recovery Status', rl, rl === 'Standby' ? 'No recovery needed' : s.running ? 'Recovery active' : 'Last recovery action'],
  ]
  return (
    <section aria-label="Status" className="grid grid-cols-2 rounded-xl border border-ln bg-s1 lg:grid-cols-4">
      {cells.map(([k, v, sub], i) => (
        <div key={k} className={`min-w-0 px-4 py-3 ${i % 2 ? 'border-l border-ln' : ''} ${i > 1 ? 'border-t border-ln lg:border-t-0' : ''} ${i === 2 ? 'lg:border-l lg:border-ln' : ''}`}>
          <p className="text-[13px] text-mu">{k}</p>
          <h3 className="my-0.5 flex items-center gap-2 text-[19px] font-semibold">{v}</h3>
          <p className="truncate text-[13px] text-mu">{sub}</p>
        </div>
      ))}
    </section>
  )
}
