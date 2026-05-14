import { useCallback, useEffect, useRef, useState } from 'react'

import { Button } from '../atoms/button'
import { Spinner } from '../atoms/spinner'
import {
  deleteMemoryEntry,
  listMemoryEntries,
  type MemoryEntry,
  updateMemoryEntry,
} from '../../services/memory-api'

import styles from './memory-editor.module.css'

type MemoryEditorProps = {
  projectId: string
}

function formatWhen(iso: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, {
      dateStyle: 'short',
      timeStyle: 'short',
    })
  } catch {
    return iso
  }
}

export function MemoryEditor({ projectId }: MemoryEditorProps) {
  const [entries, setEntries] = useState<MemoryEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [expanded, setExpanded] = useState<Record<string, boolean>>({})
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editSummary, setEditSummary] = useState('')
  const [editLessons, setEditLessons] = useState('')
  const [saving, setSaving] = useState(false)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<MemoryEntry | null>(null)
  const deleteDialogRef = useRef<HTMLDialogElement>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const rows = await listMemoryEntries(projectId)
      setEntries(rows)
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Failed to load memory'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }, [projectId])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    const el = deleteDialogRef.current
    if (!el) return
    if (deleteTarget) {
      if (!el.open) el.showModal()
    } else if (el.open) {
      el.close()
    }
  }, [deleteTarget])

  const toggleExpanded = (id: string) => {
    setExpanded((prev) => ({ ...prev, [id]: !prev[id] }))
  }

  const startEdit = (entry: MemoryEntry) => {
    setEditingId(entry.id)
    setEditSummary(entry.summary)
    setEditLessons(entry.lessons_learned)
    setExpanded((prev) => ({ ...prev, [entry.id]: true }))
  }

  const cancelEdit = () => {
    setEditingId(null)
    setEditSummary('')
    setEditLessons('')
  }

  const saveEdit = async () => {
    if (!editingId) return
    const id = editingId
    const prev = entries.find((e) => e.id === id)
    if (!prev) return

    const nextSummary = editSummary.trim()
    const nextLessons = editLessons.trim()
    if (!nextSummary || !nextLessons) {
      setError('Summary and lessons learned cannot be empty.')
      return
    }
    const optimistic: MemoryEntry = {
      ...prev,
      summary: nextSummary,
      lessons_learned: nextLessons,
      updated_at: new Date().toISOString(),
    }

    setEntries((list) => list.map((e) => (e.id === id ? optimistic : e)))
    setSaving(true)
    setError(null)
    try {
      const updated = await updateMemoryEntry(projectId, id, {
        summary: nextSummary,
        lessons_learned: nextLessons,
      })
      setEntries((list) => list.map((e) => (e.id === id ? updated : e)))
      cancelEdit()
    } catch (e) {
      setEntries((list) => list.map((e) => (e.id === id ? prev : e)))
      const msg = e instanceof Error ? e.message : 'Failed to update entry'
      setError(msg)
    } finally {
      setSaving(false)
    }
  }

  const requestDelete = (entry: MemoryEntry) => {
    setDeleteTarget(entry)
  }

  const closeDeleteDialog = () => {
    setDeleteTarget(null)
  }

  const confirmDelete = async () => {
    if (!deleteTarget) return
    const id = deleteTarget.id
    const snapshot = entries
    setEntries((list) => list.filter((e) => e.id !== id))
    setDeletingId(id)
    setError(null)
    closeDeleteDialog()
    try {
      await deleteMemoryEntry(projectId, id)
    } catch (e) {
      setEntries(snapshot)
      const msg = e instanceof Error ? e.message : 'Failed to delete entry'
      setError(msg)
    } finally {
      setDeletingId(null)
    }
  }

  if (loading) {
    return (
      <p className={styles.hint}>
        <Spinner /> Loading memory…
      </p>
    )
  }

  return (
    <section className={styles.root} aria-label="Project memory">
      <p className={styles.hint}>
        Lessons learned from completed tasks. Expand a row to read details or edit.
      </p>
      <div className={styles.toolbar}>
        <Button type="button" variant="secondary" onClick={() => void load()} disabled={saving || !!deletingId}>
          Refresh
        </Button>
      </div>
      {error ? (
        <p className={styles.hint} role="alert">
          {error}
        </p>
      ) : null}
      {entries.length === 0 ? (
        <p className={styles.hint}>No memory entries yet.</p>
      ) : (
        <ul className={styles.list}>
          {entries.map((entry) => {
            const isOpen = !!expanded[entry.id]
            const isEditing = editingId === entry.id
            return (
              <li key={entry.id} className={styles.card}>
                <button
                  type="button"
                  className={styles.cardHeader}
                  onClick={() => toggleExpanded(entry.id)}
                  aria-expanded={isOpen}
                >
                  <span className={styles.cardTitle}>{entry.summary || '(no summary)'}</span>
                  <span className={styles.chevron} aria-hidden>
                    {isOpen ? '▾' : '▸'}
                  </span>
                </button>
                {isOpen ? (
                  <div className={styles.cardBody}>
                    <p className={styles.meta}>
                      {entry.task_id ? `Task: ${entry.task_id} · ` : null}
                      {formatWhen(entry.entry_timestamp)}
                    </p>
                    {isEditing ? (
                      <div className={styles.form}>
                        <label className={styles.label} htmlFor={`mem-sum-${entry.id}`}>
                          Summary
                        </label>
                        <textarea
                          id={`mem-sum-${entry.id}`}
                          className={styles.textarea}
                          rows={2}
                          value={editSummary}
                          onChange={(ev) => setEditSummary(ev.target.value)}
                        />
                        <label className={styles.label} htmlFor={`mem-less-${entry.id}`}>
                          Lessons learned
                        </label>
                        <textarea
                          id={`mem-less-${entry.id}`}
                          className={styles.textarea}
                          rows={5}
                          value={editLessons}
                          onChange={(ev) => setEditLessons(ev.target.value)}
                        />
                        <div className={styles.formActions}>
                          <Button type="button" variant="primary" onClick={() => void saveEdit()} disabled={saving}>
                            {saving ? 'Saving…' : 'Save'}
                          </Button>
                          <Button type="button" variant="secondary" onClick={cancelEdit} disabled={saving}>
                            Cancel
                          </Button>
                        </div>
                      </div>
                    ) : (
                      <>
                        {entry.lessons_learned ? (
                          <p className={styles.lessons}>{entry.lessons_learned}</p>
                        ) : (
                          <p className={styles.lessons}>(No lessons text)</p>
                        )}
                        {entry.files_affected?.length ? (
                          <>
                            <p className={styles.filesHeading}>Files affected</p>
                            <ul className={styles.filesList}>
                              {entry.files_affected.map((f) => (
                                <li key={f}>{f}</li>
                              ))}
                            </ul>
                          </>
                        ) : null}
                        <div className={styles.actions}>
                          <Button type="button" variant="secondary" onClick={() => startEdit(entry)}>
                            Edit
                          </Button>
                          <Button
                            type="button"
                            variant="danger"
                            onClick={() => requestDelete(entry)}
                            disabled={deletingId === entry.id}
                          >
                            {deletingId === entry.id ? 'Deleting…' : 'Delete'}
                          </Button>
                        </div>
                      </>
                    )}
                  </div>
                ) : null}
              </li>
            )
          })}
        </ul>
      )}

      <dialog ref={deleteDialogRef} className={styles.dialog} onCancel={closeDeleteDialog}>
        <div className={styles.dialogInner}>
          <h3 className={styles.dialogTitle}>Delete memory entry?</h3>
          <p className={styles.dialogText}>
            {deleteTarget
              ? `This removes “${deleteTarget.summary.slice(0, 80)}${deleteTarget.summary.length > 80 ? '…' : ''}”.`
              : null}
          </p>
          <div className={styles.dialogActions}>
            <Button type="button" variant="secondary" onClick={closeDeleteDialog}>
              Cancel
            </Button>
            <Button type="button" variant="danger" onClick={() => void confirmDelete()}>
              Delete
            </Button>
          </div>
        </div>
      </dialog>
    </section>
  )
}
