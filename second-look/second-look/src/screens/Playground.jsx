import { useState } from 'react'
import { Play, Sparkles, ArrowRight, CheckCircle2, RotateCcw } from 'lucide-react'
import { useRobot } from '../RobotContext.jsx'
import { L, PATH, OBJ, SCN, pc } from '../lib/constants.js'
import Scene from '../components/Scene.jsx'
import { Panel, H, Muted, Banner, ObjectChips, ScenarioChips, Controls, Btn } from '../components/ui.jsx'
import { PRELOADED_EXAMPLES } from '../config/guidance/examples.js'
import InfoTooltip from '../components/guidance/InfoTooltip.jsx'
import ProcessingStatus from '../components/guidance/ProcessingStatus.jsx'

export default function Playground() {
  const { s, a } = useRobot()
  const [selectedExample, setSelectedExample] = useState(PRELOADED_EXAMPLES[1]) // Default to Moved
  const O = OBJ[s.obj], d = s.decision

  const loadExample = (ex) => {
    setSelectedExample(ex)
    a.setObj(ex.obj)
    a.scenario(ex.scenario)
  }

  const runExample = () => {
    if (s.running) return
    a.start()
  }

  return (
    <>
      {/* Preloaded Scenario Cards Header */}
      <Panel data-tour="playground-examples" className="border-obs/30 bg-gradient-to-r from-s1 via-s1 to-s2/60">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between border-b border-ln/60 pb-3 mb-3">
          <div>
            <div className="flex items-center gap-2">
              <Sparkles size={16} className="text-obs" />
              <h3 className="text-sm font-bold text-tx">Try a Preconfigured Scenario</h3>
              <InfoTooltip
                title="Preloaded Recovery Demonstrations"
                body="One-click scenarios designed to showcase distinct recovery behaviors under realistic disturbance conditions."
              />
            </div>
            <p className="text-xs text-mu">
              Explore how Second Look handles location uncertainty, unexpected displacement, and physical slips.
            </p>
          </div>
          {s.outcome && (
            <button
              onClick={a.reset}
              className="flex items-center gap-1.5 self-start rounded-lg border border-ln bg-s2 px-3 py-1.5 text-xs font-medium text-tx transition hover:bg-s2/80"
            >
              <RotateCcw size={13} />
              Reset Playground
            </button>
          )}
        </div>

        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {PRELOADED_EXAMPLES.map((ex) => {
            const isSelected = selectedExample?.id === ex.id && s.scn === ex.scenario
            return (
              <div
                key={ex.id}
                onClick={() => loadExample(ex)}
                className={`cursor-pointer rounded-xl border p-3.5 transition flex flex-col justify-between ${
                  isSelected
                    ? 'border-obs bg-s2/90 shadow-md shadow-obs/15 ring-1 ring-obs'
                    : 'border-ln/70 bg-s2/30 hover:border-ln hover:bg-s2/60'
                }`}
              >
                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <span
                      className="rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider"
                      style={{ background: `${ex.badgeCol}20`, color: ex.badgeCol }}
                    >
                      {ex.badge}
                    </span>
                    {isSelected && <CheckCircle2 size={14} className="text-obs" />}
                  </div>
                  <h4 className="text-xs font-bold text-tx">{ex.title}</h4>
                  <p className="mt-1 text-[11px] leading-relaxed text-mu">{ex.desc}</p>
                </div>

                <div className="mt-3 pt-2 border-t border-ln/40 flex items-center justify-between text-[11px]">
                  <span className="text-mu">Expected: <strong className="text-tx">{ex.expectedDecision}</strong></span>
                  <span className="font-semibold text-obs flex items-center gap-0.5">
                    {isSelected ? 'Loaded' : 'Select'}
                    <ArrowRight size={11} />
                  </span>
                </div>
              </div>
            )
          })}
        </div>

        {/* Selected Example Detail Preview & Instant Run */}
        {selectedExample && (
          <div className="mt-4 rounded-xl border border-ln/80 bg-s2/50 p-4">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-ln/50 pb-3 mb-3">
              <div>
                <span className="text-[10.5px] uppercase font-bold tracking-wider text-obs">
                  Scenario Focus: {selectedExample.title}
                </span>
                <p className="text-xs font-semibold text-tx mt-0.5">
                  Before: <span className="font-normal text-mu">{selectedExample.beforeState}</span> → Expected After: <span className="font-normal text-tx">{selectedExample.afterState}</span>
                </p>
              </div>
              <Btn
                primary
                icon={Play}
                onClick={runExample}
                disabled={s.running}
                className="self-start sm:self-auto shadow-md shadow-obs/20"
              >
                {s.running ? 'Running Scenario...' : 'Run This Example Now'}
              </Btn>
            </div>

            <div className="grid gap-3 sm:grid-cols-2 text-xs">
              <div>
                <span className="font-semibold text-tx flex items-center gap-1.5 mb-1.5">
                  <span className="h-1.5 w-1.5 rounded-full bg-obs" />
                  What you will observe:
                </span>
                <ul className="space-y-1 text-mu text-[11.5px]">
                  {selectedExample.whatToObserve.map((pt, i) => (
                    <li key={i} className="flex items-start gap-1.5">
                      <span className="text-obs font-bold">›</span>
                      <span>{pt}</span>
                    </li>
                  ))}
                </ul>
              </div>
              <div className="rounded-lg border border-ln/50 bg-s1/60 p-3 flex flex-col justify-between">
                <div>
                  <span className="font-semibold text-tx text-[11.5px] block mb-1">Key Takeaway</span>
                  <p className="text-mu text-[11px] leading-relaxed">{selectedExample.takeaway}</p>
                </div>
                <div className="mt-2 text-[10.5px] text-obs/90 font-mono">
                  Ground truth: {s.actual ? L[s.actual].n : 'Missing from workspace'}
                </div>
              </div>
            </div>
          </div>
        )}
      </Panel>

      {/* Main Interactive Playground Scene & Controls */}
      <div className="grid gap-4 lg:grid-cols-[1.6fr_1fr]">
        <Panel data-tour="playground-scene">
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-[17px] font-semibold">Remembered versus actual</h2>
            <InfoTooltip
              title="Perceptual Grounding"
              body="Dashed amber ring indicates prior belief stored in memory. Solid teal object indicates ground-truth physical coordinate in the simulation."
            />
          </div>
          <Scene />
          <p className="mt-2.5 text-[13px]">
            <span className="text-mem font-medium">Dashed ring: where the robot remembers it.</span>{' '}
            <span className="text-obs font-medium">Solid object: where it really is.</span>
          </p>
          <Muted>
            Actual location, hidden from the robot until scanned: {s.actual ? L[s.actual].n : 'removed from the scene'}
          </Muted>
        </Panel>

        <Panel data-tour="playground-scenarios">
          <div className="flex items-center justify-between">
            <H>Select SKU Object</H>
            <InfoTooltip
              title="Target SKU"
              body="Switch between standard warehouse items (Cup, Bottle, Box) with varying dimensions and grasp characteristics."
            />
          </div>
          <div className="-mt-1"><ObjectChips /></div>

          <div className="flex items-center justify-between mt-4">
            <H>Manual Scenario Override</H>
            <InfoTooltip
              title="Disturbance Trigger"
              body="Apply a disturbance before execution or mid-task to simulate real-time warehouse events."
            />
          </div>
          <ScenarioChips />
          <Muted className="mt-2">
            Picked before Start, a scenario applies from the beginning. Picked mid-task, it changes the world right then.
          </Muted>
          <Controls />
          <Banner outcome={s.outcome} />
        </Panel>
      </div>

      {/* AI Processing Status Pipeline */}
      <ProcessingStatus />

      {/* Triad of State: Remembered vs Observed vs Decided */}
      <div className="grid gap-4 lg:grid-cols-3">
        <Panel style={{ borderTop: '3px solid var(--mem)' }}>
          <div className="flex items-center justify-between mb-1">
            <H className="mb-0">What it remembered</H>
            <InfoTooltip
              title="Stored Memory Prior"
              body="Initial location belief established during inventory storage or previous sighting."
            />
          </div>
          <p className="text-xs text-tx/90 mt-2">
            {O} last seen on {L[s.last].n}. Confidence there: <strong className="text-mem">{pc(s.beliefs[s.last])}</strong>.
          </p>
        </Panel>

        <Panel style={{ borderTop: '3px solid var(--obs)' }}>
          <div className="flex items-center justify-between mb-1">
            <H className="mb-0">What it observes</H>
            <InfoTooltip
              title="Camera Observation"
              body="Sensory detection from gantry overhead scanner upon arrival at a target workstation."
            />
          </div>
          <p className="text-xs text-tx/90 mt-2">
            {s.obs ? s.obs.text : 'Nothing observed yet.'}
          </p>
        </Panel>

        <Panel style={{ borderTop: '3px solid var(--acc)' }}>
          <div className="flex items-center justify-between mb-1">
            <H className="mb-0">What it decides</H>
            <InfoTooltip
              title="Decision Engine Directive"
              body="Active recovery policy generated via NVIDIA Nemotron and Bayesian planner."
            />
          </div>
          <p className="text-xs text-tx/90 mt-2">
            {d ? <><b>{PATH[d.path][0]}.</b> {d.text}</> : 'Waiting for a task.'}
          </p>
        </Panel>
      </div>

      {/* Four Recovery Paths Highlight */}
      <div data-tour="recovery-paths" className="grid gap-3 lg:grid-cols-4">
        {Object.entries(PATH).map(([k, [n, t]]) => {
          const isActive = d?.path === k
          return (
            <div
              key={k}
              className={`rounded-[10px] border p-3 transition ${
                isActive
                  ? 'border-acc bg-s2 text-tx opacity-100 ring-2 ring-acc/50 shadow-md shadow-acc/10'
                  : 'border-ln bg-s1 opacity-55 hover:opacity-80'
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <b className="text-xs text-tx">{n}</b>
                {isActive && (
                  <span className="rounded-full bg-acc/20 px-1.5 py-0.5 text-[9px] font-bold text-acc uppercase">
                    Active
                  </span>
                )}
              </div>
              <Muted>{t}</Muted>
            </div>
          )
        })}
      </div>
    </>
  )
}
