"""
GearHound backend: one Flask-SocketIO server (unlike GearGoat's split
controller/simulator on two ports) that owns the simulated CAN bus, the
vehicle's decoded state, and the attack console.
"""

import os
import threading
import time

from flask import Flask, request
from flask_cors import CORS
from flask_socketio import SocketIO

from attacks.manager import AttackManager
from can_bus import CanBus
from state import VehicleState
from vehicles.profiles import DEFAULT_PROFILE_KEY, list_profiles

PORT = int(os.environ.get("PORT", 4000))
STATE_HZ = 20
TRAFFIC_FLUSH_HZ = 8
TRAFFIC_BATCH_CAP = 200

app = Flask(__name__)
app.config["CORS_HEADERS"] = "Content-Type"
CORS(app, resources={r"/*": {"origins": "*"}})
socketio = SocketIO(app, cors_allowed_origins="*")

bus = CanBus()
state = VehicleState(bus, profile_key=DEFAULT_PROFILE_KEY)


def broadcast_attack_event(event: dict) -> None:
    socketio.emit("attack_event", event)
    if event.get("type") == "status":
        # An attack can finish on its own (duration elapsed, replay ended)
        # from inside its worker thread -- push the refreshed running list
        # so the UI doesn't show a stale "Stop" button forever.
        socketio.emit("attacks_running", attacks.list_running())


attacks = AttackManager(bus, state, broadcast_attack_event)

# ---------------------------------------------------------------------------
# Physics: turns raw "throttle held" / "turning held" input into gradually
# changing speed/rpm/turn-signal signals, written onto the bus like a real
# ECU would (same idea as GearGoat's check_accel/check_turn loop).
# ---------------------------------------------------------------------------
_control_lock = threading.Lock()
_throttle = 0        # -1 braking, 0 idle, 1 accelerating
_turning = 0          # -1 left, 0 off, 1 right
MAX_SPEED = 220
MAX_RPM = 6500
IDLE_RPM = 800

# Tracks which client's mousedown last claimed each "held" control, so a
# disconnect can reset ONLY the input that client actually owned. Counting
# total connected clients (an earlier version of this) gets this wrong: an
# idle spectator tab left open masks a runaway car left by the tab that was
# actually driving and then disconnected mid-press.
_owners_lock = threading.Lock()
_control_owners = {"throttle": None, "turning": None, "horn": None}


def _set_owner(control: str, sid, active: bool) -> None:
    with _owners_lock:
        _control_owners[control] = sid if active else None


def set_throttle(value: int, sid=None) -> None:
    global _throttle
    with _control_lock:
        _throttle = value
    _set_owner("throttle", sid, value != 0)


def set_turning(value: int, sid=None) -> None:
    global _turning
    with _control_lock:
        _turning = value
    _set_owner("turning", sid, value != 0)


def set_horn(value: int, sid=None) -> None:
    state.write_signal("horn", 1 if value else 0)
    _set_owner("horn", sid, bool(value))


def physics_loop() -> None:
    last_signal_toggle = 0.0
    signal_on = False
    while True:
        with _control_lock:
            throttle, turning = _throttle, _turning

        speed = state.speed
        rpm = state.rpm

        if throttle > 0:
            speed = min(MAX_SPEED, speed + 2.5)
            rpm = min(MAX_RPM, IDLE_RPM + speed * 28)
        elif throttle < 0:
            speed = max(0, speed - 4.0)
            rpm = max(IDLE_RPM, IDLE_RPM + speed * 20)
        else:
            speed = max(0, speed - 0.6)
            rpm = max(IDLE_RPM, rpm - 40)

        state.write_signal("speed", int(speed))
        state.write_signal("rpm", int(rpm))

        now = time.time()
        if turning != 0:
            if now - last_signal_toggle > 0.5:
                signal_on = not signal_on
                last_signal_toggle = now
                bits = (1 if turning < 0 else 0) | (2 if turning > 0 else 0)
                state.write_signal("turn_signal", bits if signal_on else 0)
        else:
            if state.turn_left or state.turn_right:
                state.write_signal("turn_signal", 0)

        time.sleep(0.05)


# ---------------------------------------------------------------------------
# Broadcasters
# ---------------------------------------------------------------------------
def state_broadcast_loop() -> None:
    while True:
        socketio.emit("car_state", state.snapshot())
        time.sleep(1.0 / STATE_HZ)


_traffic_batch: list[dict] = []
_traffic_lock = threading.Lock()


