import { isAxiosError } from 'axios'
import { useEffect, useState } from 'react'

import { Button } from '../atoms/button'
import { TemplateSelector } from './template-selector'
import { createTask } from '../../services/task-api'

import modalStyles from '../organisms/new-project-modal.module.css'

export type CreateTaskModalProps = {
  open: boolean
  projectId: string
  onClose: () => void
  onCreated: () => void
}

function errorMessage(err: unknown): string {
  if (isAxiosError(err)) {
    const detail = (err.response?.data as { detail?: unknown } | undefined)?.detail
    if (typeof detail === 'string') return detail
    return err.message
  }
  if (err instanceof Error) return err.message
  return 'Unable to create task.'
}

export function CreateTaskModal({ open, projectId, onClose, onCreated }: CreateTaskModalProps) {
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [templateKey, setTemplateKey] = useState(0)

  useEffect(() => {
    if (!open) return
    setTitle('')
    setDescription('')
    setError(null)
    setTemplateKey((k) => k + 1)
  }, [open])

  if (!open) return null

  function handleDismiss() {
    if (busy) return
    onClose()
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    const trimmed = title.trim()
    if (!trimmed) return
    setBusy(true)
    setError(null)
    try {
      await createTask(projectId, {
        title: trimmed,
        description: description.trim() || undefined,
      })
      onCreated()
      onClose()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className={modalStyles.backdrop} role="presentation" onClick={handleDismiss}>
      <div
        className={modalStyles.modal}
        role="dialog"
        aria-modal="true"
        aria-labelledby="create-task-title"
        onClick={(e) => e.stopPropagation()}
      >
        <header className={modalStyles.header}>
          <h2 id="create-task-title" className={modalStyles.title}>
            Thêm task mới
          </h2>
          <button
            type="button"
            className={modalStyles.closeBtn}
            onClick={handleDismiss}
            disabled={busy}
            aria-label="Close"
          >
            ×
          </button>
        </header>

        <form onSubmit={(e) => void handleSubmit(e)} className={modalStyles.body}>
          {error ? (
            <p className={modalStyles.inlineError} role="alert">
              {error}
            </p>
          ) : null}

          <TemplateSelector
            key={templateKey}
            projectId={projectId}
            onSelect={(t, d) => {
              setTitle(t)
              setDescription(d)
            }}
          />

          <div className={modalStyles.field}>
            <label htmlFor="create-task-title-input" className={modalStyles.label}>
              Tiêu đề
              <span className={modalStyles.required} aria-hidden="true">
                *
              </span>
            </label>
            <input
              id="create-task-title-input"
              type="text"
              className={modalStyles.input}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              required
              maxLength={500}
              disabled={busy}
            />
          </div>

          <div className={modalStyles.field}>
            <label htmlFor="create-task-description" className={modalStyles.label}>
              Mô tả
            </label>
            <textarea
              id="create-task-description"
              rows={4}
              className={modalStyles.textarea}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              disabled={busy}
              placeholder="Optional"
            />
          </div>

          <footer className={modalStyles.footer}>
            <Button type="button" variant="secondary" onClick={handleDismiss} disabled={busy}>
              Hủy
            </Button>
            <Button type="submit" variant="primary" disabled={busy || !title.trim()}>
              {busy ? 'Đang tạo…' : 'Tạo task'}
            </Button>
          </footer>
        </form>
      </div>
    </div>
  )
}
