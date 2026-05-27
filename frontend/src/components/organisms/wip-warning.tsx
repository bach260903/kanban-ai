import { useEffect } from 'react'

export type WIPWarningVariant = 'toast' | 'banner'

export type WIPWarningProps = {
  open: boolean
  variant?: WIPWarningVariant
  title?: string
  message?: string
  currentTaskTitle?: string | null
  /** ms; toast auto-dismiss. Set to 0 to disable. Default 4000ms for toast. */
  autoCloseMs?: number
  onDismiss: () => void
  onGoToCurrentTask?: () => void
}

function IconAlertOctagon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-5 w-5"
      aria-hidden
    >
      <polygon points="7.86 2 16.14 2 22 7.86 22 16.14 16.14 22 7.86 22 2 16.14 2 7.86 7.86 2" />
      <line x1="12" y1="8" x2="12" y2="12" />
      <line x1="12" y1="16" x2="12.01" y2="16" />
    </svg>
  )
}

function IconClose() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-4 w-4"
      aria-hidden
    >
      <path d="M18 6 6 18M6 6l12 12" />
    </svg>
  )
}

function IconArrowRight() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-3.5 w-3.5"
      aria-hidden
    >
      <path d="M5 12h14M13 5l7 7-7 7" />
    </svg>
  )
}

const DEFAULT_TITLE = 'WIP limit reached'
const DEFAULT_MESSAGE =
  'Only one task can be In progress at a time. Finish or cancel the current one before starting another.'

export function WIPWarning({
  open,
  variant = 'toast',
  title = DEFAULT_TITLE,
  message,
  currentTaskTitle,
  autoCloseMs,
  onDismiss,
  onGoToCurrentTask,
}: WIPWarningProps) {
  const resolvedAutoClose =
    autoCloseMs ?? (variant === 'toast' ? 4000 : 0)

  useEffect(() => {
    if (!open) return
    if (!resolvedAutoClose) return
    const id = window.setTimeout(onDismiss, resolvedAutoClose)
    return () => window.clearTimeout(id)
  }, [open, resolvedAutoClose, onDismiss])

  if (!open) return null

  const resolvedMessage =
    message ??
    (currentTaskTitle
      ? `Already in progress: "${currentTaskTitle}". Finish or cancel it first.`
      : DEFAULT_MESSAGE)

  if (variant === 'banner') {
    return (
      <div
        role="alert"
        aria-live="assertive"
        className="flex animate-slide-down items-start gap-3 rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-amber-900 shadow-elev-1"
      >
        <span className="mt-0.5 text-amber-600">
          <IconAlertOctagon />
        </span>
        <div className="flex flex-1 flex-col gap-1">
          <p className="font-mono text-[12px] font-bold uppercase tracking-wider">
            {title}
          </p>
          <p className="text-[13px] leading-relaxed text-amber-800">{resolvedMessage}</p>
        </div>
        <div className="flex items-center gap-1">
          {onGoToCurrentTask ? (
            <button
              type="button"
              onClick={onGoToCurrentTask}
              className="inline-flex h-7 cursor-pointer items-center gap-1 rounded-md bg-amber-600 px-2 font-mono text-[11px] font-semibold text-white transition-colors duration-150 hover:bg-amber-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-500 focus-visible:ring-offset-1"
            >
              View task
              <IconArrowRight />
            </button>
          ) : null}
          <button
            type="button"
            onClick={onDismiss}
            aria-label="Dismiss warning"
            className="inline-flex h-7 w-7 cursor-pointer items-center justify-center rounded-md text-amber-700 transition-colors duration-150 hover:bg-amber-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400"
          >
            <IconClose />
          </button>
        </div>
      </div>
    )
  }

  return (
    <div
      role="status"
      aria-live="polite"
      className="pointer-events-none fixed inset-x-0 bottom-6 z-50 flex justify-center px-4 sm:bottom-8"
    >
      <div className="pointer-events-auto flex w-full max-w-md animate-slide-down items-start gap-3 rounded-xl border border-amber-300 bg-white px-4 py-3 shadow-elev-3 ring-1 ring-amber-200/60">
        <span className="mt-0.5 grid h-8 w-8 flex-shrink-0 place-items-center rounded-lg bg-amber-100 text-amber-700">
          <IconAlertOctagon />
        </span>
        <div className="flex flex-1 flex-col gap-0.5">
          <p className="font-mono text-[12px] font-bold uppercase tracking-wider text-amber-700">
            {title}
          </p>
          <p className="text-[13px] leading-relaxed text-slate-700">{resolvedMessage}</p>
          {onGoToCurrentTask ? (
            <button
              type="button"
              onClick={onGoToCurrentTask}
              className="mt-1.5 inline-flex w-fit cursor-pointer items-center gap-1 rounded-md text-[11.5px] font-semibold text-brand-700 underline-offset-2 transition-colors duration-150 hover:text-brand-800 hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-300"
            >
              Go to current task
              <IconArrowRight />
            </button>
          ) : null}
        </div>
        <button
          type="button"
          onClick={onDismiss}
          aria-label="Dismiss warning"
          className="inline-flex h-7 w-7 cursor-pointer items-center justify-center rounded-md text-slate-400 transition-colors duration-150 hover:bg-slate-100 hover:text-slate-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-300"
        >
          <IconClose />
        </button>
      </div>
    </div>
  )
}
