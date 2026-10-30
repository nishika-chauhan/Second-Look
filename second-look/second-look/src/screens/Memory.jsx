import { useRobot } from '../RobotContext.jsx'
import { L, PATH, OBJ, best, pc } from '../lib/constants.js'
import { Panel, H, Muted } from '../components/ui.jsx'
import InfoTooltip from '../components/guidance/InfoTooltip.jsx'
import ProcessingStatus from '../components/guidance/ProcessingStatus.jsx'

const edge = { obs: 'var(--obs)', bad: 'var(--bad)', mem: 'var(--mem)' }

export default function Memory() {
  const { s } = useRobot()
  const o = OBJ[s.obj].toLowerCase(), bl = best(s.beliefs), d = s.decision
  const timeline = [...s.timeline, { k: 'mem', text: `Earlier: ${o} seen on Table A (stored memory).` }]

  return (
    <div className="space-y-3">
      <div data-tour="memory-cards" className="grid gap-3 lg:grid-cols-3">
        <Panel style={{ borderTop: '3px solid var(--mem)' }} className="p-3.5">
          <div className="flex items-center justify-between">
            <Muted>Last-known location</Muted>
            <InfoTooltip
              title="Prior Memory"
              body="Historical coordinate stored in the warehouse database before task initiation."
            />
          </div>
          <h2 className="text-[16px] font-semibold text-tx mt-0.5">{L[s.last].n}</h2>
        </Panel>

        <Panel style={{ borderTop: '3px solid var(--obs)' }} className="p-3.5">
          <div className="flex items-center justify-between">
            <Muted>Currently detected</Muted>
            <InfoTooltip
              title="Live Visual Sensor Feedback"
              body="Ground-truth camera reading from the robot's overhead scanner upon arrival at a workstation."
            />
          </div>
          <h2 className="text-[16px] font-semibold text-tx mt-0.5">
            {s.obs ? (s.obs.seen ? L[s.obs.loc].n : `Not on ${L[s.obs.loc].n}`) : 'No observation yet'}
          </h2>
        </Panel>

        <Panel style={{ borderTop: '3px solid var(--acc)' }} className="p-3.5">
          <div className="flex items-center justify-between">
            <Muted>Most likely location</Muted>
            <InfoTooltip
              title="Posterior Distribution Mode"
              body="Highest-probability station calculated by fusing historical priors with real-time sensory evidence."
            />
          </div>
          <h2 className="text-[16px] font-semibold text-tx mt-0.5">{L[bl].n}, {pc(s.beliefs[bl])}</h2>
        </Panel>
      </div>

      <div className="grid gap-3 lg:grid-cols-[1.6fr_1fr]">
        <Panel data-tour="belief-bars" className="p-3.5">
          <div className="flex items-center justify-between mb-2">
            <H className="mb-0 text-xs">Where the robot thinks the {o} is</H>
            <InfoTooltip
              title="Bayesian Belief Updating"
              body="Probability mass is distributed across known stations (A, B, C) and uncertainty (U). Missing an item at Table A drops its confidence from 92% to 2% and redistributes the remainder."
            />
          </div>
          {['A', 'B', 'C', 'U'].map((k) => (
            <div key={k} className="my-2 grid grid-cols-[84px_1fr_44px] items-center gap-2">
              <span className="text-xs font-medium text-tx">{k === 'U' ? 'Out of view' : L[k].n}</span>
              <div className="h-1.5 overflow-hidden rounded bg-s2">
                <div
                  className="h-full bg-mem transition-all duration-500"
                  style={{ width: pc(s.beliefs[k]) }}
                />
              </div>
              <b className="text-right font-mono text-xs font-semibold text-tx">{pc(s.beliefs[k])}</b>
            </div>
          ))}

          <div data-tour="evidence-stream" className="mt-4 border-t border-ln/60 pt-2.5">
            <div className="flex items-center justify-between mb-1">
              <H className="mb-0 text-xs">Evidence updates</H>
              <InfoTooltip
                title="Reasoning Chain"
                body="Step-by-step mathematical updates showing how sensor observations transform the belief distribution."
              />
            </div>
            <ul className="max-h-60 space-y-1 overflow-auto text-[12.5px]">
              {s.evidence.length ? (
                s.evidence.map((x, i) => (
                  <li key={i} className="border-l-2 border-mem py-0.5 pl-2 text-tx/90">
                    {x}
                  </li>
                ))
              ) : (
                <li className="border-l-2 border-ln py-0.5 pl-2 text-mu">
                  Start a task to see how evidence updates the belief.
                </li>
              )}
            </ul>
          </div>
        </Panel>

        <Panel data-tour="decision-card" className="p-3.5 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <H className="mb-0 text-xs">Next action</H>
              <InfoTooltip
                title="AI Recovery Policy"
                body="NVIDIA Nemotron and Bayesian planner select the next optimal action: Trust Memory, Search Elsewhere, Retry Grasp, or Request Help."
              />
            </div>
            {d ? (
              <div className="rounded-lg border border-acc/40 bg-acc/10 p-2.5 text-xs leading-relaxed text-tx">
                <strong className="text-acc">{PATH[d.path][0]}.</strong> {d.text}
              </div>
            ) : (
              <p className="text-xs text-mu">No decision yet. Start a task from the Robot Workstation.</p>
            )}

            <div className="mt-4 border-t border-ln/60 pt-2.5">
              <div className="flex items-center justify-between mb-1">
                <H className="mb-0 text-xs">Memory timeline</H>
                <InfoTooltip
                  title="Episodic Memory Trail"
                  body="Longer-horizon history recording what was observed in previous warehouse shifts."
                />
              </div>
              <ul className="max-h-60 space-y-1 overflow-auto text-[12.5px]">
                {timeline.map((x, i) => (
                  <li key={i} className="border-l-2 py-0.5 pl-2 text-tx/90" style={{ borderColor: edge[x.k] || 'var(--mem)' }}>
                    {x.text}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </Panel>
      </div>

      <ProcessingStatus />
    </div>
  )
}
