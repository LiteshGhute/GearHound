"""
Simulated vehicle state.

Mirrors how a real instrument cluster works: it has no idea whether a frame
on the bus came from a legitimate ECU or an attacker's `cansend` -- it just
decodes whatever arrives. That's what makes the attack console's effects
show up live on the dashboard, same as the underlying physics of a real
CAN bus.
"""

import random
import threading

from can_bus import CanBus, pack_uint, unpack_uint
from vehicles.profiles import VehicleProfile, get_profile, DEFAULT_PROFILE_KEY

MAX_SPEED = 220     # kph
MAX_RPM = 8000
DOOR_COUNT = 4


class VehicleState:
    def __init__(self, bus: CanBus, profile_key: str = DEFAULT_PROFILE_KEY):
        self.bus = bus
        self.lock = threading.RLock()
        self.frame_buffers: dict[int, bytearray] = {}
        self.profile: VehicleProfile = get_profile(profile_key)

        self.speed = 0
        self.rpm = 800  # idle
        self.fuel = 100
        self.doors = [1, 1, 1, 1]  # 1 = locked
        self.turn_left = False
        self.turn_right = False
        self.headlights = False
        self.horn = False

        self.bus.subscribe(self._on_frame)

    # ---- outbound: legitimate dashboard control writes a signal -----------
    def write_signal(self, name: str, value: int) -> None:
        with self.lock:
            spec = self.profile.signals.get(name)
            if spec is None:
                return
            buf = self.frame_buffers.setdefault(spec.arb_id, bytearray(8))
            packed = pack_uint(value, spec.length)
            buf[spec.byte:spec.byte + spec.length] = packed
            frame_copy = bytes(buf)
        self.bus.send(spec.arb_id, frame_copy)

    def set_profile(self, profile_key: str) -> None:
        with self.lock:
            self.profile = get_profile(profile_key)
            self.frame_buffers = {}
            self.speed = 0
            self.rpm = 800
            self.fuel = 100
            self.doors = [1, 1, 1, 1]
            self.turn_left = False
            self.turn_right = False
            self.headlights = False
            self.horn = False

    # ---- inbound: any frame on the bus updates the cluster ----------------
    def _on_frame(self, arb_id: int, data: bytes, timestamp: float) -> None:
        # Under a flood attack, a real bus would lose arbitration on lower-
        # priority (higher-ID) frames. Model that by probabilistically
        # dropping legitimate frames in proportion to bus congestion.
        if self.bus.congestion > 0 and random.random() < self.bus.congestion:
            return
        with self.lock:
            id_map = self.profile.id_map()
            names = id_map.get(arb_id)
            if not names:
                return
            for name in names:
                spec = self.profile.signals[name]
                value = unpack_uint(data, spec.byte, spec.length)
                self._apply_decoded(name, value)

    def _apply_decoded(self, name: str, value: int) -> None:
        if name == "speed":
            self.speed = min(value, MAX_SPEED)
        elif name == "rpm":
            self.rpm = min(value, MAX_RPM)
        elif name == "fuel":
            self.fuel = min(value, 100)
        elif name == "doors":
            for i in range(DOOR_COUNT):
                self.doors[i] = 1 if (value >> i) & 1 else 0
        elif name == "turn_signal":
            self.turn_left = bool(value & 0x1)
            self.turn_right = bool(value & 0x2)
        elif name == "headlights":
            self.headlights = bool(value & 0x1)
        elif name == "horn":
            self.horn = bool(value & 0x1)

    def snapshot(self) -> dict:
        with self.lock:
            return {
                "profile": self.profile.key,
                "speed": round(self.speed, 1),
                "rpm": round(self.rpm),
                "fuel": round(self.fuel),
                "doors": list(self.doors),
                "turn_left": self.turn_left,
                "turn_right": self.turn_right,
                "headlights": self.headlights,
                "horn": self.horn,
            }
