"""Coordinates attack lifecycle: start/stop/list, and capture recordings for replay."""

from can_bus import CanBus
from state import VehicleState

from attacks.base import RunningAttack
from attacks.flood import run_flood
from attacks.fuzz import run_fuzz
from attacks.replay import CaptureBuffer, run_replay
from attacks.spoof import run_spoof

ATTACK_KINDS = ("fuzz", "flood", "spoof", "replay")


class AttackManager:
    def __init__(self, bus: CanBus, state: VehicleState, on_event):
        self.bus = bus
        self.state = state
        self.on_event = on_event
        self.running: dict[str, RunningAttack] = {}
        self.captures: dict[str, CaptureBuffer] = {}
        self._active_capture: CaptureBuffer | None = None
        self.bus.subscribe(self._feed_active_capture)

    # ---- recording (for replay) --------------------------------------
    def start_capture(self, name: str) -> dict:
        cap = CaptureBuffer(name)
        cap.start()
        self.captures[name] = cap
        self._active_capture = cap
        self.on_event({"type": "capture_started", "name": name})
        return cap.to_dict()

    def stop_capture(self) -> dict:
        if self._active_capture is None:
            return {"error": "no capture in progress"}
        self._active_capture.stop()
        result = self._active_capture.to_dict()
        self._active_capture = None
        self.on_event({"type": "capture_stopped", **result})
        return result

    def _feed_active_capture(self, arb_id: int, data: bytes, ts: float) -> None:
        if self._active_capture is not None:
            self._active_capture.on_frame(arb_id, data, ts)

    def list_captures(self) -> list:
        return [c.to_dict() for c in self.captures.values()]

    # ---- attacks --------------------------------------------------------
    def start(self, kind: str, params: dict) -> dict:
        if kind not in ATTACK_KINDS:
            return {"error": f"unknown attack kind '{kind}'"}

        if kind == "fuzz":
            worker = lambda a: run_fuzz(a, self.bus)
        elif kind == "flood":
            worker = lambda a: run_flood(a, self.bus)
        elif kind == "spoof":
            worker = lambda a: run_spoof(a, self.bus, self.state.profile)
        elif kind == "replay":
            cap = self.captures.get(params.get("capture"))
            if cap is None:
                return {"error": f"no capture named '{params.get('capture')}'"}
            worker = lambda a: run_replay(a, self.bus, cap)

        attack = RunningAttack(kind, params, worker, self.on_event)
        self.running[attack.id] = attack
        attack.start()
        return attack.to_dict()

    def stop(self, attack_id: str) -> dict:
        attack = self.running.get(attack_id)
        if attack is None:
            return {"error": f"no running attack '{attack_id}'"}
        attack.stop()
        return attack.to_dict()

    def list_running(self) -> list:
        # Only surface attacks still actually running -- finished/stopped/
        # errored ones are dropped so the console doesn't accumulate stale
        # "Stop" buttons for attacks that already ended on their own.
        return [a.to_dict() for a in self.running.values() if a.status == "running"]
