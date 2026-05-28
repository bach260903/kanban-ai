import { useState } from 'react'
import type { RiskAssessmentOut } from '../../services/devops-api'
import styles from './risk-assessment-panel.module.css'

type Props = {
  assessment: RiskAssessmentOut
  /** Show compact inline layout (for pipeline-run page) */
  compact?: boolean
}

export function RiskAssessmentPanel({ assessment, compact = false }: Props) {
  const [expanded, setExpanded] = useState(false)

  const { risk_score, risk_level, reasoning, risk_factors, blast_radius, safe_to_deploy, via_llm } =
    assessment

  return (
    <div className={`${styles.panel} ${styles[`level_${risk_level}`]} ${compact ? styles.compact : ''}`}>
      <div className={styles.header} onClick={() => setExpanded(e => !e)}>
        <div className={styles.scoreCircle}>
          <svg viewBox="0 0 36 36" className={styles.circleSvg}>
            <circle className={styles.circleTrack} cx="18" cy="18" r="15.9" />
            <circle
              className={`${styles.circleFill} ${styles[`fill_${risk_level}`]}`}
              cx="18"
              cy="18"
              r="15.9"
              strokeDasharray={`${Math.round(risk_score * 100)} 100`}
            />
          </svg>
          <span className={styles.scoreText}>{Math.round(risk_score * 100)}</span>
        </div>

        <div className={styles.titleBlock}>
          <div className={styles.titleRow}>
            <span className={`${styles.badge} ${styles[`badge_${risk_level}`]}`}>
              {risk_level.toUpperCase()}
            </span>
            <span className={styles.title}>Deployment Risk</span>
            {!safe_to_deploy && (
              <span className={styles.unsafePill}>Deploy blocked</span>
            )}
            {via_llm && <span className={styles.aiPill}>AI</span>}
          </div>
          {blast_radius && (
            <p className={styles.blastRadius}>{blast_radius}</p>
          )}
        </div>

        <button
          className={styles.expandBtn}
          aria-label={expanded ? 'Collapse' : 'Expand'}
          aria-expanded={expanded}
        >
          {expanded ? '▲' : '▼'}
        </button>
      </div>

      {expanded && (
        <div className={styles.body}>
          <p className={styles.reasoning}>{reasoning}</p>

          {risk_factors.length > 0 && (
            <ul className={styles.factorList}>
              {risk_factors.map((f, i) => (
                <li key={i} className={styles.factor}>
                  <span className={styles.factorDot} />
                  {f}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
