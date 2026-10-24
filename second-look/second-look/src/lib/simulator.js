import { L, OBJ, SCN, pc } from './constants.js'

/** Stand-in robot used when VITE_WS_URL is not set. It emits the same events a backend would. */
export function createSimulator(store) {
  const get = store.get, d = store.dispatch
  let tok = 0, bt = 0

  const sleep = (ms, k) => new Promise((r) => {
    const tick = () => {
      if (k !== tok) return r(false)
      if (get().paused) return setTimeout(tick, 120)
      if (get().fast || ms <= 0) return setTimeout(() => r(true), 0)
      const x = Math.min(ms, 60); ms -= x; setTimeout(tick, x)
    }
    tick()
  })

  async function start() {
    if (get().running) return
    const k = ++tok, { mode, scn: sc, obj } = get(), O = OBJ[obj], o = O.toLowerCase(), vis = new Set()
    let t = 0, rec = 0, slipUsed = false, target = 'A'
    const w = async (s) => { t += s; if (!(await sleep(s * 450, k))) throw 0 }
    const lg = (text) => d({ t: 'log', time: t, text })
    const dec = (path, text) => { d({ t: 'decision', path, text }); lg(text) }
    const fin = (ok, cause) => {
      const m = ok ? `${O} retrieved in ${t.toFixed(1)}s${rec ? ` after ${rec} recovery step${rec > 1 ? 's' : ''}` : ''}.` : cause + '.'
      d({ t: 'task', status: ok ? 'completed' : 'failed', msg: m, progress: ok ? 100 : get().progress })
      lg(m)
      d({ t: 'done', outcome: { ok, text: m }, trial: { n: get().trials.length + 1, mode, obj, sc, ok, time: +t.toFixed(1), rec, cause: ok ? '' : cause } })
    }

    d({ t: 'start', actual: sc === 'moved' ? 'BC'[Math.random() * 2 | 0] : sc === 'missing' ? null : 'A', slip: sc === 'slip' })
    lg(`Task started: retrieve the ${o}.`)
    dec('trust', mode === 'baseline'
      ? `Memory-only baseline: going straight to Table A, where the ${o} was last seen.`
      : `The ${o} was last seen on Table A with 92% confidence. Checking there first.`)
    try {
      for (;;) {
        const pr = vis.size * 25
        d({ t: 'task', status: 'moving', at: target, progress: 10 + pr, msg: `Moving to ${L[target].n}` }); await w(1.6)
        d({ t: 'task', status: 'searching', progress: Math.min(70, 25 + pr), msg: `Scanning ${L[target].n}` }); await w(0.8)
        const old = get().beliefs[target], name = L[target].n
        if (get().actual === target) {
          d({ t: 'belief', last: target, beliefs: { A: 0.01, B: 0.01, C: 0.01, U: 0.01, [target]: 0.97 }, ev: `${name}: ${pc(old)} → 97%. The ${o} is in view, so confidence rises.` })
          const tx = `${O} spotted on ${name}.`; d({ t: 'obs', loc: target, seen: true, text: tx }); lg(tx)
          d({ t: 'task', status: 'retrieving', progress: 75, msg: `Grasping the ${o}` }); await w(1.2)
          if (get().slip && !slipUsed) {
            slipUsed = true
            if (mode === 'baseline') return fin(false, 'Grasp slipped and the baseline cannot retry')
            rec++; lg('Grasp slipped.')
            dec('retry', `The grasp slipped, but the ${o} is still in view. Retrying once.`)
            d({ t: 'task', status: 'retrieving', progress: 88, msg: 'Retrying grasp' }); await w(1.2)
          }
          return fin(true)
        }
        vis.add(target)
        const b = { ...get().beliefs }, freed = b[target] * 0.97
        b[target] *= 0.03
        const open = ['A', 'B', 'C'].filter((x) => !vis.has(x)), sum = open.reduce((a, x) => a + b[x], 0)
        if (open.length && sum > 0) open.forEach((x) => (b[x] += (freed * b[x]) / sum)); else b.U += freed
        d({ t: 'belief', beliefs: b, ev: `${name}: ${pc(old)} → ${pc(b[target])}. No ${o} in view, so confidence drops.` })
        const tx = `No ${o} on ${name}.`; d({ t: 'obs', loc: target, seen: false, text: tx }); lg(tx)
        if (mode === 'baseline') return fin(false, 'Object not at the last-known location')
        rec++
        const next = open.sort((a, c) => b[c] - b[a])[0]
        if (next && b[next] >= 0.3) {
          target = next
          dec('search', `${name} is empty. ${L[next].n} now holds ${pc(b[next])} of the belief, so the robot searches there next.`)
          await w(0.6)
        } else {
          dec('help', `No surface holds more than 30% of the belief, and ${pc(b.U)} points somewhere out of view. Asking a person for help.`)
          return fin(false, 'Object missing from every known surface; human help requested')
        }
      }
    } catch { /* aborted by reset */ }
  }

  function trigger(sc) {
    d({ t: 'ui', patch: { scn: sc } })
    const s = get()
    if (!s.running) return
    let loc = s.actual
    if (sc === 'moved') {
      const o = ['A', 'B', 'C'].filter((x) => x !== s.actual && !s.visited.includes(x))
      if (o.length) loc = o[Math.random() * o.length | 0]
    }
    if (sc === 'missing') loc = null
    d({ t: 'actual', loc, slip: sc === 'slip' })
    d({ t: 'log', time: s.clock, text: `Scenario triggered: ${SCN[sc].toLowerCase()}.` })
  }

  function reset() { tok++; bt++; d({ t: 'reset' }) }

  async function batch() {
    if (get().running || get().fast) return
    const b = ++bt, ob = Object.keys(OBJ), list = ['none', 'moved', 'moved', 'slip', 'missing', 'none', 'moved', 'slip']
    let i = 0
    d({ t: 'ui', patch: { fast: true } })
    for (const m of ['second', 'baseline']) for (const sc of list) {
      if (b !== bt) return
      d({ t: 'ui', patch: { mode: m, scn: sc, obj: ob[i++ % 3] } })
      await start()
    }
    d({ t: 'ui', patch: { fast: false, mode: 'second', scn: 'none' } })
  }

  return { start, trigger, reset, batch }
}
