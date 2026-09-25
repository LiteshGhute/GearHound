import Gauge from "./Gauge.jsx";
import { useVehicleControls } from "../hooks/useVehicleControls.js";

const DOOR_LABELS = ["FL", "FR", "RL", "RR"];

// Road scroll and wheel spin durations get FASTER (shorter) as speed rises;
// clamped so idle isn't frozen-stiff and top speed isn't a blur.
function speedToDuration(speed, maxSpeed, minDuration, maxDuration) {
  const pct = Math.max(0, Math.min(1, speed / maxSpeed));
  return maxDuration - pct * (maxDuration - minDuration);
}

export default function Dashboard({ carState, busCongestion, sendControl }) {
  const { speed, rpm, fuel, doors, turn_left, turn_right, headlights, horn } = carState;
  const { pressed, handlers } = useVehicleControls(sendControl);

  const moving = speed > 0.5;
  const roadDuration = speedToDuration(speed, 220, 0.25, 2.2);
  const wheelDuration = speedToDuration(speed, 220, 0.12, 1.1);
  const engineRevving = rpm > 2200;

  const toggleDoor = (idx) => {
    const locked = doors[idx] === 1;
    sendControl("door", { index: idx, locked: !locked });
  };

  const toggleHeadlights = () => sendControl("headlights", { value: headlights ? 0 : 1 });

  return (
    <div className="dashboard-panel">
      {busCongestion > 0.05 && (
        <div className="congestion-banner">
          Bus congestion {Math.round(busCongestion * 100)}%, legitimate signals may be dropped
        </div>
      )}

      <div className="gauge-row">
        <Gauge label="SPEED" value={speed} max={220} unit="km/h" accent="var(--accent)" danger={190} />
        <Gauge label="RPM" value={rpm} max={7000} unit="rpm x1" accent="var(--accent-2)" danger={6200} />
        <Gauge label="FUEL" value={fuel} max={100} unit="%" accent="var(--fuel)" />
      </div>

      <div className="signal-row">
        <button className={`signal-btn left ${turn_left ? "active" : ""}`} {...handlers.left}>
          LEFT
        </button>
        <button className={`light-btn ${headlights ? "active" : ""}`} onClick={toggleHeadlights}>
          LIGHTS
        </button>
        <button className={`signal-btn right ${turn_right ? "active" : ""}`} {...handlers.right}>
          RIGHT
        </button>
      </div>

      <div className="car-topdown">
        <div className="road">
          <div
            className="road-lane"
            style={{
              animationDuration: `${roadDuration}s`,
              animationPlayState: moving ? "running" : "paused",
            }}
          />
        </div>

        <div className={`car-body ${engineRevving ? "revving" : ""} ${pressed.brake ? "braking" : ""}`}>
          <div className="windshield" />

          <div className={`beam left ${headlights ? "on" : ""}`} />
          <div className={`beam right ${headlights ? "on" : ""}`} />

          <div className={`indicator-lamp left ${turn_left ? "on" : ""}`} />
          <div className={`indicator-lamp right ${turn_right ? "on" : ""}`} />

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

          <div
            className="wheel wheel-fl"
            style={{ animationDuration: `${wheelDuration}s`, animationPlayState: moving ? "running" : "paused" }}
          />
          <div
            className="wheel wheel-fr"
            style={{ animationDuration: `${wheelDuration}s`, animationPlayState: moving ? "running" : "paused" }}
          />
          <div
            className="wheel wheel-rl"
            style={{ animationDuration: `${wheelDuration}s`, animationPlayState: moving ? "running" : "paused" }}
          />
          <div
            className="wheel wheel-rr"
            style={{ animationDuration: `${wheelDuration}s`, animationPlayState: moving ? "running" : "paused" }}
          />

          <div className={`brake-light left ${pressed.brake ? "on" : ""}`} />
          <div className={`brake-light right ${pressed.brake ? "on" : ""}`} />

          {horn && (
            <>
              <div className="horn-ring" />
              <div className="horn-ring delay" />
            </>
          )}
        </div>

        {moving && <div className="speed-lines" style={{ opacity: Math.min(1, speed / 140) }} />}
      </div>

      <div className="pedal-row">
        <button className="pedal brake" {...handlers.brake}>
          BRAKE
        </button>
        <button className="pedal horn" {...handlers.horn} style={{ opacity: horn ? 1 : 0.75 }}>
          HORN
        </button>
        <button className="pedal accel" {...handlers.accelerate}>
          ACCELERATE
        </button>
      </div>
    </div>
  );
}
