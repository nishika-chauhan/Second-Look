/** WebSocket client with exponential-backoff reconnect. Incoming JSON events go straight into the store. */
const BLOCKED = new Set(['ui', 'conn']) // the server may not change local UI state

export function connectSocket(url, store, onStatus) {
  let ws, closed = false, retry = 0, timer
  const open = () => {
    onStatus('connecting')
    ws = new WebSocket(url)
    ws.onopen = () => { retry = 0; onStatus('live') }
    ws.onmessage = (m) => {
      try {
        const e = JSON.parse(m.data)
        if (e && typeof e.t === 'string' && !BLOCKED.has(e.t)) store.dispatch(e)
      } catch { /* ignore malformed frames */ }
    }
    ws.onclose = () => {
      if (closed) return
      onStatus('offline')
      timer = setTimeout(open, Math.min(1000 * 2 ** retry++, 10000))
    }
    ws.onerror = () => ws.close()
  }
  open()
  return {
    send: (msg) => { if (ws?.readyState === 1) { ws.send(JSON.stringify(msg)); return true } return false },
    close() { closed = true; clearTimeout(timer); ws?.close() },
  }
}
