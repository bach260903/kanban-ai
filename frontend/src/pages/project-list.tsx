import { isAxiosError } from 'axios'
import { type FormEvent, useEffect, useState } from 'react'

import { Button } from '../components/atoms/button'
import { Spinner } from '../components/atoms/spinner'
import { TextInput } from '../components/atoms/text-input'
import { createProject, listProjects } from '../services/project-api'
import { useProjectStore } from '../store/project-store'
import type { PrimaryLanguage } from '../types'

import styles from './project-list.module.css'

const LANGUAGES: PrimaryLanguage[] = ['python', 'javascript', 'typescript']

function formatUpdated(iso: string): string {
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return iso
  }
}

function messageFromUnknown(err: unknown): string {
  if (isAxiosError(err)) {
    const data = err.response?.data as { detail?: unknown } | undefined
    const d = data?.detail
    if (typeof d === 'string') return d
    if (Array.isArray(d)) {
      return d.map((x) => (typeof x === 'object' && x && 'msg' in x ? String((x as { msg: string }).msg) : String(x))).join(
        '; ',
      )
    }
    return err.message || 'Request failed'
  }
  if (err instanceof Error) return err.message
  return 'Something went wrong'
}

export default function ProjectList() {
  const { projects, setProjects } = useProjectStore()
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)

  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [language, setLanguage] = useState<PrimaryLanguage>('typescript')
  const [createError, setCreateError] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        setLoadError(null)
        setLoading(true)
        const list = await listProjects()
        if (!cancelled) setProjects(list)
      } catch (e) {
        if (!cancelled) setLoadError(messageFromUnknown(e))
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [setProjects])

  async function handleCreate(e: FormEvent) {
    e.preventDefault()
    setCreateError(null)
    const trimmed = name.trim()
    if (!trimmed) {
      setCreateError('Name is required.')
      return
    }
    setCreating(true)
    try {
      await createProject({
        name: trimmed,
        description: description.trim() === '' ? null : description.trim(),
        primary_language: language,
      })
      setName('')
      setDescription('')
      const list = await listProjects()
      setProjects(list)
    } catch (err) {
      if (isAxiosError(err) && err.response?.status === 409) {
        const data = err.response.data as { detail?: string }
        setCreateError(data.detail ?? 'A project with this name already exists.')
      } else {
        setCreateError(messageFromUnknown(err))
      }
    } finally {
      setCreating(false)
    }
  }

  return (
    <div className={styles.page}>
      <h1 className={styles.title}>Projects</h1>
      <p className={styles.sub}>Create and open Neo-Kanban projects.</p>

      <form className={styles.form} onSubmit={handleCreate} noValidate>
        <strong>New project</strong>
        <div className={styles.formRow}>
          <div className={styles.fieldGrow}>
            <TextInput
              id="project-name"
              label="Name"
              name="name"
              value={name}
              onChange={(ev) => setName(ev.target.value)}
              required
              maxLength={255}
              autoComplete="off"
              disabled={creating}
            />
          </div>
          <label className={styles.selectLabel}>
            Language
            <select
              className={styles.select}
              value={language}
              onChange={(ev) => setLanguage(ev.target.value as PrimaryLanguage)}
              disabled={creating}
              aria-label="Primary language"
            >
              {LANGUAGES.map((lang) => (
                <option key={lang} value={lang}>
                  {lang}
                </option>
              ))}
            </select>
          </label>
        </div>
        <TextInput
          id="project-description"
          label="Description (optional)"
          name="description"
          value={description}
          onChange={(ev) => setDescription(ev.target.value)}
          disabled={creating}
        />
        {createError ? <p className={styles.inlineError}>{createError}</p> : null}
        <Button type="submit" variant="primary" disabled={creating}>
          {creating ? 'Creating…' : 'Create project'}
        </Button>
      </form>

      {loadError ? <div className={styles.banner}>{loadError}</div> : null}

      {loading ? (
        <div className={styles.loading} role="status">
          <Spinner aria-label="Loading projects" />
          Loading projects…
        </div>
      ) : null}

      {!loading && !loadError && projects.length === 0 ? (
        <p className={styles.empty}>No projects yet. Create one above.</p>
      ) : null}

      {!loading && projects.length > 0 ? (
        <div className={styles.grid}>
          {projects.map((p) => (
            <article key={p.id} className={styles.card}>
              <h3>{p.name}</h3>
              <div className={styles.meta}>
                <span className={styles.lang}>{p.primary_language}</span>
                <span>{p.status}</span>
                <span>Updated {formatUpdated(p.updated_at)}</span>
              </div>
              {p.description ? <p className={styles.desc}>{p.description}</p> : null}
            </article>
          ))}
        </div>
      ) : null}
    </div>
  )
}
