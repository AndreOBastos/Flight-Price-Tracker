import { useEffect, useRef } from "react";
import L from "leaflet";

/**
 * Draw a great-circle arc between two lat/lng points by interpolating along the
 * shortest path on the sphere. Returns an array of [lat, lng] points.
 */
function greatCircle(a, b, steps = 64) {
  const toRad = (d) => (d * Math.PI) / 180;
  const toDeg = (r) => (r * 180) / Math.PI;
  const lat1 = toRad(a.lat), lon1 = toRad(a.lng);
  const lat2 = toRad(b.lat), lon2 = toRad(b.lng);
  const d = 2 * Math.asin(
    Math.sqrt(
      Math.sin((lat2 - lat1) / 2) ** 2 +
        Math.cos(lat1) * Math.cos(lat2) * Math.sin((lon2 - lon1) / 2) ** 2,
    ),
  );
  if (d === 0) return [[a.lat, a.lng], [b.lat, b.lng]];
  const pts = [];
  for (let i = 0; i <= steps; i++) {
    const f = i / steps;
    const A = Math.sin((1 - f) * d) / Math.sin(d);
    const B = Math.sin(f * d) / Math.sin(d);
    const x = A * Math.cos(lat1) * Math.cos(lon1) + B * Math.cos(lat2) * Math.cos(lon2);
    const y = A * Math.cos(lat1) * Math.sin(lon1) + B * Math.cos(lat2) * Math.sin(lon2);
    const z = A * Math.sin(lat1) + B * Math.sin(lat2);
    const lat = toDeg(Math.atan2(z, Math.sqrt(x * x + y * y)));
    const lon = toDeg(Math.atan2(y, x));
    pts.push([lat, lon]);
  }
  return pts;
}

export default function FlightMap({ outbound, inbound }) {
  const ref = useRef(null);
  const mapRef = useRef(null);

  useEffect(() => {
    if (!ref.current) return;
    const map = L.map(ref.current, { zoomControl: true, attributionControl: false });
    L.tileLayer(
      "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
      { maxZoom: 10, minZoom: 1 },
    ).addTo(map);
    mapRef.current = map;
    return () => { map.remove(); mapRef.current = null; };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    // Clear existing layers except the tile layer (index 0).
    map.eachLayer((layer) => {
      if (!(layer instanceof L.TileLayer)) map.removeLayer(layer);
    });

    const allPoints = [];
    const drawRoute = (route, color) => {
      if (!route || !route.route_coords || route.route_coords.length < 2) return;
      const coords = route.route_coords;
      const iatas = route.route_iatas || [];
      for (let i = 0; i < coords.length - 1; i++) {
        const a = coords[i], b = coords[i + 1];
        if (!a || !b) continue;
        const pts = greatCircle(a, b);
        L.polyline(pts, { color, weight: 3, opacity: 0.9 }).addTo(map);
      }
      coords.forEach((c, i) => {
        if (!c) return;
        L.circleMarker([c.lat, c.lng], {
          radius: 5,
          color,
          fillColor: "#fff",
          fillOpacity: 1,
          weight: 2,
        }).bindTooltip(iatas[i] || "", { permanent: true, direction: "top", className: "iata-tip" }).addTo(map);
        allPoints.push([c.lat, c.lng]);
      });
    };

    drawRoute(outbound, "#38bdf8");
    drawRoute(inbound, "#fbbf24");

    if (allPoints.length > 0) {
      map.fitBounds(L.latLngBounds(allPoints).pad(0.3));
    } else {
      map.setView([20, 0], 1);
    }
  }, [outbound, inbound]);

  return <div className="map-container" ref={ref} />;
}
