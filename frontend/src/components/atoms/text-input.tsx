import { useId, type InputHTMLAttributes } from 'react'

import styles from './text-input.module.css'

export type TextInputProps = {
  label?: string
  hint?: string
  invalid?: boolean
} & InputHTMLAttributes<HTMLInputElement>

export function TextInput({ label, hint, id, invalid, className, disabled, ...rest }: TextInputProps) {
  const autoId = useId()
  const inputId = id ?? autoId
  const inputClass = [styles.input, invalid ? styles.inputInvalid : '', className].filter(Boolean).join(' ')

  return (
    <div className={styles.wrap}>
      {label ? (
        <label className={styles.label} htmlFor={inputId}>
          {label}
        </label>
      ) : null}
      <input id={inputId} className={inputClass} disabled={disabled} {...rest} />
      {hint ? <span className={styles.hint}>{hint}</span> : null}
    </div>
  )
}
