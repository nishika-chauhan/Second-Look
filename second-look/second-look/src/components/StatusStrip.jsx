import { useRobot } from '../RobotContext.jsx'
import { L, ST, best, pc } from '../lib/constants.js'
import InfoTooltip from './guidance/InfoTooltip.jsx'

export default function StatusStrip() {
  const { s } = useRobot()
  const bl = best(s.beliefs), idle = !s.running && !s.log.length, d = s.decision?.path
  const rl = d === 'search' ? 'Searching elsewhere' : d === 'retry' ? 'Retrying' : d === 'help' ? 'Help requested' : 'Standby'
  const col = { completed: 'var(--ok)', failed: 'var(--bad)', idle: 'var(--mu)' }[s.status] || 'var(--obs)'

  const cells = [
    {
      label: 'Current Task',
      value: `Retrieve ${{ cup: 'Cup', bottle: 'Bottle', box: 'Box' }[s.obj]}`,
      sub: s.msg,
      tip: 'task',
    },
    {
      label: 'Robot State',
      value: (
        <>
          <i className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: col }} />
          {s.paused ? 'Paused' : ST[s.status]}
        </>
      ),
      sub: idle ? 'Awaiting command' : s.msg,
      tip: 'robotState',
    },
    {
      label: 'Memory Confidence',
      value: pc(s.beliefs[bl]),
      sub: idle ? 'Prior distribution' : `Best match: ${L[bl].n}`,
      tip: 'memoryConfidence',
    },
    {
      label: 'Recovery Status',
      value: rl,
      sub: rl === 'Standby' ? 'No recovery needed' : s.running ? 'Recovery active' : 'Last recovery action',
      tip: 'recoveryStatus',
    },
  ]

  return (
    <section
      aria-label="Status"
      data-tour="status-strip"
      className="grid grid-cols-2 rounded-xl border border-ln bg-s1 lg:grid-cols-4 shadow-xs"
    >
      {cells.map((cell, i) => (
        <div
          key={cell.label}
          className={`min-w-0 px-3.5 py-2 ${i % 2 ? 'border-l border-ln' : ''} ${
            i > 1 ? 'border-t border-ln lg:border-t-0' : ''
          } ${i === 2 ? 'lg:border-l lg:border-ln' : ''}`}
        >
          <div className="flex items-center justify-between">
            <p className="text-[11px] text-mu font-medium">{cell.label}</p>
            <InfoTooltip tip={cell.tip} />
          </div>
          <h3 className="my-0.5 flex items-center gap-1.5 text-[16px] font-semibold text-tx leading-tight">
            {cell.value}
          </h3>
          <p className="truncate text-[11px] text-mu">{cell.sub}</p>
        </div>
      ))}
    </section>
  )
}
