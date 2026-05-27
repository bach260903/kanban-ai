import axios, { isAxiosError } from 'axios'
import { Plus } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'

import { Button } from '../components/atoms/button'
import { EmptyState } from '../components/molecules/empty-state'
import {
  NewProjectModal,
  type NewProjectFormValues,
} from '../components/organisms/new-project-modal'
import { ProjectCard } from '../components/organisms/project-card'
import { ProjectCardSkeleton } from '../components/organisms/project-card-skeleton'
import { createProject, listProjects } from '../services/project-api'
import { useProjectStore } from '../store/project-store'

import styles from './project-list.module.css'

const SKELETON_COUNT = 6
/** Skip a refetch if the cached list is younger than this (StrictMode-friendly). */
const STALE_TIME_MS = 60_000

function messageFromUnknown(err: unknown): string {
  if (isAxiosError(err)) {
    if (err.code === 'ECONNABORTED' || err.message.includes('timeout')) {
      return (
        'Backend không phản hồi (timeout 30s). Kiểm tra uvicorn port 8000, Postgres/Redis, ' +
        'rồi mở /dev/auth để lấy JWT nếu chưa đăng nhập.'
      )
    }
    if (err.response?.status === 401) {
      return 'Chưa có JWT. Mở /dev/auth để lấy dev token (cần DEV_AUTH_ENABLED=true trên backend).'
    }
    const data = err.response?.data as { detail?: unknown } | undefined
    const d = data?.detail
    if (typeof d === 'string') return d
    if (Array.isArray(d)) {
      return d
        .map((x) => (typeof x === 'object' && x && 'msg' in x ? String((x as { msg: string }).msg) : String(x)))
        .join('; ')
    }
    return err.message || 'Request failed'
  }
  if (err instanceof Error) return err.message
  return 'Something went wrong'
}

/**
 * Module-scoped fetch timestamp — a StrictMode-safe dedupe guard. Two effect
 * setups within ~60s reuse the cached store payload instead of issuing a second
 * GET /api/v1/projects. Production (no StrictMode) hits the network exactly once.
 */
let lastFetchedAt = 0

export default function ProjectList() {
  const { projects, setProjects } = useProjectStore()
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [modalOpen, setModalOpen] = useState(false)

  useEffect(() => {
    const ac = new AbortController()
    const fresh = Date.now() - lastFetchedAt < STALE_TIME_MS

    if (fresh && projects.length > 0) {
      setLoading(false)
      return () => ac.abort()
    }

    setLoadError(null)
    setLoading(true)
    ;(async () => {
      try {
        const list = await listProjects({ signal: ac.signal })
        if (ac.signal.aborted) return
        setProjects(list)
        lastFetchedAt = Date.now()
      } catch (e) {
        if (ac.signal.aborted) return
        if (axios.isCancel(e)) return
        setLoadError(messageFromUnknown(e))
      } finally {
        if (!ac.signal.aborted) setLoading(false)
      }
    })()

    return () => ac.abort()
  }, [setProjects, projects.length])

  const handleCreate = useCallback(
    async (values: NewProjectFormValues) => {
      await createProject({
        name: values.name,
        description: values.description === '' ? null : values.description,
        primary_language: values.language,
        coding_backend: values.backend,
      })
      const list = await listProjects()
      lastFetchedAt = Date.now()
      setProjects(list)
      setModalOpen(false)
    },
    [setProjects],
  )

  const handleCreateWithError = useCallback(
    async (values: NewProjectFormValues) => {
      try {
        await handleCreate(values)
      } catch (err) {
        if (isAxiosError(err) && err.response?.status === 409) {
          const data = err.response.data as { detail?: string }
          throw new Error(data.detail ?? 'A project with this name already exists.')
        }
        throw new Error(messageFromUnknown(err))
      }
    },
    [handleCreate],
  )

  const count = projects.length

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div className={styles.headerText}>
          <h1 className={styles.title}>Projects</h1>
          <p className={styles.sub}>Create and open Neo-Kanban projects.</p>
        </div>
        <Button
          type="button"
          variant="primary"
          className={styles.newBtn}
          onClick={() => setModalOpen(true)}
        >
          <Plus size={16} aria-hidden="true" />
          New Project
        </Button>
      </div>

      {loadError ? <div className={styles.banner}>{loadError}</div> : null}

      {loading ? (
        <section
          className={styles.section}
          aria-busy="true"
          aria-live="polite"
          aria-label="Loading projects"
        >
          <div className={styles.grid}>
            {Array.from({ length: SKELETON_COUNT }).map((_, i) => (
              <ProjectCardSkeleton key={i} />
            ))}
          </div>
        </section>
      ) : count === 0 && !loadError ? (
        <EmptyState onCreate={() => setModalOpen(true)} />
      ) : (
        <section className={styles.section} aria-labelledby="projects-section-title">
          <div className={styles.sectionHeader}>
            <h2 id="projects-section-title" className={styles.sectionTitle}>
              Your Projects
              <span className={styles.sectionCount}>({count})</span>
            </h2>
          </div>
          <div className={styles.grid}>
            {projects.map((p) => (
              <ProjectCard key={p.id} project={p} />
            ))}
          </div>
        </section>
      )}

      <NewProjectModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onSubmit={handleCreateWithError}
      />
    </div>
  )
}
