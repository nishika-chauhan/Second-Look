import { useRobot } from '../RobotContext.jsx'
import { SCN } from '../lib/constants.js'
import Scene from '../components/Scene.jsx'
import { Panel, H, Muted, Banner, ObjectChips, Controls, LogList } from '../components/ui.jsx'

export default function Workstation() {
  const { s } = useRobot()
  return (
    <div className="grid gap-4 lg:grid-cols-[1.6fr_1fr]">
      <Panel>
        <h2 className="mb-2 text-[17px] font-semibold">Workspace view</h2>
        <Scene /><ObjectChips /><Controls />
        <Muted className="mt-2.5">Scenario: {SCN[s.scn]}. Change it in the Recovery Playground.</Muted>
      </Panel>
      <Panel>
        <H>Task progress</H>
        <div className="h-2 overflow-hidden rounded bg-s2"><div className="h-full bg-obs transition-all" style={{ width: `${s.progress}%` }} /></div>
        <p className="mt-2.5">{s.msg}</p>
        <Banner outcome={s.outcome} />
        <H className="mt-4">Event log</H>
        <LogList />
      </Panel>
    </div>
  )
}
