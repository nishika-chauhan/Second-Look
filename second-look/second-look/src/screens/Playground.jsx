import { useRobot } from '../RobotContext.jsx'
import { L, PATH, OBJ, pc } from '../lib/constants.js'
import Scene from '../components/Scene.jsx'
import { Panel, H, Muted, Banner, ObjectChips, ScenarioChips, Controls } from '../components/ui.jsx'

export default function Playground() {
  const { s } = useRobot()
  const O = OBJ[s.obj], d = s.decision
  return (
    <>
      <div className="grid gap-4 lg:grid-cols-[1.6fr_1fr]">
        <Panel>
          <h2 className="mb-2 text-[17px] font-semibold">Remembered versus actual</h2>
          <Scene />
          <p className="mt-2.5 text-[13px]"><span className="text-mem">Dashed ring: where the robot remembers it.</span> <span className="text-obs">Solid object: where it really is.</span></p>
          <Muted>Actual location, hidden from the robot: {s.actual ? L[s.actual].n : 'removed from the scene'}</Muted>
        </Panel>
        <Panel>
          <H>Object</H><div className="-mt-1"><ObjectChips /></div>
          <H className="mt-4">Trigger a scenario</H><ScenarioChips />
          <Muted className="mt-2">Picked before Start, a scenario applies from the beginning. Picked mid-task, it changes the world right then.</Muted>
          <Controls /><Banner outcome={s.outcome} />
        </Panel>
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <Panel style={{ borderTop: '3px solid var(--mem)' }}><H>What it remembered</H><p>{O} last seen on {L[s.last].n}. Confidence there: {pc(s.beliefs[s.last])}.</p></Panel>
        <Panel style={{ borderTop: '3px solid var(--obs)' }}><H>What it observes</H><p>{s.obs ? s.obs.text : 'Nothing observed yet.'}</p></Panel>
        <Panel style={{ borderTop: '3px solid var(--acc)' }}><H>What it decides</H><p>{d ? <><b>{PATH[d.path][0]}.</b> {d.text}</> : 'Waiting for a task.'}</p></Panel>
      </div>
      <div className="grid gap-3 lg:grid-cols-4">
        {Object.entries(PATH).map(([k, [n, t]]) => (
          <div key={k} className={`rounded-[10px] border bg-s1 p-3 ${d?.path === k ? 'border-acc opacity-100 ring-1 ring-acc' : 'border-ln opacity-55'}`}>
            <b>{n}</b><Muted>{t}</Muted>
          </div>
        ))}
      </div>
    </>
  )
}
