import { useState } from "react";
import Dashboard from "./components/Dashboard.jsx";
import DriverView from "./components/DriverView.jsx";
import TrafficMonitor from "./components/TrafficMonitor.jsx";
import AttackConsole from "./components/AttackConsole.jsx";
import VehicleSelector from "./components/VehicleSelector.jsx";
import { useSocket } from "./hooks/useSocket.js";

export default function App() {
  const {
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
  } = useSocket();

  const [view, setView] = useState("topdown"); // "topdown" | "driver"

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="brand">
          <span className="brand-mark">&#9670;</span>
          <span className="brand-name">GearHound</span>
          <span className="brand-tag">CAN bus attack simulator</span>
        </div>
        <div className="header-right">
          <div className="view-switch">
            <button className={view === "topdown" ? "active" : ""} onClick={() => setView("topdown")}>
              Top-Down
            </button>
            <button className={view === "driver" ? "active" : ""} onClick={() => setView("driver")}>
              Driver View
            </button>
          </div>
          <VehicleSelector vehicles={vehicles} selectVehicle={selectVehicle} />
          <span
            className={`conn-dot ${connected ? "up" : "down"}`}
            title={connected ? "connected" : "disconnected"}
          />
        </div>
      </header>

      <main className="app-grid">
        <section className="col-dashboard">
          {view === "topdown" ? (
            <Dashboard carState={carState} busCongestion={busCongestion} sendControl={sendControl} />
          ) : (
            <DriverView carState={carState} sendControl={sendControl} />
          )}
        </section>
        <section className="col-side">
          <TrafficMonitor traffic={traffic} />
          <AttackConsole
            attacksRunning={attacksRunning}
            captures={captures}
            attackLog={attackLog}
            startAttack={startAttack}
            stopAttack={stopAttack}
            startCapture={startCapture}
            stopCapture={stopCapture}
          />
        </section>
      </main>
    </div>
  );
}
