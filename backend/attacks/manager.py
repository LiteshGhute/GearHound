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
    def _unique_capture_name(self, name: str) -> str:
        # The frontend's capture-name field defaults to a static
        # "capture-1" that nobody has to edit, so recording twice in a row
        # with the field untouched is the COMMON case, not a rare misuse.
        # Silently overwriting `self.captures[name]` would destroy the
        # earlier finished recording with no warning; rename instead.
        if name not in self.captures:
            return name
        n = 2
        while f"{name}-{n}" in self.captures:
            n += 1
        return f"{name}-{n}"

    def start_capture(self, name: str) -> dict:
        # Starting a new recording used to silently orphan an in-progress
        # one: its frame count would just freeze with no event telling
        # anyone it stopped growing. Auto-finalize it instead, so it becomes
        # a normal, complete, listed capture rather than a stuck one.
        if self._active_capture is not None:
            self.stop_capture()

        name = self._unique_capture_name(name)
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
    def _prune_finished(self) -> None:
        # RunningAttack objects never get removed on their own once they
        # finish (list_running just filters them out), so a long session
        # with many short attacks would otherwise leak them forever.
        finished = [aid for aid, a in self.running.items() if a.status != "running"]
        for aid in finished:
            del self.running[aid]

    def start(self, kind: str, params: dict) -> dict:
        self._prune_finished()

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
        # An attack that already finished on its own (duration elapsed,
        # replay ended) carries a meaningful terminal status like
        # "completed" -- only overwrite it with "stopped" if it was
        # actually still running when this was called.
        if attack.status == "running":
            attack.stop()
        return attack.to_dict()

    def list_running(self) -> list:
        # Only surface attacks still actually running -- finished/stopped/
        # errored ones are dropped so the console doesn't accumulate stale
        # "Stop" buttons for attacks that already ended on their own.
        return [a.to_dict() for a in self.running.values() if a.status == "running"]
