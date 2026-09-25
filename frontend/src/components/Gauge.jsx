const START_ANGLE = -220; // degrees
const SWEEP = 260;

function polarToCartesian(cx, cy, r, angleDeg) {
  const rad = ((angleDeg - 90) * Math.PI) / 180;
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
}

// One fixed path for the whole gauge sweep, used for BOTH the track and the
// value stroke. Its `d` never changes with the value -- only stroke-dashoffset
// does, via CSS -- which is what makes the animation safe. Browsers don't
// understand SVG arcs semantically; transitioning `d` directly interpolates
// the raw numbers, and when the arc/large-arc flags or endpoints jump between
// frames (as they do continuously while accelerating or decelerating), that
// naive interpolation briefly renders a broken, overshooting arc before
// snapping back once updates stop. stroke-dashoffset is a single number, so
// CSS can animate it correctly with no such artifact.
function fullArcPath(cx, cy, r) {
  const start = polarToCartesian(cx, cy, r, START_ANGLE);
  const end = polarToCartesian(cx, cy, r, START_ANGLE + SWEEP);
  const largeArc = SWEEP <= 180 ? "0" : "1";
  return `M ${start.x} ${start.y} A ${r} ${r} 0 ${largeArc} 1 ${end.x} ${end.y}`;
}

export default function Gauge({
  label,
  value,
  max,
  unit = "",
  accent = "var(--accent)",
  danger,
  size = 168,
}) {
  const cx = size / 2;
  const cy = size / 2;
  const r = size / 2 - 14;
  const clamped = Math.max(0, Math.min(value, max));
  const pct = clamped / max;
  const isDanger = danger !== undefined && value >= danger;

  const path = fullArcPath(cx, cy, r);
  const arcLength = r * ((SWEEP * Math.PI) / 180);
  const dashOffset = arcLength * (1 - pct);

  return (
    <div className="gauge" style={{ width: size }}>
      <svg viewBox={`0 0 ${size} ${size}`} width={size} height={size}>
        <path d={path} className="gauge-track" />
        <path
          d={path}
          stroke={isDanger ? "var(--danger)" : accent}
          className="gauge-value"
          strokeDasharray={arcLength}
          strokeDashoffset={dashOffset}
        />
        <text x={cx} y={cy - 2} textAnchor="middle" className="gauge-number">
          {Math.round(clamped)}
        </text>
        <text x={cx} y={cy + 20} textAnchor="middle" className="gauge-unit">
          {unit}
        </text>
      </svg>
      <div className="gauge-label">{label}</div>
    </div>
  );
}
