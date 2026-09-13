export function humanizeDimension(key) {
  return key
    .split("_")
    .map((w) => w[0].toUpperCase() + w.slice(1))
    .join(" ");
}

export function verdictClass(verdict) {
  return verdict === "SELECT" ? "verdict verdict--select" : "verdict verdict--reject";
}

// Tier a score against its rubric range so weak/strong dimensions can be
// told apart at a glance instead of reading as identical gray cards.
export function scoreTier(score, range) {
  if (score === null || score === undefined || !range) return null;
  const [min, max] = range;
  const pct = (score - min) / (max - min);
  if (pct >= 0.75) return "strong";
  if (pct >= 0.4) return "mid";
  return "weak";
}

export function rateTier(rate) {
  if (rate >= 0.75) return "strong";
  if (rate >= 0.4) return "mid";
  return "weak";
}

export function truncate(text, max) {
  if (!text) return "";
  return text.length > max ? `${text.slice(0, max).trimEnd()}…` : text;
}

export function formatDuration(totalSeconds) {
  const h = Math.floor(totalSeconds / 3600);
  const m = Math.floor((totalSeconds % 3600) / 60);
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m`;
  return `${totalSeconds}s`;
}

export function roundLabel(roundType) {
  return roundType === "hld" ? "High-Level Design" : "LLD + Deep-Dive";
}
