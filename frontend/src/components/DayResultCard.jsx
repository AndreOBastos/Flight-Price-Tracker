import { useState } from "react";
import { fmtPrice, fmtDuration } from "../format.js";
import FlightMap from "./FlightMap.jsx";

function Leg({ title, leg }) {
  const route = [leg.dep_iata, ...leg.layovers.map((l) => l.iata), leg.arr_iata];
  return (
    <div className="leg">
      <h3>{title}</h3>
      <div className="airline">{leg.airline}</div>
      <div className="route">
        {route.map((iata, i) => (
          <span key={i}>
            <code>{iata}</code>
            {i < route.length - 1 && <span style={{ margin: "0 4px" }}>→</span>}
          </span>
        ))}
      </div>
      <div className="meta">
        {leg.dep_time} → {leg.arr_time} · {fmtDuration(leg.duration_min)} · {fmtPrice(leg.price, leg.currency)}
      </div>
      {leg.layovers.length > 0 && (
        <div className="layovers">
          {leg.layovers.map((l, i) => (
            <div key={i}>↳ Layover at {l.name} ({l.iata}) · {fmtDuration(l.duration_min)}</div>
          ))}
        </div>
      )}
    </div>
  );
}

function Amenities({ hints }) {
  if (!hints || Object.keys(hints).length === 0) return null;
  const rows = Object.entries(hints);
  return (
    <div className="amenities">
      <span className="tag">Typical for these carriers — not guaranteed</span>
      <table>
        <thead>
          <tr>
            <th>Carrier</th>
            <th>Wi-Fi</th>
            <th>Power</th>
            <th>Legroom</th>
            <th>Carry-on</th>
            <th>Checked</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([code, h]) => (
            <tr key={code}>
              <td><strong>{code}</strong> {h.name && h.name !== code ? `— ${h.name}` : ""}</td>
              <td>{h.wifi || "—"}</td>
              <td>{h.power || "—"}</td>
              <td>{h.legroom || "—"}</td>
              <td>{h.carryon || "—"}</td>
              <td>{h.checked || "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function OptionCard({ opt, rank, expanded, onToggle }) {
  const isCheapest = rank === 1;
  return (
    <div className={`option ${isCheapest ? "cheapest" : ""}`}>
      <div className="option-header" onClick={onToggle} role="button" tabIndex={0}>
        <span className="option-rank">#{rank}</span>
        <span className="option-airlines">
          {opt.outbound.airline}{opt.inbound.airline !== opt.outbound.airline ? ` / ${opt.inbound.airline}` : ""}
        </span>
        <span className="option-price">{fmtPrice(opt.total_price, opt.currency)}</span>
        <span className="option-toggle">{expanded ? "▾" : "▸"}</span>
      </div>
      {expanded && (
        <div className="option-body">
          <div className="legs">
            <Leg title="Outbound" leg={opt.outbound} />
            <Leg title="Return" leg={opt.inbound} />
          </div>
          <FlightMap outbound={opt.outbound} inbound={opt.inbound} />
          <Amenities hints={opt.amenity_hints} />
        </div>
      )}
    </div>
  );
}

export default function DayResultCard({ event }) {
  const [expandedIdx, setExpandedIdx] = useState(0); // cheapest expanded by default

  if (event.type === "error") {
    return (
      <div className="card error">
        <div className="card-header">
          <div className="dates">{event.departure_date}</div>
          <div className="msg">Error</div>
        </div>
        <div className="msg">{event.message}</div>
      </div>
    );
  }

  const options = event.options || [];

  if (options.length === 0) {
    const reasonMsg = {
      no_schedule:
        "Google has no schedule data for this route on this date — likely too far in the future for the carriers serving this origin. Try closer dates.",
      no_flights:
        "No round trip available on this date.",
      blocked:
        "Google temporarily blocked our request — try this date again in a moment.",
    }[event.reason] || "No round trip found";
    return (
      <div className="card no-result">
        <div className="card-header">
          <div className="dates">
            {event.departure_date} <small>→ {event.return_date}</small>
          </div>
          <div className="muted">{reasonMsg}</div>
        </div>
      </div>
    );
  }

  const cheapest = options[0];
  return (
    <div className="card">
      <div className="card-header">
        <div className="dates">
          {event.departure_date} <small>→ {event.return_date}</small>
        </div>
        <div className="price">{fmtPrice(cheapest.total_price, cheapest.currency)}</div>
      </div>
      <div className="options-list">
        {options.map((opt, i) => (
          <OptionCard
            key={i}
            opt={opt}
            rank={i + 1}
            expanded={expandedIdx === i}
            onToggle={() => setExpandedIdx(expandedIdx === i ? -1 : i)}
          />
        ))}
      </div>
    </div>
  );
}
