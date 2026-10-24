/** Minimal external store so the simulator can read fresh state synchronously. */
export function createStore(reducer, initial) {
  let state = initial
  const subs = new Set()
  return {
    get: () => state,
    dispatch(e) { state = reducer(state, e); subs.forEach((f) => f()) },
    subscribe: (f) => (subs.add(f), () => subs.delete(f)),
  }
}
