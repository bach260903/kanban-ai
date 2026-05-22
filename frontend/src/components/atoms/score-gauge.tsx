/**
 * Score gauge display for AI review score 0–100 (US1 / T035).
 */

export type ScoreGaugeProps = {
  score: number
}

function scoreColor(score: number): string {
  if (score >= 80) return 'text-green-600'
  if (score >= 50) return 'text-yellow-500'
  return 'text-red-600'
}

/**
 * Displays the AI review score as a large prominent number with a colour
 * indicating quality (green ≥ 80, yellow 50–79, red < 50).
 */
export function ScoreGauge({ score }: ScoreGaugeProps) {
  const color = scoreColor(score)
  return (
    <span className="inline-flex items-baseline gap-0.5" aria-label={`Review score: ${score} out of 100`}>
      <span className={`text-4xl font-bold tabular-nums ${color}`}>{score}</span>
      <span className="text-sm text-gray-400 font-normal">/100</span>
    </span>
  )
}
