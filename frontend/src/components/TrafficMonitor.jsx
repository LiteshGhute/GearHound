import { useMemo, useState } from "react";

const MAX_GROUPED_ROWS = 80;

function toHex(id) {
  return "0x" + id.toString(16).toUpperCase().padStart(3, "0");
}

function toByteHex(b) {
  return b.toString(16).toUpperCase().padStart(2, "0");
}

export default function TrafficMonitor({ traffic }) {
  const [mode, setMode] = useState("grouped"); // "grouped" | "log"
  const [frozen, setFrozen] = useState(false);
  const [frozenTraffic, setFrozenTraffic] = useState([]);
  const [filter, setFilter] = useState("");

  const activeTraffic = frozen ? frozenTraffic : traffic;

  const toggleFreeze = () => {
    if (!frozen) setFrozenTraffic(traffic);
    setFrozen((f) => !f);
  };

  const grouped = useMemo(() => {
    const map = new Map();
    for (const frame of activeTraffic) {
      const prev = map.get(frame.arb_id);
      const changedMask = prev
        ? frame.data.map((b, i) => (b !== prev.data[i] ? 1 : 0))
        : frame.data.map(() => 0);
      map.set(frame.arb_id, {
        arb_id: frame.arb_id,
        data: frame.data,
        changedMask,
        count: (prev?.count || 0) + 1,
        lastTs: frame.ts,
      });
    }
    return Array.from(map.values()).sort((a, b) => b.lastTs - a.lastTs).slice(0, MAX_GROUPED_ROWS);
  }, [activeTraffic]);

  const filteredGrouped = filter
    ? grouped.filter((r) => toHex(r.arb_id).toLowerCase().includes(filter.toLowerCase()))
    : grouped;

  const logRows = useMemo(() => {
    return filter
      ? activeTraffic.filter((f) => toHex(f.arb_id).toLowerCase().includes(filter.toLowerCase()))
      : activeTraffic;
  }, [activeTraffic, filter]);

  return (
    <div className="traffic-panel">
      <div className="panel-header">
        <h2>Live CAN Traffic</h2>
        <div className="panel-controls">
          <input
            className="filter-input"
            placeholder="filter by ID (e.g. 188)"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          />
          <div className="mode-toggle">
            <button className={mode === "grouped" ? "active" : ""} onClick={() => setMode("grouped")}>
              Grouped
            </button>
            <button className={mode === "log" ? "active" : ""} onClick={() => setMode("log")}>
              Log
            </button>
          </div>
          <button className={`freeze-btn ${frozen ? "active" : ""}`} onClick={toggleFreeze}>
            {frozen ? "▶ Resume" : "⏸ Freeze"}
          </button>
        </div>
      </div>

      {mode === "grouped" ? (
        <div className="traffic-table grouped">
          <div className="traffic-row header">
            <span className="col-id">ID</span>
            <span className="col-data">Data</span>
            <span className="col-count">Count</span>
          </div>
          <div className="traffic-scroll">
            {filteredGrouped.map((row) => (
              <div className="traffic-row" key={row.arb_id}>
                <span className="col-id">{toHex(row.arb_id)}</span>
                <span className="col-data">
                  {row.data.map((b, i) => (
                    <span key={i} className={`byte ${row.changedMask[i] ? "changed" : ""}`}>
                      {toByteHex(b)}
                    </span>
                  ))}
                </span>
                <span className="col-count">{row.count}</span>
              </div>
            ))}
            {filteredGrouped.length === 0 && <div className="empty-hint">No traffic yet…</div>}
          </div>
        </div>
      ) : (
        <div className="traffic-table log">
          <div className="traffic-row header">
            <span className="col-id">ID</span>
            <span className="col-data">Data</span>
          </div>
          <div className="traffic-scroll">
            {logRows
              .slice(-150)
              .reverse()
              .map((f, i) => (
                <div className="traffic-row" key={i}>
                  <span className="col-id">{toHex(f.arb_id)}</span>
                  <span className="col-data">
                    {f.data.map((b, j) => (
                      <span key={j} className="byte">
                        {toByteHex(b)}
                      </span>
                    ))}
                  </span>
                </div>
              ))}
            {logRows.length === 0 && <div className="empty-hint">No traffic yet…</div>}
          </div>
        </div>
      )}
    </div>
  );
}
