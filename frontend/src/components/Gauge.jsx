const START_ANGLE = -220; // degrees
const SWEEP = 260;

function polarToCartesian(cx, cy, r, angleDeg) {
  const rad = ((angleDeg - 90) * Math.PI) / 180;
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
}

function arcPath(cx, cy, r, startAngle, endAngle) {
  const start = polarToCartesian(cx, cy, r, endAngle);
  const end = polarToCartesian(cx, cy, r, startAngle);
  const largeArc = endAngle - startAngle <= 180 ? "0" : "1";
  return `M ${start.x} ${start.y} A ${r} ${r} 0 ${largeArc} 0 ${end.x} ${end.y}`;
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
  const valueAngle = START_ANGLE + SWEEP * pct;
  const isDanger = danger !== undefined && value >= danger;

  return (
    <div className="gauge" style={{ width: size }}>
      <svg viewBox={`0 0 ${size} ${size}`} width={size} height={size}>
        <path
          d={arcPath(cx, cy, r, START_ANGLE, START_ANGLE + SWEEP)}
          className="gauge-track"
        />
        <path
          d={arcPath(cx, cy, r, START_ANGLE, valueAngle)}
          stroke={isDanger ? "var(--danger)" : accent}
          className="gauge-value"
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
