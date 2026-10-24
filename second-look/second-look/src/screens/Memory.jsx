import { useRobot } from '../RobotContext.jsx'
import { L, PATH, OBJ, best, pc } from '../lib/constants.js'
import { Panel, H, Muted } from '../components/ui.jsx'

const edge = { obs: 'var(--obs)', bad: 'var(--bad)', mem: 'var(--mem)' }

export default function Memory() {
  const { s } = useRobot()
  const o = OBJ[s.obj].toLowerCase(), bl = best(s.beliefs), d = s.decision
  const timeline = [...s.timeline, { k: 'mem', text: `Earlier: ${o} seen on Table A (stored memory).` }]
  return (
    <>
      <div className="grid gap-4 lg:grid-cols-3">
        <Panel style={{ borderTop: '3px solid var(--mem)' }}><Muted>Last-known location</Muted><h2 className="text-[17px] font-semibold">{L[s.last].n}</h2></Panel>
        <Panel style={{ borderTop: '3px solid var(--obs)' }}><Muted>Currently detected</Muted>
          <h2 className="text-[17px] font-semibold">{s.obs ? (s.obs.seen ? L[s.obs.loc].n : `Not on ${L[s.obs.loc].n}`) : 'No observation yet'}</h2></Panel>
        <Panel><Muted>Most likely location</Muted><h2 className="text-[17px] font-semibold">{L[bl].n}, {pc(s.beliefs[bl])}</h2></Panel>
      </div>
      <div className="grid gap-4 lg:grid-cols-[1.6fr_1fr]">
        <Panel>
          <H>Where the robot thinks the {o} is</H>
          {['A', 'B', 'C', 'U'].map((k) => (
            <div key={k} className="my-2.5 grid grid-cols-[84px_1fr_44px] items-center gap-2.5">
              <span>{k === 'U' ? 'Out of view' : L[k].n}</span>
              <div className="h-2 overflow-hidden rounded bg-s2"><div className="h-full bg-mem transition-all duration-500" style={{ width: pc(s.beliefs[k]) }} /></div>
              <b className="text-right font-semibold">{pc(s.beliefs[k])}</b>
            </div>
          ))}
          <H className="mt-4">Evidence updates</H>
          <ul className="max-h-72 space-y-1.5 overflow-auto text-[13.5px]">
            {s.evidence.length ? s.evidence.map((x, i) => <li key={i} className="border-l-2 border-mem py-1 pl-2.5">{x}</li>)
              : <li className="border-l-2 border-ln py-1 pl-2.5 text-mu">Start a task to see how evidence changes the belief.</li>}
          </ul>
        </Panel>
        <Panel>
          <H>Next action</H>
          {d ? <p><b>{PATH[d.path][0]}.</b> {d.text}</p> : <p className="text-mu">No decision yet. Start a task from the Robot Workstation.</p>}
          <H className="mt-4">Memory timeline</H>
          <ul className="max-h-72 space-y-1.5 overflow-auto text-[13.5px]">
            {timeline.map((x, i) => <li key={i} className="border-l-2 py-1 pl-2.5" style={{ borderColor: edge[x.k] || 'var(--mem)' }}>{x.text}</li>)}
          </ul>
        </Panel>
      </div>
    </>
  )
}
