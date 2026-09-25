"""
Fuzzing attack: blast random/mutated arbitration IDs and payloads across a
range to discover undocumented signals -- automates what GearGoat's manual
does by hand with cansniffer's "freeze unchanging bytes" trick.
"""

import random


def run_fuzz(attack, bus) -> None:
    id_min = int(attack.params.get("id_min", 0x000))
    id_max = int(attack.params.get("id_max", 0x7FF))
    rate_hz = max(1, int(attack.params.get("rate_hz", 20)))
    mode = attack.params.get("mode", "random")  # "random" | "incremental"
    duration = attack.params.get("duration")  # seconds, None = until stopped

    if id_min > id_max:
        attack.log(f"invalid range: id_min (0x{id_min:03X}) is above id_max (0x{id_max:03X})")
        return

    attack.log(
        f"fuzzing IDs 0x{id_min:03X}-0x{id_max:03X} @ {rate_hz}Hz mode={mode}"
    )

    interval = 1.0 / rate_hz
    current_id = id_min

    while not attack.stop_event.is_set():
        if duration is not None and (attack.frames_sent * interval) >= float(duration):
            break

        if mode == "incremental":
            arb_id = current_id
            current_id = id_min if current_id >= id_max else current_id + 1
        else:
            arb_id = random.randint(id_min, id_max)

        data = bytes(random.randint(0, 255) for _ in range(8))
        bus.send(arb_id, data)
        attack.note_frame(arb_id, data)

        attack.stop_event.wait(interval)

    attack.log(f"fuzzing stopped after {attack.frames_sent} frames")
