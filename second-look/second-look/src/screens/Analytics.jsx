import { Bar, BarChart, CartesianGrid, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { useRobot, LIVE } from '../RobotContext.jsx'
import { MODE, OBJ, SCN, pc, stats } from '../lib/constants.js'
import { Panel, H, Muted, Btn } from '../components/ui.jsx'

function BarCard({ title, k, fmt, max }) {
  const { s } = useRobot()
  const a = stats(s.trials, 'second'), b = stats(s.trials, 'baseline')
  const data = [{ name: MODE.second, value: a[k] }, { name: 'Baseline', value: b[k] }]
  return (
    <Panel>
      <H>{title}</H>
      <ResponsiveContainer width="100%" height={190}>
        <BarChart data={data} margin={{ top: 18, right: 8, left: -12, bottom: 0 }}>
          <CartesianGrid stroke="#2b3644" vertical={false} />
          <XAxis dataKey="name" stroke="#8d9aac" tickLine={false} fontSize={12} />
          <YAxis stroke="#8d9aac" tickLine={false} axisLine={false} fontSize={12} domain={[0, max || 'auto']} tickFormatter={fmt} />
          <Tooltip cursor={{ fill: '#1f2936' }} contentStyle={{ background: '#171e27', border: '1px solid #2b3644', borderRadius: 8 }} formatter={(v) => fmt(v)} />
          <Bar dataKey="value" radius={[4, 4, 0, 0]} isAnimationActive={false}>
            {data.map((_, i) => <Cell key={i} fill={i ? '#8d9aac' : '#46c4b2'} />)}
            <LabelList dataKey="value" position="top" formatter={fmt} fill="#e7ecf3" fontSize={12} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <Muted>{a.n} Second Look and {b.n} baseline trials</Muted>
    </Panel>
  )
}

export default function Analytics() {
  const { s, a } = useRobot()
  const batch = !LIVE && <Btn primary onClick={a.batch} disabled={s.running || s.fast}>Run 16 simulated trials</Btn>
  if (!s.trials.length) return (
    <Panel>
      <h2 className="mb-2 text-[17px] font-semibold">No trials yet</h2>
      <p className="text-mu">Run a task in the Robot Workstation or Recovery Playground{LIVE ? '' : ', or run a batch of simulated trials'} to compare Second Look with the baseline.</p>
      <div className="mt-3">{batch}</div>
    </Panel>
  )
  const causes = {}
  s.trials.filter((x) => !x.ok).forEach((x) => { (causes[x.cause] ||= { second: 0, baseline: 0 })[x.mode]++ })
  return (
    <>
      <Panel>
        <span className="inline-block rounded-full border border-mem px-2.5 py-0.5 text-[13px] text-mem">
          {LIVE ? 'Trials reported by the connected backend' : 'Simulated trials, recorded in this session. Not real robot data.'}
        </span>
        <div className="mt-3 flex flex-wrap gap-2">{batch}<Btn onClick={a.clear}>Clear results</Btn></div>
      </Panel>
      <div className="grid gap-4 lg:grid-cols-3">
        <BarCard title="Retrieval success rate" k="rate" fmt={pc} max={1} />
        <BarCard title="Average recovery attempts" k="rec" fmt={(v) => v.toFixed(1)} />
        <BarCard title="Average search time" k="time" fmt={(v) => v.toFixed(1) + 's'} />
      </div>
      <div className="grid gap-4 lg:grid-cols-[1fr_1.4fr]">
        <Panel>
          <H>Failed retrievals and causes</H>
          <ul className="space-y-1.5 text-[13.5px]">
            {Object.entries(causes).map(([c, n]) => <li key={c} className="border-l-2 border-bad py-1 pl-2.5">{c}<br /><span className="text-mu">Second Look {n.second}, baseline {n.baseline}</span></li>)}
            {!Object.keys(causes).length && <li className="text-mu">No failures recorded.</li>}
          </ul>
        </Panel>
        <Panel>
          <H>Experiment history</H>
          <div className="max-h-80 overflow-auto">
            <table className="w-full border-collapse text-[13.5px]">
              <thead className="text-left text-mu"><tr>{['#', 'Mode', 'Object', 'Scenario', 'Result', 'Time', 'Recoveries'].map((h) => <th key={h} className="whitespace-nowrap border-b border-ln px-2.5 py-2 font-medium">{h}</th>)}</tr></thead>
              <tbody>
                {[...s.trials].reverse().slice(0, 40).map((x) => (
                  <tr key={x.n + x.mode + x.sc} className="whitespace-nowrap">
                    <td className="border-b border-ln px-2.5 py-2">{x.n}</td><td className="border-b border-ln px-2.5 py-2">{MODE[x.mode]}</td>
                    <td className="border-b border-ln px-2.5 py-2">{OBJ[x.obj]}</td><td className="border-b border-ln px-2.5 py-2">{SCN[x.sc]}</td>
                    <td className={`border-b border-ln px-2.5 py-2 ${x.ok ? 'text-ok' : 'text-bad'}`}>{x.ok ? 'Retrieved' : 'Failed'}</td>
                    <td className="border-b border-ln px-2.5 py-2">{x.time}s</td><td className="border-b border-ln px-2.5 py-2">{x.rec}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      </div>
    </>
  )
}
