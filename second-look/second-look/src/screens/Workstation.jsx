import { useRobot } from '../RobotContext.jsx'
import { SCN } from '../lib/constants.js'
import Scene from '../components/Scene.jsx'
import { Panel, H, Muted, Banner, ObjectChips, Controls, LogList } from '../components/ui.jsx'
import InfoTooltip from '../components/guidance/InfoTooltip.jsx'
import ProcessingStatus from '../components/guidance/ProcessingStatus.jsx'

export default function Workstation() {
  const { s } = useRobot()

  return (
    <>
      <div className="grid gap-4 lg:grid-cols-[1.6fr_1fr]">
        <Panel data-tour="workspace-scene">
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-[17px] font-semibold">Workspace view</h2>
            <div className="flex items-center gap-2">
              <span className="rounded-full bg-s2 px-2 py-0.5 text-[11px] font-mono text-mu border border-ln">
                MuJoCo Cartesian Gantry
              </span>
              <InfoTooltip
                title="Cartesian Gantry Simulation"
                body="Visualizes the physical robot workspace. Shows live coordinate tracking, camera scan cones, and real-time end-effector transport."
              />
            </div>
          </div>
          <Scene />
          <div data-tour="task-controls" className="mt-3">
            <div className="flex items-center justify-between">
              <H className="mb-0 text-xs text-mu">Target SKU Selection</H>
              <InfoTooltip
                title="Object Selection"
                body="Choose which item the robot should locate and retrieve from the storage workstations."
              />
            </div>
            <ObjectChips />
            <Controls />
          </div>
          <Muted className="mt-2.5">
            Scenario: <strong className="text-tx">{SCN[s.scn]}</strong>. Test disturbances in the Recovery Playground.
          </Muted>
        </Panel>

        <Panel data-tour="task-progress">
          <div className="flex items-center justify-between">
            <H>Task progress</H>
            <InfoTooltip
              title="Execution Progress"
              body="Tracks real-time task lifecycle: Approach -> Visual Scan -> Decision Validation -> Grasp -> Delivery."
            />
          </div>
          <div className="h-2 overflow-hidden rounded bg-s2">
            <div
              className="h-full bg-obs transition-all duration-300"
              style={{ width: `${s.progress}%` }}
            />
          </div>
          <p className="mt-2.5 text-xs text-tx font-medium">{s.msg}</p>
          <Banner outcome={s.outcome} />

          <div data-tour="event-log">
            <div className="flex items-center justify-between mt-4 mb-1">
              <H className="mb-0">Event log</H>
              <InfoTooltip
                title="Chronological Event Audit"
                body="Timestamped telemetry recording physical movement commands, sensor readings, and recovery trigger activations."
              />
            </div>
            <LogList />
          </div>
        </Panel>
      </div>

      <ProcessingStatus />
    </>
  )
}
