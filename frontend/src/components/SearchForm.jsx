import { useEffect, useState } from "react";
import AirportPicker from "./AirportPicker.jsx";
import { listCurrencies } from "../api.js";

function today() {
  return new Date().toISOString().slice(0, 10);
}

export default function SearchForm({ onSubmit, disabled }) {
  const [origins, setOrigins] = useState([]); // Array<{iata,label}>
  const [dests, setDests] = useState([]);
  const [tripDays, setTripDays] = useState(5);
  const [dateFrom, setDateFrom] = useState(today());
  const [dateTo, setDateTo] = useState(today());
  const [currency, setCurrency] = useState("USD");
  const [currencies, setCurrencies] = useState(["USD"]);
  const [error, setError] = useState("");

  useEffect(() => {
    listCurrencies().then(setCurrencies).catch(() => {});
  }, []);

  function submit(e) {
    e.preventDefault();
    setError("");
    if (origins.length === 0 || dests.length === 0) {
      setError("Pick at least one origin and one destination airport");
      return;
    }
    const overlap = origins
      .map((o) => o.iata)
      .filter((i) => dests.some((d) => d.iata === i));
    if (overlap.length) {
      setError(`Origin and destination share airports: ${overlap.join(", ")}`);
      return;
    }
    if (!dateFrom || !dateTo) { setError("Pick a date range"); return; }
    if (dateFrom > dateTo) { setError("Start date must be on/before end date"); return; }
    const span = Math.round((new Date(dateTo) - new Date(dateFrom)) / 86400000);
    if (span > 60) { setError("Date range must be at most 60 days"); return; }
    onSubmit({
      origins: origins.map((o) => o.iata),
      dests: dests.map((d) => d.iata),
      trip_days: Number(tripDays),
      date_from: dateFrom,
      date_to: dateTo,
      currency,
    });
  }

  // Rough estimate of how many one-way searches per date (each is ~5-10s).
  const fetchesPerDate = 2 * Math.max(1, origins.length) * Math.max(1, dests.length);

  return (
    <form className="panel" onSubmit={submit}>
      <div className="form-grid">
        <div>
          <label>From <span className="hint">(add up to 4 airports)</span></label>
          <AirportPicker
            values={origins}
            onChange={setOrigins}
            placeholder="City or IATA of origin"
          />
        </div>
        <div>
          <label>To <span className="hint">(add up to 4 airports)</span></label>
          <AirportPicker
            values={dests}
            onChange={setDests}
            placeholder="City or IATA of destination"
          />
        </div>
        <div>
          <label>Trip length (days)</label>
          <input
            type="number"
            min="0"
            max="60"
            value={tripDays}
            onChange={(e) => setTripDays(e.target.value)}
          />
        </div>
        <div>
          <label>Currency</label>
          <select value={currency} onChange={(e) => setCurrency(e.target.value)}>
            {currencies.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
        <div>
          <label>Depart between — from</label>
          <input type="date" value={dateFrom} min={today()} onChange={(e) => setDateFrom(e.target.value)} />
        </div>
        <div>
          <label>Depart between — to</label>
          <input type="date" value={dateTo} min={dateFrom || today()} onChange={(e) => setDateTo(e.target.value)} />
        </div>
        <div className="wide" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
          <span className="hint">
            {origins.length > 0 && dests.length > 0
              ? `~${fetchesPerDate} searches per date · expect ~${Math.round(fetchesPerDate * 6)}s/date`
              : ""}
          </span>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            {error && <span style={{ color: "var(--err)", fontSize: 13 }}>{error}</span>}
            <button className="primary" type="submit" disabled={disabled}>
              {disabled ? "Searching…" : "Find cheapest flights"}
            </button>
          </div>
        </div>
      </div>
    </form>
  );
}
