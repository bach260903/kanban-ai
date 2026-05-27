import { isAxiosError } from 'axios'
import { useEffect, useState } from 'react'

import { Button } from '../atoms/button'
import { showErrorToast, showSuccessToast } from '../../lib/toast'
import { createTemplate } from '../../services/template-api'

import modalStyles from '../organisms/new-project-modal.module.css'

export type SaveAsTemplateModalProps = {
  open: boolean
  projectId: string
  taskTitle: string
  taskDescription: string | null
  onClose: () => void
}

function errorMessage(err: unknown): string {
  if (isAxiosError(err)) {
    const detail = (err.response?.data as { detail?: unknown } | undefined)?.detail
    if (typeof detail === 'string') return detail
    return err.message
  }
  if (err instanceof Error) return err.message
  return 'Unable to save template.'
}

export function SaveAsTemplateModal({
  open,
  projectId,
  taskTitle,
  taskDescription,
  onClose,
}: SaveAsTemplateModalProps) {
  const [name, setName] = useState('')
  const [scope, setScope] = useState<'project' | 'global'>('project')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!open) return
    setName('')
    setScope('project')
    setBusy(false)
  }, [open, taskTitle])

  if (!open) return null

  function clearForm() {
    setName('')
    setScope('project')
  }

  function handleDismiss() {
    if (busy) return
    clearForm()
    onClose()
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    const trimmed = name.trim()
    const trimmedTitle = taskTitle.trim()
    if (!trimmed) return
    if (!trimmedTitle) {
      showErrorToast('Task phải có tiêu đề trước khi lưu template.')
      return
    }
    setBusy(true)
    try {
      await createTemplate({
        name: trimmed,
        title_template: trimmedTitle,
        description_template: (taskDescription ?? '').trim(),
        scope,
        project_id: scope === 'project' ? projectId : null,
      })
      showSuccessToast('Template đã được lưu.')
      clearForm()
      onClose()
    } catch (err) {
      showErrorToast(errorMessage(err))
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
        aria-labelledby="save-template-title"
        onClick={(e) => e.stopPropagation()}
      >
        <header className={modalStyles.header}>
          <h2 id="save-template-title" className={modalStyles.title}>
            Lưu làm template
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
          <div className={modalStyles.field}>
            <label htmlFor="template-name" className={modalStyles.label}>
              Tên template
              <span className={modalStyles.required} aria-hidden="true">
                *
              </span>
            </label>
            <input
              id="template-name"
              type="text"
              className={modalStyles.input}
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              maxLength={100}
              disabled={busy}
              placeholder={taskTitle.slice(0, 60)}
            />
          </div>

          <div className={modalStyles.field}>
            <label htmlFor="template-scope" className={modalStyles.label}>
              Phạm vi
            </label>
            <select
              id="template-scope"
              className={modalStyles.input}
              value={scope}
              onChange={(e) => setScope(e.target.value as 'project' | 'global')}
              disabled={busy}
            >
              <option value="project">Project này</option>
              <option value="global">Global (mọi project)</option>
            </select>
          </div>

          <p className="text-xs leading-relaxed text-slate-500">
            Tiêu đề và mô tả hiện tại của task sẽ được lưu vào template.
          </p>

          <footer className={modalStyles.footer}>
            <Button type="button" variant="secondary" onClick={handleDismiss} disabled={busy}>
              Hủy
            </Button>
            <Button type="submit" variant="primary" disabled={busy || !name.trim()}>
              {busy ? 'Đang lưu…' : 'Lưu template'}
            </Button>
          </footer>
        </form>
      </div>
    </div>
  )
}
