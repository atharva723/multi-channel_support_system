/** Parse a server timestamp. Values without a timezone are assumed to be UTC. */
function parseServerDate(iso: string): Date {
  if (iso && /^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}/.test(iso) && !/([zZ]|[+-]\d{2}:?\d{2})$/.test(iso)) {
    // Naive timestamp (no offset) — normalize the space separator and mark UTC.
    return new Date(iso.replace(' ', 'T') + 'Z');
  }
  return new Date(iso);
}

/** Compact relative-time formatter (e.g. "2m ago", "3h ago", "Jul 11"). */
export function relativeTime(iso: string): string {
  const then = parseServerDate(iso).getTime();
  if (Number.isNaN(then)) return '';
  const secs = Math.max(0, (Date.now() - then) / 1000);
  if (secs < 60) return 'just now';
  const mins = Math.floor(secs / 60);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days < 7) return `${days}d ago`;
  return parseServerDate(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

/** "Jan 12" style short date for connection metadata. */
export function shortDate(iso: string): string {
  const d = parseServerDate(iso);
  if (Number.isNaN(d.getTime())) return '';
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}
