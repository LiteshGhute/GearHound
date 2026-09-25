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

# Tracks every client currently holding each "held" control active (not
# just the most recent one), keyed by control name -> {sid: value}. A
# single global "owner" (an earlier version of this) only gated disconnect
# cleanup, not ordinary writes: if client A held accelerate and client B
# also pressed it, A releasing its own key unconditionally zeroed the
# shared value and cancelled B's still-active press too. The effective
# value is whichever active holder's press is most recent (re-inserting a
# key on update moves it to the end, so `reversed()` finds it), and
# releasing (or disconnecting) removes only that one sid, recomputing the
# effective value from whoever else is still holding it.
_holders_lock = threading.Lock()
_control_holders = {"throttle": {}, "turning": {}, "horn": {}}


def _update_holders(control: str, sid, value) -> int:
    with _holders_lock:
        holders = _control_holders[control]
        holders.pop(sid, None)
        if value:
            holders[sid] = value
        return next(reversed(holders.values())) if holders else 0


def _release_all_holders(sid) -> dict:
    """Remove sid from every control it was holding (e.g. on disconnect).
    Returns {control: recomputed_effective_value} for controls it affected."""
    changed = {}
    with _holders_lock:
        for control, holders in _control_holders.items():
            if sid in holders:
                del holders[sid]
                changed[control] = next(reversed(holders.values())) if holders else 0
    return changed


def _reset_all_holders() -> None:
    with _holders_lock:
        for holders in _control_holders.values():
            holders.clear()


def _apply_throttle(value: int) -> None:
    global _throttle
    with _control_lock:
        _throttle = value


def _apply_turning(value: int) -> None:
    global _turning
    with _control_lock:
        _turning = value


def _apply_horn(value: int) -> None:
    state.write_signal("horn", 1 if value else 0)


_CONTROL_APPLIERS = {"throttle": _apply_throttle, "turning": _apply_turning, "horn": _apply_horn}


def set_throttle(value: int, sid=None) -> None:
    _apply_throttle(_update_holders("throttle", sid, value))


def set_turning(value: int, sid=None) -> None:
    _apply_turning(_update_holders("turning", sid, value))


def set_horn(value: int, sid=None) -> None:
    _apply_horn(_update_holders("horn", sid, 1 if value else 0))


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
    # closed tab while it's held never fires that mouseup. Release only
    # the controls THIS client was holding (see _control_holders above),
    # recomputing each from whoever else may still be holding it, so an
    # idle spectator tab disconnecting never touches input someone else
    # is still actively holding, and a driving tab disconnecting can't be
    # masked by other tabs merely being connected.
    for control, value in _release_all_holders(request.sid).items():
        _CONTROL_APPLIERS[control](value)


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
    # A hard reset: clears every client's held input, not just whichever
    # value would win the normal holders-based arbitration, since switching
    # cars should never leave someone's stale press from the old vehicle
    # still steering the new one.
    _reset_all_holders()
    _apply_throttle(0)
    _apply_turning(0)
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
