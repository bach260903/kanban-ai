/** Minimal DOM toast — Atom/Toast/Error style */

const TOAST_DURATION_MS = 5000

export function showErrorToast(message: string): void {
  if (typeof document === 'undefined') return

  const el = document.createElement('div')
  el.setAttribute('role', 'alert')
  el.textContent = message
  Object.assign(el.style, {
    position: 'fixed',
    top: 'calc(var(--header-h, 56px) + var(--space-2, 8px))',
    right: 'var(--space-4, 16px)',
    maxWidth: '22rem',
    padding: '12px 16px',
    borderRadius: '8px',
    fontFamily: 'var(--font-ui, Inter, sans-serif)',
    fontSize: '13px',
    lineHeight: '1.35',
    fontWeight: '500',
    color: 'var(--font-primary-color, #0f172a)',
    background: 'rgba(220, 38, 38, 0.12)',
    border: '1px solid var(--c-danger-500, #dc2626)',
    boxShadow: 'var(--shadow, 0 4px 12px rgba(0,0,0,0.12))',
    zIndex: '9999',
    pointerEvents: 'auto',
  } satisfies Partial<CSSStyleDeclaration>)

  document.body.appendChild(el)
  window.setTimeout(() => {
    el.remove()
  }, TOAST_DURATION_MS)
}

export function showSuccessToast(message: string): void {
  if (typeof document === 'undefined') return

  const el = document.createElement('div')
  el.setAttribute('role', 'status')
  el.textContent = message
  Object.assign(el.style, {
    position: 'fixed',
    top: 'calc(var(--header-h, 56px) + var(--space-2, 8px))',
    right: 'var(--space-4, 16px)',
    maxWidth: '22rem',
    padding: '12px 16px',
    borderRadius: '8px',
    fontFamily: 'var(--font-ui, Inter, sans-serif)',
    fontSize: '13px',
    lineHeight: '1.35',
    fontWeight: '500',
    color: 'var(--font-primary-color, #0f172a)',
    background: 'rgba(16, 185, 129, 0.12)',
    border: '1px solid var(--c-success-500, #10b981)',
    boxShadow: 'var(--shadow)',
    zIndex: '9999',
    pointerEvents: 'none',
  } satisfies Partial<CSSStyleDeclaration>)

  document.body.appendChild(el)
  window.setTimeout(() => {
    el.remove()
  }, 4000)
}
