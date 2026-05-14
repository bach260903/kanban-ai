import type { HTMLAttributes } from 'react'

import styles from './spinner.module.css'

export type SpinnerProps = {
  'aria-label'?: string
} & Omit<HTMLAttributes<HTMLSpanElement>, 'children'>

export function Spinner({ 'aria-label': ariaLabel = 'Loading', className, ...rest }: SpinnerProps) {
  const merged = [styles.root, className].filter(Boolean).join(' ')
  return (
    <span role="status" aria-live="polite" aria-label={ariaLabel} className={merged} {...rest}>
      <span className={styles.ring} />
    </span>
  )
}