def _on_any_frame(arb_id: int, data: bytes, timestamp: float) -> None:
    with _traffic_lock:
        _traffic_batch.append({
            "arb_id": arb_id,
            "data": list(data),
            "ts": timestamp,
        })
        if len(_traffic_batch) > TRAFFIC_BATCH_CAP:
            del _traffic_batch[: len(_traffic_batch) - TRAFFIC_BATCH_CAP]


def traffic_flush_loop() -> None:
    while True:
        time.sleep(1.0 / TRAFFIC_FLUSH_HZ)
        with _traffic_lock:
            if not _traffic_batch:
                continue
            batch = list(_traffic_batch)
            _traffic_batch.clear()
        socketio.emit("traffic", {"frames": batch, "bus_congestion": bus.congestion})


bus.subscribe(_on_any_frame)


# ---------------------------------------------------------------------------
# Socket.IO handlers
# ---------------------------------------------------------------------------
@socketio.on("connect")
def on_connect():
    socketio.emit("car_state", state.snapshot())
    socketio.emit("vehicles", {"profiles": list_profiles(), "active": state.profile.key})
    socketio.emit("attacks_running", attacks.list_running())
    socketio.emit("captures", attacks.list_captures())


@socketio.on("disconnect")
def on_disconnect():
    # A held pedal, indicator, or horn press sends an "active" value on
    # mousedown and a neutral one on mouseup, but a page refresh or a
    # closed tab while it's held never fires that mouseup. Reset only the
    # controls THIS client actually owned (see _control_owners above), so
    # an idle spectator tab disconnecting never touches input someone else
    # is still actively holding, and a driving tab disconnecting can't be
    # masked by other tabs merely being connected.
    sid = request.sid
    with _owners_lock:
        owned = [name for name, owner in _control_owners.items() if owner == sid]
    if "throttle" in owned:
        set_throttle(0)
    if "turning" in owned:
        set_turning(0)
    if "horn" in owned:
        set_horn(0)


@socketio.on("control")
def on_control(data, *_ignored):
    signal = data.get("signal")
    sid = request.sid
    if signal == "throttle":
        set_throttle(int(data.get("value", 0)), sid)
    elif signal == "turning":
        set_turning(int(data.get("value", 0)), sid)
    elif signal == "door":
        idx = int(data.get("index", 0))
        locked = bool(data.get("locked"))
        doors = list(state.doors)
        if 0 <= idx < len(doors):
            doors[idx] = 1 if locked else 0
        bitmask = 0
        for i, d in enumerate(doors):
            if d:
                bitmask |= (1 << i)
        state.write_signal("doors", bitmask)
    elif signal == "headlights":
        state.write_signal("headlights", 1 if data.get("value") else 0)
    elif signal == "horn":
        set_horn(1 if data.get("value") else 0, sid)


@socketio.on("vehicle_select")
def on_vehicle_select(data, *_ignored):
    key = data.get("profile", DEFAULT_PROFILE_KEY)
    state.set_profile(key)
    set_throttle(0)
    set_turning(0)
    socketio.emit("car_state", state.snapshot())
    socketio.emit("vehicles", {"profiles": list_profiles(), "active": state.profile.key})


@socketio.on("attack_start")
def on_attack_start(data, *_ignored):
    result = attacks.start(data.get("kind"), data.get("params", {}))
    socketio.emit("attacks_running", attacks.list_running())
    return result


@socketio.on("attack_stop")
def on_attack_stop(data, *_ignored):
    result = attacks.stop(data.get("id"))
    socketio.emit("attacks_running", attacks.list_running())
    return result


@socketio.on("capture_start")
def on_capture_start(data, *_ignored):
    result = attacks.start_capture(data.get("name", f"capture-{int(time.time())}"))
    socketio.emit("captures", attacks.list_captures())
    return result


@socketio.on("capture_stop")
def on_capture_stop(_data=None, *_ignored):
    result = attacks.stop_capture()
    socketio.emit("captures", attacks.list_captures())
    return result


if __name__ == "__main__":
    threading.Thread(target=physics_loop, daemon=True).start()
    threading.Thread(target=state_broadcast_loop, daemon=True).start()
    threading.Thread(target=traffic_flush_loop, daemon=True).start()

    print(f"GearHound backend on :{PORT} (CAN bustype={bus.bustype}, channel={bus.channel})")
    socketio.run(app, host="0.0.0.0", port=PORT, allow_unsafe_werkzeug=True)
