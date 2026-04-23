import { useMemo, useState } from "react";
import SearchForm from "./components/SearchForm.jsx";
import ProgressView from "./components/ProgressView.jsx";
import DayResultCard from "./components/DayResultCard.jsx";
import { startSearch, openEventStream } from "./api.js";

export default function App() {
  const [mode, setMode] = useState("form"); // form | searching | results
  const [events, setEvents] = useState([]);
  const [progress, setProgress] = useState(null);
  const [error, setError] = useState("");
  const [sort, setSort] = useState("date"); // date | price
  const [closer, setCloser] = useState(null);

  async function handleSubmit(payload) {
    setError("");
    setEvents([]);
    setProgress(null);
    try {
      const { search_id, total_dates } = await startSearch(payload);
      setProgress({ done: 0, total: total_dates, current_date: null });
      setMode("searching");

      const close = openEventStream(search_id, {
        onEvent: (ev) => {
          if (ev.progress) setProgress(ev.progress);
          if (ev.type === "result" || ev.type === "error") {
            setEvents((prev) => [...prev, ev]);
          }
          if (ev.type === "done") {
            setMode("results");
          }
        },
        onError: () => setError("Connection lost"),
      });
      setCloser(() => close);
    } catch (e) {
      setError(e.message || "Failed to start search");
      setMode("form");
    }
  }

  function reset() {
    if (closer) closer();
    setMode("form");
    setEvents([]);
    setProgress(null);
    setError("");
  }

  const sorted = useMemo(() => {
    const arr = [...events];
    if (sort === "price") {
      arr.sort((a, b) => {
        const ap = a.options?.[0]?.total_price ?? Infinity;
        const bp = b.options?.[0]?.total_price ?? Infinity;
        return ap - bp;
      });
    } else {
      arr.sort((a, b) =>
        (a.departure_date || "").localeCompare(b.departure_date || ""),
      );
    }
    return arr;
  }, [events, sort]);

  return (
    <div className="app">
      <div className="top-actions">
        <h1>✈︎ Air Ticket Price Finder</h1>
        {mode !== "form" && (
          <button className="link-button" onClick={reset}>New search</button>
        )}
      </div>

      {mode === "form" && <SearchForm onSubmit={handleSubmit} />}

      {error && <div className="panel" style={{ borderColor: "var(--err)" }}>{error}</div>}

      {(mode === "searching" || mode === "results") && (
        <>
          {mode === "searching" && <ProgressView progress={progress} />}

          {events.length > 0 && (
            <div className="sort-bar">
              <span style={{ color: "var(--muted)", fontSize: 12 }}>Sort:</span>
              <button
                className={sort === "date" ? "active" : ""}
                onClick={() => setSort("date")}
              >By date</button>
              <button
                className={sort === "price" ? "active" : ""}
                onClick={() => setSort("price")}
              >By price</button>
            </div>
          )}

          {sorted.map((ev) => (
            <DayResultCard key={ev.departure_date + (ev.type || "")} event={ev} />
          ))}
        </>
      )}
    </div>
  );
}
