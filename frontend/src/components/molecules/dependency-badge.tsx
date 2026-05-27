export type DependencyBadgeProps = {
  blockedByTitles: string[]
  /** When set, used for count/label even if ``blockedByTitles`` is empty (e.g. graph not loaded yet). */
  forceCount?: number
  className?: string
}

function truncateTitle(title: string, max = 24): string {
  const t = title.trim()
  if (t.length <= max) return t
  return `${t.slice(0, max - 1)}…`
}

export function DependencyBadge({ blockedByTitles, forceCount, className = '' }: DependencyBadgeProps) {
  const count = forceCount ?? blockedByTitles.length
  if (count === 0) return null

  const preview = blockedByTitles.length > 0 ? blockedByTitles.slice(0, 3) : ['Prerequisite pending']
  const extra = count - Math.min(blockedByTitles.length, 3)
  const tooltipLines = [
    ...preview.map((t) => truncateTitle(t)),
    ...(extra > 0 ? ['...'] : []),
  ]

  return (
    <span
      className={`inline-flex items-center gap-1 rounded-md bg-red-100 px-2 py-0.5 font-mono text-[10.5px] font-semibold text-red-700 ${className}`.trim()}
      title={tooltipLines.join('\n')}
      role="status"
      aria-label={`Blocked by ${count} ${count === 1 ? 'dependency' : 'dependencies'}`}
    >
      <span aria-hidden>🔒</span>
      Blocked ({count})
    </span>
  )
}
