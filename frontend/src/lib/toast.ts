/** Minimal DOM toast — no extra dependencies (T061 error on 409). */

const TOAST_DURATION_MS = 5000

export function showErrorToast(message: string): void {
  if (typeof document === 'undefined') return

  const el = document.createElement('div')
  el.setAttribute('role', 'alert')
  el.textContent = message
  Object.assign(el.style, {
    position: 'fixed',
    top: '1rem',
    right: '1rem',
    maxWidth: '22rem',
    padding: '0.75rem 1rem',
    borderRadius: '8px',
    fontSize: '0.875rem',
    lineHeight: 1.35,
    fontWeight: '500',
    color: '#fef2f2',
    background: '#991b1b',
    border: '1px solid #fecaca',
    boxShadow: '0 8px 24px rgba(0,0,0,0.2)',
    zIndex: '9999',
    pointerEvents: 'none',
  } satisfies Partial<CSSStyleDeclaration>)

  document.body.appendChild(el)
  window.setTimeout(() => {
    el.remove()
  }, TOAST_DURATION_MS)
}
