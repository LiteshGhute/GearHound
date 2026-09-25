"""
CAN bus wrapper.

Wraps python-can so the rest of the app never touches `can.Bus` directly.
Two backends are supported, chosen by the CAN_BUSTYPE env var:

  virtual   - pure Python, works on macOS/Windows/Linux with no kernel
              support needed. Used for local development of GearHound
              itself (this is how the UI/attacks get built and tested
              without a Linux box).
  socketcan - real Linux SocketCAN device (e.g. vcan0), used in the
              shipped Docker image, same as GearGoat.

Everything above this layer (state tracking, attacks, Socket.IO) only
calls send_frame()/subscribe() and doesn't know or care which backend
is active.
"""

import os
import threading
import time

import can

CAN_BUSTYPE = os.environ.get("CAN_BUSTYPE", "virtual")
CAN_CHANNEL = os.environ.get("CAN_CHANNEL", "gearhound" if CAN_BUSTYPE == "virtual" else "vcan0")


class CanBus:
    def __init__(self, bustype: str = CAN_BUSTYPE, channel: str = CAN_CHANNEL):
        self.bustype = bustype
        self.channel = channel
        # A single CanBus handle both writes legitimate/attack frames AND
        # decodes whatever is on the bus (see state.py) -- unlike GearGoat's
        # split controller/simulator processes, there's only one handle
        # here, so it must hear its own transmissions echoed back, same as
        # a real CAN transceiver does off the wire.
        kwargs = {"channel": channel, "bustype": bustype, "receive_own_messages": True}
        self._bus = can.interface.Bus(**kwargs)
        self._listeners = []
        self._lock = threading.Lock()
        # 0.0 = clear bus, 1.0 = fully saturated. Keyed by attack id rather
        # than a single shared number, so two concurrent flood attacks each
        # contribute independently: stopping one doesn't erase the other's
        # congestion (it used to, when this was a single float any flood
        # could unconditionally zero out in its own cleanup).
        self._congestion_lock = threading.Lock()
        self._congestion_sources: dict[str, float] = {}
        self._rx_thread = threading.Thread(target=self._recv_loop, daemon=True)
        self._running = True
        self._rx_thread.start()

    @property
    def congestion(self) -> float:
        with self._congestion_lock:
            if not self._congestion_sources:
                return 0.0
            return max(self._congestion_sources.values())

    def set_congestion(self, source_id: str, value: float) -> None:
        """Register (or clear, with value <= 0) one attack's contribution
        to bus congestion. The effective `congestion` is the max across all
        active sources, so concurrent floods combine sensibly and each can
        be stopped independently without disturbing the others."""
        with self._congestion_lock:
            if value <= 0:
                self._congestion_sources.pop(source_id, None)
            else:
                self._congestion_sources[source_id] = value

    def send(self, arbitration_id: int, data: bytes) -> None:
        msg = can.Message(arbitration_id=arbitration_id, data=data, is_extended_id=False)
        self._bus.send(msg)

    def subscribe(self, callback) -> None:
        """callback(arbitration_id: int, data: bytes, timestamp: float)"""
        with self._lock:
            self._listeners.append(callback)

    def _recv_loop(self) -> None:
        while self._running:
            try:
                msg = self._bus.recv(timeout=1.0)
            except Exception:
                time.sleep(0.1)
                continue
            if msg is None:
                continue
            with self._lock:
                listeners = list(self._listeners)
            for cb in listeners:
                try:
                    cb(msg.arbitration_id, bytes(msg.data), msg.timestamp or time.time())
                except Exception:
                    pass

    def shutdown(self) -> None:
        self._running = False
        try:
            self._bus.shutdown()
        except Exception:
            pass


def pack_uint(value: int, length: int) -> bytes:
    value = max(0, int(value)) & (2 ** (8 * length) - 1)
    return value.to_bytes(length, byteorder="big")


def unpack_uint(data: bytes, offset: int, length: int) -> int:
    chunk = data[offset:offset + length]
    if len(chunk) < length:
        return 0
    return int.from_bytes(chunk, byteorder="big")
