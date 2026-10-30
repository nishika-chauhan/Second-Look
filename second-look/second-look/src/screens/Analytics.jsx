import { Bar, BarChart, CartesianGrid, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { useRobot, LIVE } from '../RobotContext.jsx'
import { MODE, OBJ, SCN, pc, stats } from '../lib/constants.js'
import { Panel, H, Muted, Btn } from '../components/ui.jsx'
import InfoTooltip from '../components/guidance/InfoTooltip.jsx'

function BarCard({ title, k, fmt, max, tip }) {
  const { s } = useRobot()
  const a = stats(s.trials, 'second'), b = stats(s.trials, 'baseline')
  const data = [{ name: MODE.second, value: a[k] }, { name: 'Baseline', value: b[k] }]
  return (
    <Panel className="p-3.5">
      <div className="flex items-center justify-between mb-1">
        <H className="mb-0 text-xs font-semibold">{title}</H>
        {tip && <InfoTooltip tip={tip} />}
      </div>
      <ResponsiveContainer width="100%" height={170}>
        <BarChart data={data} margin={{ top: 16, right: 8, left: -14, bottom: 0 }}>
          <CartesianGrid stroke="#2b3644" vertical={false} />
          <XAxis dataKey="name" stroke="#8d9aac" tickLine={false} fontSize={11} />
          <YAxis stroke="#8d9aac" tickLine={false} axisLine={false} fontSize={11} domain={[0, max || 'auto']} tickFormatter={fmt} />
          <Tooltip cursor={{ fill: '#1f2936' }} contentStyle={{ background: '#171e27', border: '1px solid #2b3644', borderRadius: 8 }} formatter={(v) => fmt(v)} />
          <Bar dataKey="value" radius={[4, 4, 0, 0]} isAnimationActive={false}>
            {data.map((_, i) => <Cell key={i} fill={i ? '#8d9aac' : '#46c4b2'} />)}
            <LabelList dataKey="value" position="top" formatter={fmt} fill="#e7ecf3" fontSize={11} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <Muted className="text-[11px] mt-1">{a.n} Second Look and {b.n} baseline trials</Muted>
    </Panel>
  )
}

export default function Analytics() {
  const { s, a } = useRobot()
  const batch = !LIVE && (
    <Btn primary onClick={a.batch} disabled={s.running || s.fast} className="py-1.5 px-3 text-xs">
      Run 16 simulated trials
    </Btn>
  )

  if (!s.trials.length) {
    return (
      <Panel data-tour="analytics-controls" className="p-4">
        <div className="flex items-center gap-2 mb-1.5">
          <h2 className="text-[16px] font-semibold text-tx">No trials recorded yet</h2>
          <InfoTooltip
            title="Benchmark Dataset"
            body="Trials evaluate both Second Look and a memory-only baseline across randomized SKUs and disturbance conditions."
          />
        </div>
        <p className="text-mu text-xs max-w-[65ch] leading-relaxed">
          Run an individual task in the Robot Workstation or Recovery Playground, or execute an instant batch of 16 simulated trials to evaluate comparative success rates and recovery metrics.
        </p>
        <div className="mt-3.5 flex flex-wrap items-center gap-2.5">
          {batch}
        </div>
      </Panel>
    )
  }

  const causes = {}
  s.trials.filter((x) => !x.ok).forEach((x) => {
    (causes[x.cause] ||= { second: 0, baseline: 0 })[x.mode]++
  })

  return (
    <div className="space-y-3">
      <Panel data-tour="analytics-controls" className="p-3.5">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2.5">
          <div>
            <span className="inline-block rounded-full border border-mem px-2 py-0.2 text-[11px] font-semibold text-mem">
              {LIVE ? 'Live Backend Telemetry' : 'Session Benchmark Dataset (Simulation)'}
            </span>
            <p className="mt-0.5 text-xs text-mu">
              Contrasting Second Look (Bayesian belief + Nemotron recovery) with Baseline (memory-only direct path).
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {batch}
            <Btn onClick={a.clear} className="py-1.5 px-3 text-xs">Clear results</Btn>
          </div>
        </div>
      </Panel>

      <div data-tour="analytics-charts" className="grid gap-3 lg:grid-cols-3">
        <BarCard title="Retrieval success rate" k="rate" fmt={pc} max={1} tip="successRate" />
        <BarCard title="Average recovery attempts" k="rec" fmt={(v) => v.toFixed(1)} tip="recoveryAttempts" />
        <BarCard title="Average search time" k="time" fmt={(v) => v.toFixed(1) + 's'} tip="searchTime" />
      </div>

      <div className="grid gap-3 lg:grid-cols-[1fr_1.4fr]">
        <Panel className="p-3.5">
          <div className="flex items-center justify-between mb-2">
            <H className="mb-0 text-xs">Failed retrievals and causes</H>
            <InfoTooltip
              title="Root Cause Analysis"
              body="Breaks down causes of failure: Memory-only baseline fails on moved items and mechanical slips, whereas Second Look isolates unrecoverable missing items."
            />
          </div>
          <ul className="space-y-1.5 text-xs">
            {Object.entries(causes).map(([c, n]) => (
              <li key={c} className="border-l-2 border-bad py-0.5 pl-2">
                <span className="text-tx font-medium">{c}</span><br />
                <span className="text-mu">Second Look: {n.second} | Baseline: {n.baseline}</span>
              </li>
            ))}
            {!Object.keys(causes).length && <li className="text-mu">No failures recorded.</li>}
          </ul>
        </Panel>

        <Panel data-tour="experiment-history" className="p-3.5">
          <div className="flex items-center justify-between mb-2">
            <H className="mb-0 text-xs">Experiment history</H>
            <InfoTooltip
              title="Individual Trial Log"
              body="Chronological ledger of executed pick operations, tracking operating mode, SKU, disturbance scenario, and recovery steps."
            />
          </div>
          <div className="max-h-72 overflow-auto">
            <table className="w-full border-collapse text-xs">
              <thead className="text-left text-mu">
                <tr>
                  {['#', 'Mode', 'Object', 'Scenario', 'Result', 'Time', 'Recoveries'].map((h) => (
                    <th key={h} className="whitespace-nowrap border-b border-ln px-2 py-1.5 font-medium">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {[...s.trials].reverse().slice(0, 40).map((x) => (
                  <tr key={x.n + x.mode + x.sc} className="whitespace-nowrap hover:bg-s2/40">
                    <td className="border-b border-ln px-2 py-1.5 font-mono text-mu">{x.n}</td>
                    <td className="border-b border-ln px-2 py-1.5">{MODE[x.mode]}</td>
                    <td className="border-b border-ln px-2 py-1.5">{OBJ[x.obj]}</td>
                    <td className="border-b border-ln px-2 py-1.5">{SCN[x.sc]}</td>
                    <td className={`border-b border-ln px-2 py-1.5 font-semibold ${x.ok ? 'text-ok' : 'text-bad'}`}>
                      {x.ok ? 'Retrieved' : 'Failed'}
                    </td>
                    <td className="border-b border-ln px-2 py-1.5 font-mono">{x.time}s</td>
                    <td className="border-b border-ln px-2 py-1.5 font-mono">{x.rec}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      </div>
    </div>
  )
}
