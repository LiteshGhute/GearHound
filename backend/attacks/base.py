"""Shared plumbing for every attack module: background thread + live log feed."""

import threading
import time
import uuid


def param_int(params: dict, key: str, default: int) -> int:
    """dict.get(key, default) only falls back to `default` when the key is
    ABSENT -- a client that sends the key with a JSON `null` gets `None`
    back instead, and int(None) crashes the attack thread with a raw
    TypeError surfaced verbatim in the Attack Log. Treat "present but
    null" the same as "absent"."""
    value = params.get(key)
    return default if value is None else int(value)


class RunningAttack:
    """One in-flight attack instance. Runs `worker` in a daemon thread until
    stopped, and streams structured log lines back through `on_event`."""

    def __init__(self, kind: str, params: dict, worker, on_event):
        self.id = uuid.uuid4().hex[:8]
        self.kind = kind
        self.params = params
        self.on_event = on_event
        self.started_at = time.time()
        self.stop_event = threading.Event()
        self.frames_sent = 0
        self.status = "running"
        self._last_frame_emit = 0.0
        self._frame_emit_interval = 0.1  # cap "frame" events at 10/sec per attack
        self._last_status_emit = 0.0
        self._status_emit_interval = 0.5  # live frames_sent counter in the UI
        self._thread = threading.Thread(
            target=self._run, args=(worker,), daemon=True
        )

    def start(self) -> None:
        self._thread.start()

    def _run(self, worker) -> None:
        try:
            worker(self)
            if self.status == "running":
                self.status = "completed"
        except Exception as exc:  # noqa: BLE001
            self.status = "error"
            self.log(f"attack error: {exc}")
        finally:
            if self.status == "running":
                self.status = "completed"
            self.emit_status()

    def stop(self) -> None:
        self.stop_event.set()
        self.status = "stopped"

    def log(self, message: str) -> None:
        self.on_event({
            "type": "log",
            "attack_id": self.id,
            "kind": self.kind,
            "message": message,
            "ts": time.time(),
        })

    def note_frame(self, arb_id: int, data: bytes) -> None:
        self.frames_sent += 1
        now = time.time()

        # A slow trickle (replay, low-rate fuzz) never hits the frame-emit
        # throttle below, so the console's live frame counter would sit
        # frozen for seconds at a time. Emit a lightweight status update on
        # its own cadence, independent of the frame throttle.
        if now - self._last_status_emit >= self._status_emit_interval:
            self._last_status_emit = now
            self.emit_status()

        # High-rate attacks (flood, fuzz) can emit hundreds of frames/sec --
        # throttle the UI-facing event so the socket stays responsive. The
        # live traffic monitor still sees every frame via its own bus
        # subscription, independent of this rate limit.
        if now - self._last_frame_emit < self._frame_emit_interval:
            return
        self._last_frame_emit = now
        self.on_event({
            "type": "frame",
            "attack_id": self.id,
            "kind": self.kind,
            "arb_id": arb_id,
            "data": list(data),
            "ts": now,
        })

    def emit_status(self) -> None:
        self.on_event({
            "type": "status",
            "attack_id": self.id,
            "kind": self.kind,
            "status": self.status,
            "frames_sent": self.frames_sent,
            "ts": time.time(),
        })

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "params": self.params,
            "status": self.status,
            "frames_sent": self.frames_sent,
            "started_at": self.started_at,
        }
