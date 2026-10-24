import { createContext, useContext, useEffect, useMemo, useRef, useSyncExternalStore } from 'react'
import { createStore } from './lib/store.js'
import { reducer, initial } from './lib/reducer.js'
import { createSimulator } from './lib/simulator.js'
import { connectSocket } from './lib/socket.js'

export const WS_URL = import.meta.env.VITE_WS_URL || ''
export const LIVE = !!WS_URL
const store = createStore(reducer, { ...initial, conn: LIVE ? 'connecting' : 'simulated' })
const sim = createSimulator(store)
const Ctx = createContext(null)

export function RobotProvider({ children }) {
  const s = useSyncExternalStore(store.subscribe, store.get)
  const sock = useRef(null)

  useEffect(() => {
    if (!LIVE) return
    sock.current = connectSocket(WS_URL, store, (conn) => store.dispatch({ t: 'conn', conn }))
    return () => sock.current.close()
  }, [])

  const a = useMemo(() => {
    const send = (m) => sock.current?.send(m)
    const ui = (patch) => store.dispatch({ t: 'ui', patch })
    return {
      setObj: (obj) => ui({ obj }),
      setMode: (mode) => ui({ mode }),
      start: () => { const { obj, scn, mode } = store.get(); LIVE ? send({ cmd: 'start', obj, scenario: scn, mode }) : sim.start() },
      pause: () => { const v = !store.get().paused; if (LIVE) send({ cmd: 'pause', value: v }); store.dispatch({ t: 'pause', v }) },
      reset: () => { if (LIVE) { send({ cmd: 'reset' }); store.dispatch({ t: 'reset' }) } else sim.reset() },
      scenario: (sc) => { if (LIVE) { ui({ scn: sc }); send({ cmd: 'scenario', scenario: sc }) } else sim.trigger(sc) },
      batch: () => sim.batch(),
      clear: () => store.dispatch({ t: 'clear' }),
    }
  }, [])

  return <Ctx.Provider value={{ s, a }}>{children}</Ctx.Provider>
}
export const useRobot = () => useContext(Ctx)
