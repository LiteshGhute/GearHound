import { useState } from "react";

const SIGNAL_OPTIONS = [
  { key: "speed", label: "Speed", max: 220 },
  { key: "rpm", label: "RPM", max: 7000 },
  { key: "fuel", label: "Fuel", max: 100 },
  { key: "doors", label: "Doors (bitmask)", max: 15 },
  { key: "turn_signal", label: "Turn signal (bitmask)", max: 3 },
  { key: "headlights", label: "Headlights", max: 1 },
  { key: "horn", label: "Horn", max: 1 },
];

function AttackCard({ title, subtitle, children }) {
  return (
    <div className="attack-card">
      <div className="attack-card-title">{title}</div>
      <div className="attack-card-subtitle">{subtitle}</div>
      {children}
    </div>
  );
}

export default function AttackConsole({
  attacksRunning,
  captures,
  attackLog,
  startAttack,
  stopAttack,
  startCapture,
  stopCapture,
}) {
  const [recording, setRecording] = useState(false);
  const [captureName, setCaptureName] = useState("capture-1");

  const [fuzzParams, setFuzzParams] = useState({ id_min: "0x000", id_max: "0x2FF", rate_hz: 25, mode: "random", duration: 10 });
  const [floodParams, setFloodParams] = useState({ arb_id: "0x000", rate_hz: 400, duration: 8 });
  const [spoofParams, setSpoofParams] = useState({ signal: "speed", value: 200, rate_hz: 40, duration: 8 });
  const [replayParams, setReplayParams] = useState({ capture: "", loop: false, speed: 1 });

  const parseHex = (v) => (typeof v === "string" && v.trim().toLowerCase().startsWith("0x") ? parseInt(v, 16) : parseInt(v, 10) || 0);
  // `Number(x) || undefined` treats 0 as falsy and silently turns an
  // intentional "duration: 0" into "unlimited" -- same bug the backend had.
  // An empty field is the only case that should mean "no limit".
  const numOrUndefined = (v) => (v === "" || v === null || v === undefined ? undefined : Number(v));

  const runningByKind = (kind) => attacksRunning.filter((a) => a.kind === kind);

  const handleRecordToggle = () => {
    if (!recording) {
      startCapture(captureName);
      setRecording(true);
    } else {
      stopCapture();
      setRecording(false);
    }
  };

  return (
    <div className="attack-console">
      <div className="panel-header">
        <h2>Attack Console</h2>
      </div>

      <div className="attack-grid">
        <AttackCard title="Capture & Replay" subtitle="Record real traffic, replay it back verbatim">
          <div className="field-row">
            <input value={captureName} onChange={(e) => setCaptureName(e.target.value)} placeholder="capture name" />
            <button className={`btn ${recording ? "danger" : "primary"}`} onClick={handleRecordToggle}>
              {recording ? "⏹ Stop recording" : "● Record"}
            </button>
          </div>
          <div className="field-row">
            <select value={replayParams.capture} onChange={(e) => setReplayParams({ ...replayParams, capture: e.target.value })}>
              <option value="">select capture…</option>
              {captures.map((c) => (
                <option key={c.name} value={c.name}>
                  {c.name} ({c.frame_count} frames)
                </option>
              ))}
            </select>
            <label className="checkbox-label">
              <input type="checkbox" checked={replayParams.loop} onChange={(e) => setReplayParams({ ...replayParams, loop: e.target.checked })} />
              loop
            </label>
          </div>
          <div className="field-row">
            <button
              className="btn primary"
              disabled={!replayParams.capture}
              onClick={() => startAttack("replay", replayParams)}
            >
              ▶ Replay
            </button>
            {runningByKind("replay").map((a) => (
              <button key={a.id} className="btn danger" onClick={() => stopAttack(a.id)}>
                Stop ({a.frames_sent})
              </button>
            ))}
          </div>
        </AttackCard>

        <AttackCard title="Fuzzing" subtitle="Sweep arbitration IDs to discover undocumented signals">
          <div className="field-row">
            <input value={fuzzParams.id_min} onChange={(e) => setFuzzParams({ ...fuzzParams, id_min: e.target.value })} placeholder="min ID" />
            <input value={fuzzParams.id_max} onChange={(e) => setFuzzParams({ ...fuzzParams, id_max: e.target.value })} placeholder="max ID" />
          </div>
          <div className="field-row">
            <select value={fuzzParams.mode} onChange={(e) => setFuzzParams({ ...fuzzParams, mode: e.target.value })}>
              <option value="random">random</option>
              <option value="incremental">incremental</option>
            </select>
            <input
              type="number"
              value={fuzzParams.rate_hz}
              onChange={(e) => setFuzzParams({ ...fuzzParams, rate_hz: e.target.value })}
              placeholder="Hz"
            />
          </div>
          <div className="field-row">
            <input
              type="number"
              value={fuzzParams.duration}
              onChange={(e) => setFuzzParams({ ...fuzzParams, duration: e.target.value })}
              placeholder="duration (s, blank = unlimited)"
            />
          </div>
          <div className="field-row">
            <button
              className="btn primary"
              onClick={() =>
                startAttack("fuzz", {
                  id_min: parseHex(fuzzParams.id_min),
                  id_max: parseHex(fuzzParams.id_max),
                  rate_hz: Number(fuzzParams.rate_hz),
                  mode: fuzzParams.mode,
                  duration: numOrUndefined(fuzzParams.duration),
                })
              }
            >
              ▶ Start fuzzing
            </button>
            {runningByKind("fuzz").map((a) => (
              <button key={a.id} className="btn danger" onClick={() => stopAttack(a.id)}>
                Stop ({a.frames_sent})
              </button>
            ))}
          </div>
        </AttackCard>

        <AttackCard title="Flood / DoS" subtitle="Saturate the bus with a high-priority frame">
          <div className="field-row">
            <input value={floodParams.arb_id} onChange={(e) => setFloodParams({ ...floodParams, arb_id: e.target.value })} placeholder="arb ID (low = high priority)" />
            <input
              type="number"
              value={floodParams.rate_hz}
              onChange={(e) => setFloodParams({ ...floodParams, rate_hz: e.target.value })}
              placeholder="Hz"
            />
          </div>
          <div className="field-row">
            <input
              type="number"
              value={floodParams.duration}
              onChange={(e) => setFloodParams({ ...floodParams, duration: e.target.value })}
              placeholder="duration (s, blank = unlimited)"
            />
          </div>
          <div className="field-row">
            <button
              className="btn primary"
              onClick={() =>
                startAttack("flood", {
                  arb_id: parseHex(floodParams.arb_id),
                  rate_hz: Number(floodParams.rate_hz),
                  duration: numOrUndefined(floodParams.duration),
                })
              }
            >
              ▶ Start flood
            </button>
            {runningByKind("flood").map((a) => (
              <button key={a.id} className="btn danger" onClick={() => stopAttack(a.id)}>
                Stop ({a.frames_sent})
              </button>
            ))}
          </div>
        </AttackCard>

        <AttackCard title="Signal Spoofing" subtitle="Force a signal to a chosen value, overriding legit writes">
          <div className="field-row">
            <select value={spoofParams.signal} onChange={(e) => setSpoofParams({ ...spoofParams, signal: e.target.value })}>
              {SIGNAL_OPTIONS.map((s) => (
                <option key={s.key} value={s.key}>
                  {s.label}
                </option>
              ))}
            </select>
            <input
              type="number"
              value={spoofParams.value}
              onChange={(e) => setSpoofParams({ ...spoofParams, value: e.target.value })}
              placeholder="value"
            />
          </div>
          <div className="field-row">
            <input
              type="number"
              value={spoofParams.rate_hz}
              onChange={(e) => setSpoofParams({ ...spoofParams, rate_hz: e.target.value })}
              placeholder="Hz"
            />
            <input
              type="number"
              value={spoofParams.duration}
              onChange={(e) => setSpoofParams({ ...spoofParams, duration: e.target.value })}
              placeholder="duration (s, blank = unlimited)"
            />
          </div>
          <div className="field-row">
            <button
              className="btn primary"
              onClick={() =>
                startAttack("spoof", {
                  signal: spoofParams.signal,
                  value: Number(spoofParams.value),
                  rate_hz: Number(spoofParams.rate_hz),
                  duration: numOrUndefined(spoofParams.duration),
                })
              }
            >
              ▶ Start spoof
            </button>
            {runningByKind("spoof").map((a) => (
              <button key={a.id} className="btn danger" onClick={() => stopAttack(a.id)}>
                Stop ({a.frames_sent})
              </button>
            ))}
          </div>
        </AttackCard>
      </div>

      <div className="attack-log">
        <div className="panel-header">
          <h3>Attack Log</h3>
        </div>
        <div className="log-scroll">
          {attackLog
            .slice()
            .reverse()
            .map((e, i) => (
              <div key={i} className={`log-line log-${e.type}`}>
                <span className="log-kind">[{e.kind}]</span>{" "}
                {e.type === "log" ? e.message : `status: ${e.status}, frames sent: ${e.frames_sent}`}
              </div>
            ))}
          {attackLog.length === 0 && <div className="empty-hint">No attack activity yet…</div>}
        </div>
      </div>
    </div>
  );
}
