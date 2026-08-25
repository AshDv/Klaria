const PARIS = "Europe/Paris";

export function instant(value) {
  if (value instanceof Date) return value;
  const text = String(value || "");
  const hasZone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(text);
  return new Date(hasZone ? text : `${text}Z`);
}

export function parisDateTime(value, dateStyle = "medium", timeStyle = "short") {
  return new Intl.DateTimeFormat("fr-FR", { dateStyle, timeStyle, timeZone: PARIS })
    .format(instant(value));
}

export function parisDate(value, options = {}) {
  return new Intl.DateTimeFormat("fr-FR", { ...options, timeZone: PARIS })
    .format(instant(value));
}

export function parisTime(value) {
  return new Intl.DateTimeFormat("fr-FR", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: PARIS,
  }).format(instant(value));
}

export function parisDayKey(value) {
  const parts = new Intl.DateTimeFormat("en-CA", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    timeZone: PARIS,
  }).formatToParts(instant(value));
  const get = (type) => parts.find((part) => part.type === type)?.value;
  return `${get("year")}-${get("month")}-${get("day")}`;
}
