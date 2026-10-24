export const L = { A: { n: 'Table A', x: 110 }, B: { n: 'Table B', x: 300 }, C: { n: 'Shelf C', x: 490 } }
export const OBJ = { cup: 'Cup', bottle: 'Bottle', box: 'Box' }
export const SCN = { none: 'Object stays put', moved: 'Object moved', missing: 'Object missing', slip: 'Grasp slips' }
export const MODE = { second: 'Second Look', baseline: 'Memory-only baseline' }
export const ST = { idle: 'Idle', searching: 'Searching', moving: 'Moving', retrieving: 'Retrieving', completed: 'Completed', failed: 'Failed' }
export const PATH = {
  trust: ['Trust memory', 'Revisit the last-known location when evidence supports it.'],
  search: ['Search elsewhere', 'Explore likely alternative locations.'],
  retry: ['Retry', 'Repeat an action when a retry is justified.'],
  help: ['Request help', 'Ask for human assistance when uncertainty remains too high.'],
}
export const pc = (v) => Math.round(v * 100) + '%'
export const best = (b) => ['A', 'B', 'C'].sort((x, y) => b[y] - b[x])[0]
export function stats(trials, m) {
  const t = trials.filter((x) => x.mode === m), n = t.length
  const av = (f) => (n ? t.reduce((a, x) => a + f(x), 0) / n : 0)
  return { n, rate: n ? t.filter((x) => x.ok).length / n : 0, time: av((x) => x.time), rec: av((x) => x.rec) }
}
