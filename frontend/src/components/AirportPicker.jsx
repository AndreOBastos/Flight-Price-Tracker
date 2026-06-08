import { useState } from "react";
import AirportAutocomplete from "./AirportAutocomplete.jsx";

/**
 * Multi-airport picker. Renders selected airports as chips and an inline
 * AirportAutocomplete to add more. Useful for cities with several airports
 * (e.g. NYC = JFK / EWR / LGA, London = LHR / LGW / STN / LCY).
 *
 * Props:
 *   values: Array<{iata, label}>
 *   onChange: (next: Array) => void
 *   placeholder: string for the empty-state input
 *   max: maximum number of airports (default 4)
 */
export default function AirportPicker({ values = [], onChange, placeholder, max = 4 }) {
  // Bump this key when a selection lands so the autocomplete remounts with
  // an empty input — saves us from threading a "clear" prop into it.
  const [resetKey, setResetKey] = useState(0);

  function handleSelect(item) {
    // The autocomplete fires onChange(null) on every keystroke; ignore those.
    if (!item) return;
    if (values.length >= max) return;
    if (values.some((v) => v.iata === item.iata)) {
      // Duplicate — silently drop and reset the input.
      setResetKey((k) => k + 1);
      return;
    }
    onChange([...values, item]);
    setResetKey((k) => k + 1);
  }

  function remove(iata) {
    onChange(values.filter((v) => v.iata !== iata));
  }

  return (
    <div className="airport-picker">
      {values.length > 0 && (
        <div className="airport-chips">
          {values.map((v) => (
            <span key={v.iata} className="airport-chip">
              {v.label || v.iata}
              <button
                type="button"
                onClick={() => remove(v.iata)}
                aria-label={`Remove ${v.iata}`}
              >
                ×
              </button>
            </span>
          ))}
        </div>
      )}
      {values.length < max && (
        <AirportAutocomplete
          key={resetKey}
          value={null}
          onChange={handleSelect}
          placeholder={
            values.length === 0 ? placeholder : "Add another airport (optional)"
          }
        />
      )}
      {values.length >= max && (
        <div className="picker-limit">Maximum of {max} airports reached.</div>
      )}
    </div>
  );
}
