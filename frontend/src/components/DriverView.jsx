import { useVehicleControls } from "../hooks/useVehicleControls.js";

function speedToDuration(speed, maxSpeed, minDuration, maxDuration) {
  const pct = Math.max(0, Math.min(1, speed / maxSpeed));
  return maxDuration - pct * (maxDuration - minDuration);
}

export default function DriverView({ carState, sendControl }) {
  const { speed, rpm, fuel, doors, turn_left, turn_right, headlights, horn } = carState;
  const { pressed, handlers } = useVehicleControls(sendControl);

  const moving = speed > 0.5;
  const roadDuration = speedToDuration(speed, 220, 0.18, 1.6);
  const rpmPct = Math.min(100, (rpm / 7000) * 100);
  const speedPct = Math.min(100, (speed / 220) * 100);
  const toggleHeadlights = () => sendControl("headlights", { value: headlights ? 0 : 1 });

  return (
    <div className={`driver-view ${headlights ? "lights-on" : "lights-off"}`}>
      <div className="dv-sky" />

      <div className="dv-road-wrap">
        <div
          className="dv-road"
          style={{ animationDuration: `${roadDuration}s`, animationPlayState: moving ? "running" : "paused" }}
        >
          <div className="dv-center-line" />
        </div>
        <div className="dv-edge dv-edge-left" />
        <div className="dv-edge dv-edge-right" />
      </div>

      {headlights && (
        <>
          <div className="dv-headlight-cone left" />
          <div className="dv-headlight-cone right" />
        </>
      )}

      {pressed.brake && <div className="dv-brake-vignette" />}
      {horn && <div className="dv-horn-ripple" />}

      <div className={`dv-indicator dv-indicator-left ${turn_left ? "on" : ""}`}>&#9664;</div>
      <div className={`dv-indicator dv-indicator-right ${turn_right ? "on" : ""}`}>&#9654;</div>

      <div className="dv-mirror dv-mirror-left">
        <span className={doors[0] ? "locked" : "unlocked"}>{doors[0] ? "LOCK" : "OPEN"}</span>
      </div>
      <div className="dv-mirror dv-mirror-right">
        <span className={doors[1] ? "locked" : "unlocked"}>{doors[1] ? "LOCK" : "OPEN"}</span>
      </div>

      <div className="dv-hud">
        <div className="dv-hud-speed">
          <span className="dv-hud-speed-num">{Math.round(speed)}</span>
          <span className="dv-hud-speed-unit">km/h</span>
        </div>
        <div className="dv-hud-bars">
          <div className="dv-bar">
            <div className="dv-bar-label">RPM</div>
            <div className="dv-bar-track">
              <div className={`dv-bar-fill rpm ${rpmPct > 88 ? "redline" : ""}`} style={{ width: `${rpmPct}%` }} />
            </div>
          </div>
          <div className="dv-bar">
            <div className="dv-bar-label">FUEL</div>
            <div className="dv-bar-track">
              <div className="dv-bar-fill fuel" style={{ width: `${fuel}%` }} />
            </div>
          </div>
        </div>
      </div>

      <div className="dv-cockpit">
        <div className="dv-dash-glow" style={{ opacity: 0.3 + speedPct / 200 }} />
        <div className="dv-wheel">
          <div className="dv-wheel-hub" />
          <div className="dv-wheel-spoke spoke-1" />
          <div className="dv-wheel-spoke spoke-2" />
          <div className="dv-wheel-spoke spoke-3" />
        </div>
      </div>

      <div className="dv-controls">
        <button className="dv-btn left" {...handlers.left}>
          TURN L
        </button>
        <button className="dv-btn brake" {...handlers.brake}>
          BRAKE
        </button>
        <button className={`dv-btn lights ${headlights ? "active" : ""}`} onClick={toggleHeadlights}>
          LIGHTS
        </button>
        <button className="dv-btn horn" {...handlers.horn}>
          HORN
        </button>
        <button className="dv-btn accel" {...handlers.accelerate}>
          GAS
        </button>
        <button className="dv-btn right" {...handlers.right}>
          TURN R
        </button>
      </div>
    </div>
  );
}
