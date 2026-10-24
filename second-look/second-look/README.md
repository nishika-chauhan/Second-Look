# Second Look

React + Vite + Tailwind + Recharts + WebSocket frontend for the Second Look robot retrieval demo.

```bash
npm install
cp .env.example .env     # optional: set VITE_WS_URL to use a live backend
npm run dev
```

With `VITE_WS_URL` empty, a built-in simulator plays the robot. With it set, the app connects over WebSocket
(auto-reconnect with backoff) and the simulator is not used.

## Event protocol (server to browser, JSON, one event per message)

Every screen renders from one store (`src/lib/reducer.js`), so these events keep all four screens consistent.

| `t` | Fields | Meaning |
| --- | --- | --- |
| `start` | `actual` (`A`/`B`/`C`/null), `slip` | A run begins; `actual` is the ground-truth location |
| `task` | `status`, `msg`, `progress`, `at` | `status`: idle, moving, searching, retrieving, completed, failed. `at`: `A`/`B`/`C`/`home` |
| `belief` | `beliefs {A,B,C,U}` (sum to 1), `last?`, `ev` | New belief and a readable evidence line. `U` = out of view |
| `obs` | `loc`, `seen`, `text` | What the camera saw |
| `decision` | `path`, `text` | `trust`, `search`, `retry` or `help` |
| `log` | `time`, `text` | Event log line, `time` in seconds |
| `actual` | `loc`, `slip` | Ground truth changed mid-run |
| `done` | `outcome {ok,text}`, `trial?` | `trial`: `{n, mode, obj, sc, ok, time, rec, cause}` feeds analytics |
| `pause` / `reset` | `v` | Pause state / clear the run |

## Commands (browser to server)

`{cmd:'start', obj, scenario, mode}`, `{cmd:'pause', value}`, `{cmd:'reset'}`, `{cmd:'scenario', scenario}`
where `obj` is cup, bottle or box, `scenario` is none, moved, missing or slip, and `mode` is second or baseline.

## Layout

- `src/lib/reducer.js`: state and events. `store.js`: tiny external store. `socket.js`: WebSocket client.
- `src/lib/simulator.js`: simulated robot that emits the same events.
- `src/RobotContext.jsx`: provider; picks WebSocket or simulator and exposes actions.
- `src/screens/*`: the five sidebar screens. `src/components/*`: shared UI and the SVG scene.

Analytics only shows trials the app has recorded. Simulated trials are labeled as such in the UI.
