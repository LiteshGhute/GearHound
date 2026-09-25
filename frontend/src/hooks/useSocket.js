import { useCallback, useEffect, useRef, useState } from "react";
import { io } from "socket.io-client";

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "http://localhost:4000";
const TRAFFIC_BUFFER_CAP = 400;
const LOG_BUFFER_CAP = 200;

// socket.io-client only pops a trailing argument as an ack callback when it
// is actually a function -- an explicit `undefined` is still sent as a
// second literal event argument, which breaks single-argument server
// handlers. Centralize the "only pass it if callable" guard here.
function emit(socket, event, data, cb) {
  if (typeof cb === "function") {
    socket?.emit(event, data, cb);
  } else {
    socket?.emit(event, data);
  }
}

const EMPTY_STATE = {
  profile: "sedan",
  speed: 0,
  rpm: 800,
  fuel: 100,
  doors: [1, 1, 1, 1],
  turn_left: false,
  turn_right: false,
  headlights: false,
  horn: false,
};

export function useSocket() {
  const socketRef = useRef(null);
  const [connected, setConnected] = useState(false);
  const [carState, setCarState] = useState(EMPTY_STATE);
  const [vehicles, setVehicles] = useState({ profiles: [], active: "sedan" });
  const [traffic, setTraffic] = useState([]);
  const [busCongestion, setBusCongestion] = useState(0);
  const [attacksRunning, setAttacksRunning] = useState([]);
  const [captures, setCaptures] = useState([]);
  const [attackLog, setAttackLog] = useState([]);

  useEffect(() => {
    const socket = io(BACKEND_URL, { transports: ["websocket", "polling"] });
    socketRef.current = socket;

    socket.on("connect", () => setConnected(true));
    socket.on("disconnect", () => setConnected(false));

    socket.on("car_state", (data) => setCarState(data));
    socket.on("vehicles", (data) => setVehicles(data));
    socket.on("attacks_running", (data) => setAttacksRunning(data));
    socket.on("captures", (data) => setCaptures(data));

    socket.on("traffic", (payload) => {
      setBusCongestion(payload.bus_congestion || 0);
      setTraffic((prev) => {
        const next = [...prev, ...payload.frames];
        return next.length > TRAFFIC_BUFFER_CAP
          ? next.slice(next.length - TRAFFIC_BUFFER_CAP)
          : next;
      });
    });

    socket.on("attack_event", (event) => {
      // "status" fires every ~0.5s while an attack runs (to keep the live
      // frame counter fresh) but only transitions worth narrating in the
      // log are the terminal ones -- otherwise the panel fills with
      // "status: running" noise every half second.
      const isTerminalStatus = event.type === "status" && event.status !== "running";
      if (event.type === "log" || isTerminalStatus) {
        setAttackLog((prev) => {
          const next = [...prev, event];
          return next.length > LOG_BUFFER_CAP
            ? next.slice(next.length - LOG_BUFFER_CAP)
            : next;
        });
      }
    });

    return () => socket.disconnect();
  }, []);

  const sendControl = useCallback((signal, payload = {}) => {
    socketRef.current?.emit("control", { signal, ...payload });
  }, []);

  const selectVehicle = useCallback((profile) => {
    setTraffic([]);
    socketRef.current?.emit("vehicle_select", { profile });
  }, []);

  const startAttack = useCallback((kind, params, cb) => {
    // socket.io-client only treats a trailing FUNCTION as an ack callback.
    // Passing an explicit `undefined` (the common case here, since callers
    // rarely need the ack) still counts as a real argument and gets sent
    // as a second positional value in the event payload, which crashes
    // the single-argument Flask-SocketIO handler server-side. Only emit
    // the callback slot when it's actually a function.
    emit(socketRef.current, "attack_start", { kind, params }, cb);
  }, []);

  const stopAttack = useCallback((id, cb) => {
    emit(socketRef.current, "attack_stop", { id }, cb);
  }, []);

  const startCapture = useCallback((name, cb) => {
    emit(socketRef.current, "capture_start", { name }, cb);
  }, []);

  const stopCapture = useCallback((cb) => {
    emit(socketRef.current, "capture_stop", {}, cb);
  }, []);

  return {
    connected,
    carState,
    vehicles,
    traffic,
    busCongestion,
    attacksRunning,
    captures,
    attackLog,
    sendControl,
    selectVehicle,
    startAttack,
    stopAttack,
    startCapture,
    stopCapture,
  };
}
