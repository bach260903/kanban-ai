/**
 * Returns a short human-friendly relative time label for an ISO timestamp
 * (e.g. ``2h ago``, ``3 days ago``, ``just now``). Uses the browser's
 * ``Intl.RelativeTimeFormat`` so locale switches automatically.
 */
const RTF =
  typeof Intl !== 'undefined' && typeof Intl.RelativeTimeFormat === 'function'
    ? new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' })
    : null

const UNITS: Array<{ unit: Intl.RelativeTimeFormatUnit; seconds: number }> = [
  { unit: 'year', seconds: 60 * 60 * 24 * 365 },
  { unit: 'month', seconds: 60 * 60 * 24 * 30 },
  { unit: 'week', seconds: 60 * 60 * 24 * 7 },
  { unit: 'day', seconds: 60 * 60 * 24 },
  { unit: 'hour', seconds: 60 * 60 },
  { unit: 'minute', seconds: 60 },
]

export function relativeTime(iso: string, now: Date = new Date()): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  const deltaSec = Math.round((date.getTime() - now.getTime()) / 1000)
  const abs = Math.abs(deltaSec)
  if (abs < 45) return 'just now'
  if (!RTF) return date.toLocaleString()
  for (const { unit, seconds } of UNITS) {
    if (abs >= seconds) {
      return RTF.format(Math.round(deltaSec / seconds), unit)
    }
  }
  return RTF.format(deltaSec, 'second')
}
