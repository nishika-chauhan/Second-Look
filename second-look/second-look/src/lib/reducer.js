/**
 * Every screen renders from this one state. Both the simulator and the WebSocket
 * feed it the same events:
 *   start    { actual, slip }                  new run begins
 *   task     { status, msg, progress, at }     robot state and location (A | B | C | home)
 *   belief   { beliefs:{A,B,C,U}, last?, ev }  belief update plus a readable evidence line
 *   obs      { loc, seen, text }               what the camera saw
 *   decision { path, text }                    path: trust | search | retry | help
 *   log      { time, text }                    event log entry (time in seconds)
 *   done     { outcome:{ok,text}, trial? }     run finished; trial is stored for analytics
 *   actual   { loc, slip }  pause { v }  reset
 */
export const initRun = () => ({
  status: 'idle', progress: 0, at: 'home', actual: 'A', slip: false,
  beliefs: { A: 0.92, B: 0.04, C: 0.03, U: 0.01 }, last: 'A', obs: null, visited: [],
  decision: null, evidence: [], timeline: [], log: [], outcome: null,
  msg: 'Ready to start', running: false, paused: false, clock: 0,
})
export const initial = { obj: 'cup', scn: 'none', mode: 'second', fast: false, trials: [], conn: 'simulated', ...initRun() }

export function reducer(s, e) {
  switch (e.t) {
    case 'reset': return { ...s, ...initRun(), fast: false }
    case 'start': return { ...s, ...initRun(), running: true, status: 'moving', msg: 'Task started', actual: 'actual' in e ? e.actual : s.actual, slip: !!e.slip }
    case 'actual': return { ...s, actual: e.loc, slip: !!e.slip }
    case 'task': return { ...s, status: e.status, msg: e.msg ?? s.msg, progress: e.progress ?? s.progress, at: e.at || s.at }
    case 'belief': return { ...s, beliefs: e.beliefs, last: e.last || s.last, evidence: e.ev ? [e.ev, ...s.evidence] : s.evidence }
    case 'obs': return { ...s, obs: e, timeline: [{ k: e.seen ? 'obs' : 'bad', text: e.text }, ...s.timeline], visited: e.seen ? s.visited : [...s.visited, e.loc] }
    case 'decision': return { ...s, decision: e }
    case 'log': return { ...s, clock: e.time, log: [e, ...s.log].slice(0, 80) }
    case 'done': return { ...s, running: false, outcome: e.outcome, trials: e.trial ? [...s.trials, e.trial] : s.trials }
    case 'pause': return { ...s, paused: e.v }
    case 'clear': return { ...s, trials: [] }
    case 'ui': return { ...s, ...e.patch }
    case 'conn': return { ...s, conn: e.conn }
    default: return s
  }
}
