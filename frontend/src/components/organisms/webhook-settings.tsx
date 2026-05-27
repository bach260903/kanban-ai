import { isAxiosError } from 'axios'
import { useCallback, useEffect, useState } from 'react'

import { Button } from '../atoms/button'
import { Spinner } from '../atoms/spinner'
import { TextInput } from '../atoms/text-input'
import { useAuth } from '../../contexts/auth-context'
import { showErrorToast, showSuccessToast } from '../../lib/toast'
import { getGitHubConfig, upsertGitHubConfig, type GitHubConfig } from '../../services/github-api'
import { getMembers } from '../../services/member-api'
import {
  createWebhook,
  deleteWebhook,
  listWebhooks,
  patchWebhook,
  testWebhook,
  type WebhookItem,
} from '../../services/webhook-api'

import styles from './webhook-settings.module.css'

const WEBHOOK_EVENTS = [
  { id: 'task.done', label: 'Task done' },
  { id: 'task.needs_review', label: 'Task needs review' },
  { id: 'agent.error', label: 'Agent error' },
] as const

type WebhookSettingsProps = {
  projectId: string
}

function truncateUrl(url: string, max = 40): string {
  if (url.length <= max) return url
  return `${url.slice(0, max - 1)}…`
}

function apiError(err: unknown, fallback: string): string {
  if (isAxiosError(err)) {
    const detail = (err.response?.data as { detail?: unknown } | undefined)?.detail
    if (typeof detail === 'string') return detail
    if (err.response?.status === 403) return 'Bạn không có quyền thực hiện thao tác này'
  }
  return fallback
}

