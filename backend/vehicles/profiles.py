"""
Vehicle ECU profiles.

Each profile defines the arbitration IDs and byte offsets a simulated vehicle
uses for every signal on the bus. Swapping the active profile changes the
whole "wiring" of the car without touching any other code -- exactly the kind
of variation a real pentester has to re-derive per make/model.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SignalSpec:
    """Where a signal lives on the bus: which frame, which byte(s)."""
    arb_id: int
    byte: int
    length: int = 1


@dataclass(frozen=True)
class VehicleProfile:
    key: str
    name: str
    description: str
    signals: dict = field(default_factory=dict)

    def signal(self, name: str) -> SignalSpec:
        return self.signals[name]

    def id_map(self) -> dict:
        """arb_id -> list of signal names sharing that frame."""
        out = {}
        for sig_name, spec in self.signals.items():
            out.setdefault(spec.arb_id, []).append(sig_name)
        return out


# --- Sedan: mirrors GearGoat's original wiring, plus new signals -----------
SEDAN = VehicleProfile(
    key="sedan",
    name="Sedan LX",
    description="Baseline profile, arbitration IDs match the classic GearGoat layout.",
    signals={
        "turn_signal": SignalSpec(arb_id=0x188, byte=0),
        "doors":       SignalSpec(arb_id=0x19B, byte=2),
        "speed":       SignalSpec(arb_id=0x244, byte=3, length=2),
        "rpm":         SignalSpec(arb_id=0x316, byte=0, length=2),
        "fuel":        SignalSpec(arb_id=0x372, byte=1),
        "headlights":  SignalSpec(arb_id=0x188, byte=4),
        "horn":        SignalSpec(arb_id=0x1A0, byte=0),
    },
)

# --- SUV: different IDs entirely, some signals share frames -----------------
SUV = VehicleProfile(
    key="suv",
    name="Trailhawk SUV",
    description="Different arbitration IDs than the Sedan; several signals share frames.",
    signals={
        "turn_signal": SignalSpec(arb_id=0x210, byte=1),
        "doors":       SignalSpec(arb_id=0x210, byte=3),   # shares frame with turn_signal
        "speed":       SignalSpec(arb_id=0x2C4, byte=2, length=2),
        "rpm":         SignalSpec(arb_id=0x2C4, byte=5, length=2),  # shares frame with speed
        "fuel":        SignalSpec(arb_id=0x3A8, byte=0),
        "headlights":  SignalSpec(arb_id=0x210, byte=6),
        "horn":        SignalSpec(arb_id=0x055, byte=0),
    },
)

# --- Truck: sparse, high arbitration IDs, wide byte offsets -----------------
TRUCK = VehicleProfile(
    key="truck",
    name="Ironhide Truck",
    description="Higher arbitration IDs and wider frames, closer to a heavy-vehicle bus layout.",
    signals={
        "turn_signal": SignalSpec(arb_id=0x4A1, byte=2),
        "doors":       SignalSpec(arb_id=0x512, byte=0),
        "speed":       SignalSpec(arb_id=0x520, byte=4, length=2),
        "rpm":         SignalSpec(arb_id=0x520, byte=1, length=2),
        "fuel":        SignalSpec(arb_id=0x600, byte=3),
        "headlights":  SignalSpec(arb_id=0x4A1, byte=5),
        "horn":        SignalSpec(arb_id=0x4F0, byte=0),
    },
)

PROFILES = {p.key: p for p in (SEDAN, SUV, TRUCK)}

DEFAULT_PROFILE_KEY = SEDAN.key


def get_profile(key: str) -> VehicleProfile:
    return PROFILES.get(key, PROFILES[DEFAULT_PROFILE_KEY])


def list_profiles() -> list:
    return [
        {"key": p.key, "name": p.name, "description": p.description}
        for p in PROFILES.values()
    ]
