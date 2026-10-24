import { useRobot } from '../RobotContext.jsx'
import { L } from '../lib/constants.js'

const Shape = ({ o, x }) =>
  o === 'cup' ? <path d={`M${x - 9} 130h18l-3 20h-12z`} />
  : o === 'bottle' ? <path d={`M${x - 4} 118h8v8l5 7v17h-18v-17l5-7z`} />
  : <rect x={x - 13} y={132} width={26} height={18} rx={2} />

/** Dashed amber ring = what the robot remembers. Solid teal object = where it really is. */
export default function Scene() {
  const { s } = useRobot()
  const done = s.status === 'completed'
  const rx = s.at === 'home' ? 300 : L[s.at].x
  const g = L[s.last].x
  return (
    <svg viewBox="0 0 600 290" role="img" aria-label="Robot workspace with Table A, Table B and Shelf C" className="block h-auto w-full rounded-lg border border-ln bg-bg">
      {Object.values(L).map((l) => (
        <g key={l.n}>
          <rect x={l.x - 70} y={150} width={140} height={12} rx={4} fill="var(--s2)" stroke="var(--ln)" />
          <path d={`M${l.x - 58} 162v52M${l.x + 58} 162v52`} stroke="var(--ln)" strokeWidth={4} />
          <text x={l.x} y={192} textAnchor="middle" fill="var(--mu)" fontSize={13}>{l.n}</text>
        </g>
      ))}
      <circle cx={g} cy={134} r={28} fill="none" stroke="var(--mem)" strokeWidth={2} strokeDasharray="5 4" />
      <text x={g} y={96} textAnchor="middle" fill="var(--mem)" fontSize={12}>remembered</text>
      {s.actual && !done && <g fill="var(--obs)"><Shape o={s.obj} x={L[s.actual].x} /></g>}
      {!s.actual && <text x={300} y={50} textAnchor="middle" fill="var(--bad)" fontSize={13}>The object has been removed from the scene</text>}
      <g style={{ transform: `translateX(${rx}px)`, transition: 'transform .9s ease-in-out' }}>
        {s.status === 'searching' && <path d="M0 244L-64 152H64z" fill="var(--obs)" opacity={0.14} />}
        <rect x={-26} y={244} width={52} height={26} rx={9} fill="var(--acc)" />
        <circle cy={257} r={5} fill="var(--bg)" />
        {done && <g fill="var(--obs)" transform="translate(0 92)"><Shape o={s.obj} x={0} /></g>}
      </g>
    </svg>
  )
}
