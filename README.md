# GearHound

A CAN bus car-hacking simulator, built as a from-scratch successor to
[GearGoat](https://github.com/ine-labs/GearGoat). Same idea: a fake
dashboard wired to a real CAN bus, safe to attack. GearHound adds a proper
live dashboard UI, three vehicle profiles instead of one fixed wiring, and
a built-in attack console (fuzzing, flooding/DoS, signal spoofing, and
capture and replay) instead of requiring a separate can-utils terminal
session.

## Why it's different from GearGoat

- **One unified backend**, not a split controller/simulator across two
  ports. The same process writes legitimate signals and decodes whatever
  is on the bus, closer to how a real ECU behaves.
- **Runs anywhere without Linux/SocketCAN.** `CAN_BUSTYPE=virtual` (the
  default) uses python-can's in-process virtual bus, so the whole thing,
  dashboard, traffic monitor, every attack, works on macOS/Windows for
  development. Set `CAN_BUSTYPE=socketcan` for a real Linux `vcan0`
  deployment (see below).
- **Three vehicle profiles** (Sedan / SUV / Truck), each with a different
  arbitration ID map. The SUV profile even packs two signals (speed and
  RPM) into the same frame at different byte offsets, so "the ID you
  learned on one car doesn't transfer" is a first-class, switchable
  feature.
- **Attacks are UI-driven**, not terminal exercises: fuzzing, bus flooding
  (with a live "bus congestion" effect on the dashboard), signal spoofing
  (an active override that wins against legitimate writes), and
  record/replay capture, all with live traffic visible as they run.

## Project layout

```
backend/
  app.py                 Flask-SocketIO server, physics loop, broadcasters
  can_bus.py              python-can wrapper (virtual/socketcan)
  state.py                Simulated vehicle state, decodes any frame on the bus
  vehicles/profiles.py     Sedan / SUV / Truck arbitration-ID maps
  attacks/
    base.py                Shared attack-thread plumbing and event throttling
    fuzz.py, flood.py, spoof.py, replay.py
    manager.py             Starts/stops attacks, owns capture recordings
frontend/
  src/hooks/useSocket.js   Socket.IO client and all app state
  src/components/          Dashboard, TrafficMonitor, AttackConsole, VehicleSelector
  src/styles/global.css    Dark dashboard theme
```

## Running it locally (development)

Requires Python 3.10+ (project was built and tested against 3.12) and
Node 18+.

**Backend:**
```sh
cd backend
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
CAN_BUSTYPE=virtual PORT=4000 ./venv/bin/python3 app.py
```

**Frontend:**
```sh
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. The frontend expects the backend at
`http://localhost:4000` by default (override with `VITE_BACKEND_URL`).

## Known limitation (dev mode only)

The Flask-SocketIO dev server (Werkzeug plus `simple-websocket`, no
eventlet/gevent) doesn't reliably complete the WebSocket upgrade
handshake. Socket.IO transparently falls back to HTTP long-polling, so
everything still works, just with slightly higher latency than a real
WebSocket connection. This resolves itself in a production deployment
behind gunicorn and eventlet.

## Deploying against a real CAN bus

Set `CAN_BUSTYPE=socketcan` and `CAN_CHANNEL=vcan0` (or a real interface),
and run the backend on a Linux host with the interface already up
(`ip link add dev vcan0 type vcan && ip link set up vcan0`, same as
GearGoat's `vcan_setup.sh`). Build the frontend (`npm run build`) and serve
the static output from any web server.

## The attacks

- **Fuzzing.** Sweeps a range of arbitration IDs with random or
  incremental payloads to discover undocumented signals. Automates the
  cansniffer "freeze unchanging bytes" trick GearGoat's manual teaches by
  hand.
- **Flood / DoS.** Hammers a low (high-priority) arbitration ID as fast as
  possible. Modeled bus congestion probabilistically drops legitimate
  frames while it runs, visible as a live warning banner on the dashboard.
- **Signal spoofing.** Continuously re-sends a forged value for a chosen
  signal at a configurable rate, overriding whatever the legitimate writer
  sends. An active override, not a one-shot injection.
- **Capture and replay.** Records everything on the bus for a window of
  time and plays it back verbatim, at adjustable speed, optionally looped.
