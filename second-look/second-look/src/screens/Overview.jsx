import { Panel, Muted } from '../components/ui.jsx'

const STEPS = [
  ['workstation', 'Start retrieval', 'Robot Workstation'], ['memory', 'Observe memory and decisions', 'Memory & Decisions'],
  ['playground', 'Trigger a recovery scenario', 'Recovery Playground'], ['analytics', 'Evaluate the outcome', 'Results & Analytics'],
]
export default function Overview({ setView }) {
  return (
    <>
      <Panel>
        <h2 className="mb-2 text-[17px] font-semibold">Can the robot trust what it remembers?</h2>
        <p className="max-w-[62ch] text-mu">Second Look keeps a belief about where an object is, then updates it as the camera sees or misses the object. When the world changes, it decides whether to trust memory, search elsewhere, retry or ask for help.</p>
      </Panel>
      <div className="grid gap-3 lg:grid-cols-4">
        {STEPS.map(([k, a, b], i) => (
          <button key={k} onClick={() => setView(k)} className="flex flex-col gap-1 rounded-[10px] border border-ln bg-s1 p-4 text-left hover:border-obs">
            <Muted>Step {i + 1}</Muted><b>{a}</b><Muted>{b}</Muted>
          </button>
        ))}
      </div>
    </>
  )
}
