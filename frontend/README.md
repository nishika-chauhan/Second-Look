# Dashboard

Serve this directory from the repository root with:

```bash
cd frontend
python -m http.server 5173
```

Open `http://localhost:5173/dashboard.html`. Run the FastAPI WebSocket backend separately from `ai/` on port 8000. The frontend connects to `ws://localhost:8000/ws`.

The dashboard includes live event cards, belief confidence plotting, engine/offline/fallback metadata, controls for scenario/engine/probabilities/seed, move-while-hidden and reset commands, CSV results charts, and a final-demo walkthrough.

Note: the server.py bundled in this archive appears older than the updated protocol described in the project handoff. In particular, it does not currently handle `move_object` and its `start` command does not consume `engine`, `false_alarm_rate`, or `seed`; it also still uses wildcard CORS. Use the updated backend from B before testing these controls, and tighten CORS to `http://localhost:5173` (plus the agreed 127.0.0.1 / Vite preview origins as appropriate).
