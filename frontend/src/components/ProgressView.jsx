export default function ProgressView({ progress }) {
  if (!progress) return null;
  const pct = progress.total ? Math.round((progress.done / progress.total) * 100) : 0;
  return (
    <div className="panel">
      <div style={{ display: "flex", justifyContent: "space-between" }}>
        <strong>Searching…</strong>
        <span>{progress.done} / {progress.total}</span>
      </div>
      <div className="progress-bar">
        <div style={{ width: `${pct}%` }} />
      </div>
      <div className="status-line">
        {progress.current_date ? `Checked ${progress.current_date}` : ""}
      </div>
    </div>
  );
}
