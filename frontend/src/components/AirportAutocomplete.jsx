import { useEffect, useRef, useState } from "react";
import { searchAirports } from "../api.js";

export default function AirportAutocomplete({ value, onChange, placeholder }) {
  const [query, setQuery] = useState(value?.label || "");
  const [suggestions, setSuggestions] = useState([]);
  const [open, setOpen] = useState(false);
  const [highlight, setHighlight] = useState(0);
  const timerRef = useRef(null);
  const rootRef = useRef(null);

  useEffect(() => {
    const handler = (e) => {
      if (rootRef.current && !rootRef.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  function onInputChange(e) {
    const q = e.target.value;
    setQuery(q);
    onChange(null);
    clearTimeout(timerRef.current);
    if (!q.trim()) {
      setSuggestions([]);
      setOpen(false);
      return;
    }
    timerRef.current = setTimeout(async () => {
      try {
        const items = await searchAirports(q);
        setSuggestions(items);
        setOpen(true);
        setHighlight(0);
      } catch {
        setSuggestions([]);
      }
    }, 200);
  }

  function pick(item) {
    setQuery(`${item.city} (${item.iata})`);
    setSuggestions([]);
    setOpen(false);
    onChange({ iata: item.iata, label: `${item.city} (${item.iata})` });
  }

  function onKeyDown(e) {
    if (!open || suggestions.length === 0) return;
    if (e.key === "ArrowDown") {
      setHighlight((h) => Math.min(h + 1, suggestions.length - 1));
      e.preventDefault();
    } else if (e.key === "ArrowUp") {
      setHighlight((h) => Math.max(h - 1, 0));
      e.preventDefault();
    } else if (e.key === "Enter") {
      pick(suggestions[highlight]);
      e.preventDefault();
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  }

  return (
    <div className="autocomplete" ref={rootRef}>
      <input
        type="text"
        value={query}
        onChange={onInputChange}
        onKeyDown={onKeyDown}
        onFocus={() => query && suggestions.length && setOpen(true)}
        placeholder={placeholder || "City or IATA code"}
        autoComplete="off"
      />
      {open && suggestions.length > 0 && (
        <ul className="autocomplete-list">
          {suggestions.map((s, i) => (
            <li
              key={s.iata}
              className={i === highlight ? "active" : ""}
              onMouseEnter={() => setHighlight(i)}
              onMouseDown={(e) => {
                e.preventDefault();
                pick(s);
              }}
            >
              <span className="iata">{s.iata}</span>
              {s.city}
              <span className="muted"> — {s.name}, {s.country}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
