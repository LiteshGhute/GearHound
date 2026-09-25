export default function VehicleSelector({ vehicles, selectVehicle }) {
  const { profiles, active } = vehicles;
  return (
    <div className="vehicle-selector">
      {profiles.map((p) => (
        <button
          key={p.key}
          className={`vehicle-chip ${p.key === active ? "active" : ""}`}
          onClick={() => selectVehicle(p.key)}
          title={p.description}
        >
          {p.name}
        </button>
      ))}
    </div>
  );
}
