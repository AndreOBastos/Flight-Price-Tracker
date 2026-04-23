import { useEffect, useState } from "react";
import AirportAutocomplete from "./AirportAutocomplete.jsx";
import { listCurrencies } from "../api.js";

function today() {
  return new Date().toISOString().slice(0, 10);
}

export default function SearchForm({ onSubmit, disabled }) {
  const [origin, setOrigin] = useState(null);
  const [dest, setDest] = useState(null);
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
    if (!origin || !dest) { setError("Select origin and destination airports"); return; }
    if (origin.iata === dest.iata) { setError("Origin and destination must differ"); return; }
    if (!dateFrom || !dateTo) { setError("Pick a date range"); return; }
    if (dateFrom > dateTo) { setError("Start date must be on/before end date"); return; }
    const span = Math.round((new Date(dateTo) - new Date(dateFrom)) / 86400000);
    if (span > 60) { setError("Date range must be at most 60 days"); return; }
    onSubmit({
      origin: origin.iata,
      dest: dest.iata,
      trip_days: Number(tripDays),
      date_from: dateFrom,
      date_to: dateTo,
      currency,
    });
  }

  return (
    <form className="panel" onSubmit={submit}>
      <div className="form-grid">
        <div>
          <label>From</label>
          <AirportAutocomplete value={origin} onChange={setOrigin} placeholder="City of origin" />
        </div>
        <div>
          <label>To</label>
          <AirportAutocomplete value={dest} onChange={setDest} placeholder="City of destination" />
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
        <div className="wide" style={{ display: "flex", justifyContent: "flex-end", alignItems: "center", gap: 12 }}>
          {error && <span style={{ color: "var(--err)", fontSize: 13 }}>{error}</span>}
          <button className="primary" type="submit" disabled={disabled}>
            {disabled ? "Searching…" : "Find cheapest flights"}
          </button>
        </div>
      </div>
    </form>
  );
}
