const SYMBOL = {
  USD: "$", EUR: "€", GBP: "£", BRL: "R$", CAD: "CA$", AUD: "A$",
  JPY: "¥", CHF: "Fr ", MXN: "MX$", INR: "₹",
};

export function fmtPrice(n, currency) {
  const sym = SYMBOL[currency] || (currency + " ");
  return `${sym}${Math.round(n).toLocaleString()}`;
}

export function fmtDuration(mins) {
  if (!mins) return "";
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  if (h && m) return `${h}h ${m}m`;
  if (h) return `${h}h`;
  return `${m}m`;
}
