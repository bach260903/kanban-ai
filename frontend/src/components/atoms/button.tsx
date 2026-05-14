import type { ButtonHTMLAttributes, ReactNode } from 'react'

import styles from './button.module.css'

export type ButtonVariant = 'primary' | 'secondary' | 'danger'

export type ButtonProps = {
  variant?: ButtonVariant
  children: ReactNode
} & ButtonHTMLAttributes<HTMLButtonElement>

export function Button({
  variant = 'primary',
  className,
  children,
  type = 'button',
  ...rest
}: ButtonProps) {
  const variantClass = styles[variant]
  const merged = [styles.button, variantClass, className].filter(Boolean).join(' ')
  return (
    <button type={type} className={merged} {...rest}>
      {children}
    </button>
  )
}
