import { X } from 'lucide-react'
import {
  type FormEvent,
  type KeyboardEvent,
  type MouseEvent,
  useEffect,
  useRef,
  useState,
} from 'react'

import type { CodingBackend, PrimaryLanguage } from '../../types'
import { Button } from '../atoms/button'
import { BackendSelector } from '../molecules/backend-selector'

import styles from './new-project-modal.module.css'

const LANGUAGES: PrimaryLanguage[] = ['typescript', 'python', 'javascript']

export type NewProjectFormValues = {
  name: string
  description: string
  language: PrimaryLanguage
  backend: CodingBackend
}

export type NewProjectModalProps = {
  open: boolean
  onClose: () => void
  onSubmit: (values: NewProjectFormValues) => Promise<void>
}

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'

export function NewProjectModal({ open, onClose, onSubmit }: NewProjectModalProps) {
  const modalRef = useRef<HTMLDivElement>(null)
  const nameInputRef = useRef<HTMLInputElement>(null)
  const previouslyFocused = useRef<HTMLElement | null>(null)

  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [language, setLanguage] = useState<PrimaryLanguage>('typescript')
  const [backend, setBackend] = useState<CodingBackend>('groq')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    if (!open) return
    previouslyFocused.current = document.activeElement as HTMLElement | null
    setName('')
    setDescription('')
    setLanguage('typescript')
    setBackend('groq')
    setError(null)
    setSubmitting(false)
    const id = window.setTimeout(() => nameInputRef.current?.focus(), 30)
    const prevOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      window.clearTimeout(id)
      document.body.style.overflow = prevOverflow
      previouslyFocused.current?.focus()
    }
  }, [open])

  function handleKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === 'Escape') {
      event.stopPropagation()
      if (!submitting) onClose()
      return
    }
    if (event.key !== 'Tab') return
    const node = modalRef.current
    if (!node) return
    const focusables = Array.from(
      node.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR),
    ).filter((el) => !el.hasAttribute('disabled'))
    if (focusables.length === 0) return
    const first = focusables[0]
    const last = focusables[focusables.length - 1]
    const active = document.activeElement as HTMLElement | null
    if (event.shiftKey && active === first) {
      event.preventDefault()
      last.focus()
    } else if (!event.shiftKey && active === last) {
      event.preventDefault()
      first.focus()
    }
  }

  function handleBackdropClick(event: MouseEvent<HTMLDivElement>) {
    if (submitting) return
    if (event.target === event.currentTarget) onClose()
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    const trimmed = name.trim()
    if (!trimmed) {
      setError('Name is required.')
      nameInputRef.current?.focus()
      return
    }
    setSubmitting(true)
    try {
      await onSubmit({
        name: trimmed,
        description: description.trim(),
        language,
        backend,
      })
    } catch (err) {
      setSubmitting(false)
      setError(err instanceof Error ? err.message : 'Could not create project.')
    }
  }

  if (!open) return null

  return (
    <div
      className={styles.backdrop}
      role="presentation"
      onClick={handleBackdropClick}
      onKeyDown={handleKeyDown}
    >
      <div
        ref={modalRef}
        className={styles.modal}
        role="dialog"
        aria-modal="true"
        aria-labelledby="new-project-modal-title"
      >
        <header className={styles.header}>
          <h2 id="new-project-modal-title" className={styles.title}>
            Create New Project
          </h2>
          <button
            type="button"
            className={styles.closeBtn}
            onClick={onClose}
            aria-label="Close dialog"
            disabled={submitting}
          >
            <X size={18} aria-hidden="true" />
          </button>
        </header>

        <form onSubmit={handleSubmit} noValidate>
          <div className={styles.body}>
            {error ? (
              <p className={styles.inlineError} role="alert">
                {error}
              </p>
            ) : null}

            <div className={styles.field}>
              <label htmlFor="project-name" className={styles.label}>
                Project Name
                <span className={styles.required} aria-hidden="true">
                  *
                </span>
              </label>
              <input
                ref={nameInputRef}
                id="project-name"
                name="name"
                type="text"
                className={styles.input}
                value={name}
                onChange={(ev) => setName(ev.target.value)}
                required
                maxLength={255}
                autoComplete="off"
                disabled={submitting}
              />
            </div>

            <div className={styles.field}>
              <label htmlFor="project-description" className={styles.label}>
                Description
              </label>
              <textarea
                id="project-description"
                name="description"
                rows={3}
                className={styles.textarea}
                value={description}
                onChange={(ev) => setDescription(ev.target.value)}
                disabled={submitting}
                placeholder="What is this project about? (optional)"
              />
            </div>

            <div className={styles.formGrid}>
              <div className={styles.field}>
                <label htmlFor="project-language" className={styles.label}>
                  Language
                  <span className={styles.required} aria-hidden="true">
                    *
                  </span>
                </label>
                <select
                  id="project-language"
                  name="language"
                  className={styles.select}
                  value={language}
                  onChange={(ev) => setLanguage(ev.target.value as PrimaryLanguage)}
                  disabled={submitting}
                  required
                >
                  {LANGUAGES.map((lang) => (
                    <option key={lang} value={lang}>
                      {lang}
                    </option>
                  ))}
                </select>
              </div>

              <div className={styles.field}>
                <label htmlFor="project-backend" className={styles.label}>
                  AI Backend
                  <span className={styles.required} aria-hidden="true">
                    *
                  </span>
                </label>
                <BackendSelector
                  id="project-backend"
                  name="backend"
                  className={styles.select}
                  value={backend}
                  onChange={setBackend}
                  disabled={submitting}
                />
              </div>
            </div>
          </div>

          <footer className={styles.footer}>
            <Button
              type="button"
              variant="secondary"
              onClick={onClose}
              disabled={submitting}
            >
              Cancel
            </Button>
            <Button type="submit" variant="primary" disabled={submitting}>
              {submitting ? 'Creating…' : 'Create Project'}
            </Button>
          </footer>
        </form>
      </div>
    </div>
  )
}