export function WebhookSettings({ projectId }: WebhookSettingsProps) {
  const { user } = useAuth()
  const [loading, setLoading] = useState(true)
  const [webhooks, setWebhooks] = useState<WebhookItem[]>([])
  const [githubConfig, setGithubConfig] = useState<GitHubConfig | null>(null)
  const [canManageWebhooks, setCanManageWebhooks] = useState(false)
  const [canManageGithub, setCanManageGithub] = useState(false)

  const [newUrl, setNewUrl] = useState('')
  const [newSecret, setNewSecret] = useState('')
  const [newEvents, setNewEvents] = useState<string[]>(['task.done'])
  const [urlError, setUrlError] = useState<string | null>(null)
  const [savingWebhook, setSavingWebhook] = useState(false)
  const [busyWebhookId, setBusyWebhookId] = useState<string | null>(null)

  const [repoName, setRepoName] = useState('')
  const [pat, setPat] = useState('')
  const [baseBranch, setBaseBranch] = useState('main')
  const [patSaved, setPatSaved] = useState(false)
  const [savingGithub, setSavingGithub] = useState(false)

  function applyGithubConfig(gh: GitHubConfig | null) {
    setGithubConfig(gh)
    if (gh) {
      setRepoName(gh.repo_full_name)
      setBaseBranch(gh.default_base_branch)
      setPatSaved(true)
    } else {
      setRepoName('')
      setBaseBranch('main')
      setPatSaved(false)
    }
    setPat('')
  }

  const load = useCallback(async (showLoading = true) => {
    if (showLoading) setLoading(true)
    try {
      const [rows, gh, members] = await Promise.all([
        listWebhooks(projectId),
        getGitHubConfig(projectId),
        getMembers(projectId),
      ])
      setWebhooks(rows)
      applyGithubConfig(gh)
      const me = members.find((member) => member.user_id === user?.id)
      setCanManageWebhooks(me?.role === 'owner' || me?.role === 'leader')
      setCanManageGithub(me?.role === 'owner')
    } catch (err) {
      setWebhooks([])
      applyGithubConfig(null)
      setCanManageWebhooks(false)
      setCanManageGithub(false)
      showErrorToast(apiError(err, 'Không tải được cấu hình tích hợp'))
    } finally {
      if (showLoading) setLoading(false)
    }
  }, [projectId, user?.id])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    setNewUrl('')
    setNewSecret('')
    setNewEvents(['task.done'])
    setUrlError(null)
  }, [projectId])

  function toggleNewEvent(eventId: string, checked: boolean) {
    setNewEvents((prev) => {
      if (checked) return prev.includes(eventId) ? prev : [...prev, eventId]
      return prev.filter((id) => id !== eventId)
    })
  }

  function validateWebhookUrl(url: string): boolean {
    const trimmed = url.trim()
    if (!trimmed.startsWith('https://')) {
      setUrlError('URL phải bắt đầu với https://')
      return false
    }
    setUrlError(null)
    return true
  }

  async function handleCreateWebhook() {
    const url = newUrl.trim()
    if (!validateWebhookUrl(url)) {
      return
    }
    if (newEvents.length === 0) {
      showErrorToast('Chọn ít nhất một sự kiện')
      return
    }
    setSavingWebhook(true)
    try {
      await createWebhook(projectId, {
        url,
        events: newEvents,
        secret: newSecret.trim() || undefined,
      })
      showSuccessToast('Đã thêm webhook')
      setNewUrl('')
      setNewSecret('')
      setNewEvents(['task.done'])
      await load(false)
    } catch (err) {
      showErrorToast(apiError(err, 'Không tạo được webhook'))
    } finally {
      setSavingWebhook(false)
    }
  }

  async function handleToggleEnabled(webhook: WebhookItem) {
    setBusyWebhookId(webhook.id)
    try {
      await patchWebhook(projectId, webhook.id, { enabled: !webhook.enabled })
      setWebhooks((prev) =>
        prev.map((row) => (row.id === webhook.id ? { ...row, enabled: !row.enabled } : row)),
      )
    } catch (err) {
      showErrorToast(apiError(err, 'Không cập nhật được webhook'))
    } finally {
      setBusyWebhookId(null)
    }
  }

  async function handleDelete(webhook: WebhookItem) {
    if (!window.confirm('Xóa webhook này? Thao tác không thể hoàn tác.')) return
    setBusyWebhookId(webhook.id)
    try {
      await deleteWebhook(projectId, webhook.id)
      showSuccessToast('Đã xóa webhook')
      await load(false)
    } catch (err) {
      showErrorToast(apiError(err, 'Không xóa được webhook'))
    } finally {
      setBusyWebhookId(null)
    }
  }

  async function handleTest(webhook: WebhookItem) {
    if (!webhook.enabled) {
      showErrorToast('Webhook đang tắt — bật lại trước khi test')
      return
    }
    setBusyWebhookId(webhook.id)
    try {
      const result = await testWebhook(projectId, webhook.id)
      showSuccessToast(`Đã gửi: ${result.response_time_ms}ms`)
    } catch (err) {
      showErrorToast(apiError(err, 'Gửi thất bại'))
    } finally {
      setBusyWebhookId(null)
    }
  }

  async function handleSaveGithub() {
    const repo = repoName.trim()
    if (!repo.includes('/')) {
      showErrorToast('Repo phải có dạng owner/repo')
      return
    }
    if (!pat.trim() && !patSaved) {
      showErrorToast('Nhập Personal Access Token')
      return
    }
    if (!pat.trim()) {
      showErrorToast('Nhập PAT mới để cập nhật cấu hình GitHub')
      return
    }
    setSavingGithub(true)
    try {
      const saved = await upsertGitHubConfig(projectId, {
        repo_full_name: repo,
        pat: pat.trim(),
        default_base_branch: baseBranch.trim() || 'main',
      })
      applyGithubConfig(saved)
      showSuccessToast('Đã lưu và xác thực GitHub')
    } catch (err) {
      showErrorToast(apiError(err, 'PAT hoặc repository không hợp lệ'))
    } finally {
      setSavingGithub(false)
    }
  }

  if (loading) {
    return (
      <p className={styles.loading}>
        <Spinner aria-label="Loading integrations" />
        Đang tải…
      </p>
    )
  }

  return (
    <div className={styles.root}>
      <section className={styles.section} aria-labelledby="webhooks-heading">
        <h2 id="webhooks-heading" className={styles.sectionTitle}>
          Webhooks
        </h2>
        {webhooks.length === 0 ? (
          <p className={styles.empty}>Chưa có webhook nào.</p>
        ) : (
          <ul className={styles.list}>
            {webhooks.map((webhook) => (
              <li key={webhook.id} className={styles.row}>
                <p className={styles.url} title={webhook.url}>
                  {truncateUrl(webhook.url)}
                </p>
                <div className={styles.chips}>
                  {webhook.events.map((event) => (
                    <span key={event} className={styles.chip}>
                      {event}
                    </span>
                  ))}
                </div>
                <div className={styles.rowActions}>
                  <label className={styles.toggle}>
                    <input
                      type="checkbox"
                      checked={webhook.enabled}
                      disabled={!canManageWebhooks || busyWebhookId === webhook.id}
                      onChange={() => void handleToggleEnabled(webhook)}
                    />
                    Bật
                  </label>
                  <Button
                    type="button"
                    variant="secondary"
                    disabled={
                      !canManageWebhooks || !webhook.enabled || busyWebhookId === webhook.id
                    }
                    onClick={() => void handleTest(webhook)}
                  >
                    Test
                  </Button>
                  <Button
                    type="button"
                    variant="danger"
                    disabled={!canManageWebhooks || busyWebhookId === webhook.id}
                    onClick={() => void handleDelete(webhook)}
                  >
                    Xóa
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}

        {canManageWebhooks ? (
          <div className={styles.addForm}>
            <h3 className={styles.addTitle}>Thêm webhook</h3>
            <TextInput
              label="URL"
              value={newUrl}
              onChange={(e) => {
                setNewUrl(e.target.value)
                if (urlError) setUrlError(null)
              }}
              onBlur={() => {
                if (newUrl.trim()) validateWebhookUrl(newUrl)
              }}
              placeholder="https://example.com/hook"
              disabled={savingWebhook}
              invalid={!!urlError}
              hint={urlError ?? undefined}
            />
            <div className={styles.events}>
              <span className={styles.eventsLabel}>Sự kiện</span>
              {WEBHOOK_EVENTS.map((event) => (
                <label key={event.id} className={styles.eventOption}>
                  <input
                    type="checkbox"
                    checked={newEvents.includes(event.id)}
                    disabled={savingWebhook}
                    onChange={(e) => toggleNewEvent(event.id, e.target.checked)}
                  />
                  {event.label}
                </label>
              ))}
            </div>
            <TextInput
              label="Secret (tùy chọn)"
              type="password"
              value={newSecret}
              onChange={(e) => setNewSecret(e.target.value)}
              disabled={savingWebhook}
              autoComplete="off"
            />
            <Button
              type="button"
              variant="primary"
              disabled={savingWebhook}
              onClick={() => void handleCreateWebhook()}
            >
              {savingWebhook ? 'Đang lưu…' : 'Lưu'}
            </Button>
          </div>
        ) : (
          <p className={styles.hint}>Chỉ leader hoặc owner mới có thể quản lý webhook.</p>
        )}
      </section>

      <section className={styles.section} aria-labelledby="github-heading">
        <h2 id="github-heading" className={styles.sectionTitle}>
          GitHub
        </h2>
        {githubConfig ? (
          <p className={styles.hint}>
            Repo hiện tại: <strong>{githubConfig.repo_full_name}</strong> (base:{' '}
            {githubConfig.default_base_branch})
          </p>
        ) : (
          <p className={styles.empty}>Chưa cấu hình GitHub.</p>
        )}
        {canManageGithub ? (
          <div className={styles.addForm}>
            <div className={styles.formRow}>
              <TextInput
                label="Repository (owner/repo)"
                value={repoName}
                onChange={(e) => setRepoName(e.target.value)}
                placeholder="owner/repo"
                disabled={savingGithub}
              />
              <TextInput
                label="Base branch"
                value={baseBranch}
                onChange={(e) => setBaseBranch(e.target.value)}
                disabled={savingGithub}
              />
            </div>
            {patSaved && !pat ? (
              <p className={styles.patSaved}>PAT: ••••••••</p>
            ) : null}
            <TextInput
              label="Personal Access Token"
              type="password"
              value={pat}
              onChange={(e) => setPat(e.target.value)}
              placeholder={patSaved ? 'Nhập PAT mới để thay đổi' : 'ghp_…'}
              disabled={savingGithub}
              autoComplete="off"
            />
            <Button
              type="button"
              variant="primary"
              disabled={savingGithub}
              onClick={() => void handleSaveGithub()}
            >
              {savingGithub ? 'Đang xác thực…' : 'Lưu & Validate'}
            </Button>
          </div>
        ) : (
          <p className={styles.hint}>Chỉ owner mới có thể cấu hình GitHub.</p>
        )}
      </section>
    </div>
  )
}
