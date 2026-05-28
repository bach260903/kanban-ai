import { isAxiosError } from 'axios'
import { ChevronLeft } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { Spinner } from '../components/atoms/spinner'
import { DeploymentSettings } from '../components/organisms/deployment-settings'
import { ProjectMembers } from '../components/organisms/project-members'
import { WebhookSettings } from '../components/organisms/webhook-settings'
import { getProject } from '../services/project-api'

import pageShell from './page-shell.module.css'
import styles from './project-settings.module.css'

type SettingsTab = 'members' | 'webhooks' | 'deployments'

function errorMessage(error: unknown): string {
  if (isAxiosError(error)) {
    const detail = (error.response?.data as { detail?: unknown } | undefined)?.detail
    if (typeof detail === 'string') return detail
    return error.message
  }
  if (error instanceof Error) return error.message
  return 'Unable to load project.'
}

export default function ProjectSettings() {
  const { id } = useParams()
  const [activeTab, setActiveTab] = useState<SettingsTab>('members')
  const [projectName, setProjectName] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    void (async () => {
      if (!id) {
        setError('Project ID is missing from URL.')
        setLoading(false)
        return
      }
      try {
        setLoading(true)
        setError(null)
        const project = await getProject(id)
        if (!cancelled) setProjectName(project.name)
      } catch (err) {
        if (!cancelled) setError(errorMessage(err))
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [id])

  if (!id) {
    return (
      <div className={pageShell.shell}>
        <p className={styles.error}>Project ID is missing from URL.</p>
      </div>
    )
  }

  return (
    <div className={pageShell.shell}>
      <Link to={`/projects/${id}`} className={styles.backLink}>
        <ChevronLeft size={16} aria-hidden="true" />
        {projectName ?? 'Workspace'}
      </Link>
      <h1 className={pageShell.title}>Project settings</h1>
      {projectName ? (
        <p className={pageShell.lead}>{projectName}</p>
      ) : null}

      <nav className={styles.tabs} aria-label="Settings sections">
        <button
          type="button"
          className={activeTab === 'members' ? styles.tabActive : styles.tab}
          aria-selected={activeTab === 'members'}
          onClick={() => setActiveTab('members')}
        >
          Members
        </button>
        <button
          type="button"
          className={activeTab === 'webhooks' ? styles.tabActive : styles.tab}
          aria-selected={activeTab === 'webhooks'}
          onClick={() => setActiveTab('webhooks')}
        >
          Webhooks & Integrations
        </button>
        <button
          type="button"
          className={activeTab === 'deployments' ? styles.tabActive : styles.tab}
          aria-selected={activeTab === 'deployments'}
          onClick={() => setActiveTab('deployments')}
        >
          Deployments
        </button>
      </nav>

      {loading ? (
        <p className={styles.loading}>
          <Spinner aria-label="Loading project settings" />
          Loading project…
        </p>
      ) : null}

      {error ? (
        <p className={styles.error} role="alert">
          {error}
        </p>
      ) : null}

      <div className={styles.panel}>
        {activeTab === 'members' && <ProjectMembers projectId={id} />}
        {activeTab === 'webhooks' && <WebhookSettings projectId={id} />}
        {activeTab === 'deployments' && <DeploymentSettings projectId={id} />}
      </div>
    </div>
  )
}
