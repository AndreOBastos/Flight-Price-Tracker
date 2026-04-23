const BASE = "/api";

export async function searchAirports(q) {
  const r = await fetch(`${BASE}/airports?q=${encodeURIComponent(q)}`);
  if (!r.ok) throw new Error("airport search failed");
  return r.json();
}

export async function listCurrencies() {
  const r = await fetch(`${BASE}/currencies`);
  if (!r.ok) throw new Error("currencies fetch failed");
  return r.json();
}

export async function startSearch(payload) {
  const r = await fetch(`${BASE}/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!r.ok) {
    const detail = await r.json().catch(() => ({}));
    throw new Error(detail.detail || "search failed");
  }
  return r.json();
}

export function openEventStream(searchId, { onEvent, onDone, onError }) {
  const es = new EventSource(`${BASE}/search/${searchId}/events`);
  es.onmessage = (msg) => {
    try {
      const ev = JSON.parse(msg.data);
      onEvent(ev);
      if (ev.type === "done") {
        es.close();
        onDone && onDone();
      }
    } catch (err) {
      onError && onError(err);
    }
  };
  es.onerror = (err) => {
    onError && onError(err);
    es.close();
  };
  return () => es.close();
}
