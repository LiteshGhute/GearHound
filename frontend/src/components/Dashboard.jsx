import { useCallback } from "react";
import Gauge from "./Gauge.jsx";

const DOOR_LABELS = ["FL", "FR", "RL", "RR"];

function useHold(onDown, onUp) {
  return {
    onMouseDown: onDown,
    onMouseUp: onUp,
    onMouseLeave: onUp,
    onTouchStart: (e) => { e.preventDefault(); onDown(); },
    onTouchEnd: (e) => { e.preventDefault(); onUp(); },
  };
}

export default function Dashboard({ carState, busCongestion, sendControl }) {
  const { speed, rpm, fuel, doors, turn_left, turn_right, headlights, horn } = carState;

  const throttleDown = useCallback(() => sendControl("throttle", { value: 1 }), [sendControl]);
  const throttleUp = useCallback(() => sendControl("throttle", { value: 0 }), [sendControl]);
  const brakeDown = useCallback(() => sendControl("throttle", { value: -1 }), [sendControl]);
  const brakeUp = useCallback(() => sendControl("throttle", { value: 0 }), [sendControl]);

  const leftDown = useCallback(() => sendControl("turning", { value: -1 }), [sendControl]);
  const leftUp = useCallback(() => sendControl("turning", { value: 0 }), [sendControl]);
  const rightDown = useCallback(() => sendControl("turning", { value: 1 }), [sendControl]);
  const rightUp = useCallback(() => sendControl("turning", { value: 0 }), [sendControl]);

  const toggleDoor = (idx) => {
    const locked = doors[idx] === 1;
    sendControl("door", { index: idx, locked: !locked });
  };

  const toggleHeadlights = () => sendControl("headlights", { value: headlights ? 0 : 1 });

  const hornDown = useHold(
    () => sendControl("horn", { value: 1 }),
    () => sendControl("horn", { value: 0 })
  );

  return (
    <div className="dashboard-panel">
      {busCongestion > 0.05 && (
        <div className="congestion-banner">
          ⚠ Bus congestion {Math.round(busCongestion * 100)}%, legitimate signals may be dropped
        </div>
      )}

      <div className="gauge-row">
        <Gauge label="SPEED" value={speed} max={220} unit="km/h" accent="var(--accent)" danger={190} />
        <Gauge label="RPM" value={rpm} max={7000} unit="rpm x1" accent="var(--accent-2)" danger={6200} />
        <Gauge label="FUEL" value={fuel} max={100} unit="%" accent="var(--fuel)" />
      </div>

      <div className="signal-row">
        <button
          className={`signal-btn left ${turn_left ? "active" : ""}`}
          {...useHold(leftDown, leftUp)}
        >
          ◀ LEFT
        </button>
        <button
          className={`light-btn ${headlights ? "active" : ""}`}
          onClick={toggleHeadlights}
        >
          ☀ LIGHTS
        </button>
        <button
          className={`signal-btn right ${turn_right ? "active" : ""}`}
          {...useHold(rightDown, rightUp)}
        >
          RIGHT ▶
        </button>
      </div>

      <div className="car-topdown">
        <div className="car-body">
          <div className="windshield" />
          {doors.map((locked, i) => (
            <button
              key={i}
              className={`door door-${i} ${locked ? "locked" : "unlocked"}`}
              onClick={() => toggleDoor(i)}
              title={`${DOOR_LABELS[i]} door: ${locked ? "locked" : "unlocked"} (click to toggle)`}
            >
              {DOOR_LABELS[i]}
            </button>
          ))}
        </div>
      </div>

      <div className="pedal-row">
        <button className="pedal brake" {...useHold(brakeDown, brakeUp)}>
          BRAKE
        </button>
        <button className="pedal horn" {...hornDown} style={{ opacity: horn ? 1 : 0.75 }}>
          🔊 HORN
        </button>
        <button className="pedal accel" {...useHold(throttleDown, throttleUp)}>
          ACCELERATE
        </button>
      </div>
    </div>
  );
}
