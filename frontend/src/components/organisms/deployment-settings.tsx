/**
 * DeploymentSettings — configure Vercel/Railway auto-deployment for a project.
 * Used inside project-settings.tsx Deployments tab.
 */

import { isAxiosError } from 'axios'
import { Bell, CheckCircle2, ExternalLink, Rocket, Save, TestTube2, Trash2, XCircle } from 'lucide-react'
import { useEffect, useState } from 'react'

import { Spinner } from '../atoms/spinner'
import {
  deleteDeploymentConfig,
  getDeploymentConfig,
  testDeploymentConfig,
  upsertDeploymentConfig,
  type DeploymentConfigOut,
} from '../../services/deployment-api'
import { getAlertConfig, updateAlertConfig, type AlertConfigOut } from '../../services/devops-api'

import styles from './deployment-settings.module.css'

type Props = { projectId: string }

function errMsg(err: unknown): string {
  if (isAxiosError(err)) return (err.response?.data as { detail?: string })?.detail ?? err.message
  if (err instanceof Error) return err.message
  return 'Unknown error'
}

export function DeploymentSettings({ projectId }: Props) {
  const [config, setConfig] = useState<DeploymentConfigOut | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [testResult, setTestResult] = useState<{ ok: boolean; message: string } | null>(null)

  // Provider form state
  const [provider, setProvider] = useState<'vercel' | 'railway' | 'none'>('none')
  const [token, setToken] = useState('')
  const [projectName, setProjectName] = useState('')
  const [teamId, setTeamId] = useState('')
  const [baseUrl, setBaseUrl] = useState('')
  const [enabled, setEnabled] = useState(true)

  // Alert config state
  const [alertCfg, setAlertCfg] = useState<AlertConfigOut | null>(null)
  const [discordUrl, setDiscordUrl] = useState('')
  const [slackUrl, setSlackUrl] = useState('')
  const [healthPath, setHealthPath] = useState('/health')
  const [alertOnAnomaly, setAlertOnAnomaly] = useState(true)
  const [monitorMins, setMonitorMins] = useState(5)
  const [savingAlert, setSavingAlert] = useState(false)
  const [alertSaved, setAlertSaved] = useState(false)

  useEffect(() => {
    let cancelled = false
    void (async () => {
      try {
        const [cfg, alert] = await Promise.allSettled([
          getDeploymentConfig(projectId),
          getAlertConfig(projectId),
        ])
        if (!cancelled) {
          if (cfg.status === 'fulfilled' && cfg.value) {
            setConfig(cfg.value)
            setProvider(cfg.value.provider)
            setProjectName(cfg.value.project_name)
            setTeamId(cfg.value.team_id ?? '')
            setBaseUrl(cfg.value.base_url ?? '')
            setEnabled(cfg.value.enabled)
          }
          if (alert.status === 'fulfilled') {
            const a = alert.value
            setAlertCfg(a)
            setDiscordUrl(a.discord_webhook_url ?? '')
            setSlackUrl(a.slack_webhook_url ?? '')
            setHealthPath(a.health_check_path ?? '/health')
            setAlertOnAnomaly(a.alert_on_anomaly)
            setMonitorMins(a.monitor_duration_minutes)
          }
        }
      } catch (err) {
        if (!cancelled) setError(errMsg(err))
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => { cancelled = true }
  }, [projectId])

  async function handleSaveAlert(e: React.FormEvent) {
    e.preventDefault()
    setSavingAlert(true)
    setAlertSaved(false)
    try {
      const updated = await updateAlertConfig(projectId, {
        discord_webhook_url: discordUrl || null,
        slack_webhook_url: slackUrl || null,
        health_check_path: healthPath || '/health',
        alert_on_anomaly: alertOnAnomaly,
        monitor_duration_minutes: monitorMins,
      })
      setAlertCfg(updated)
      setAlertSaved(true)
      setTimeout(() => setAlertSaved(false), 3000)
    } catch (err) {
      setError(errMsg(err))
    } finally {
      setSavingAlert(false)
    }
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true)
    setError(null)
    setTestResult(null)
    try {
      const cfg = await upsertDeploymentConfig(projectId, {
        provider,
        token,
        project_name: projectName,
        team_id: teamId || null,
        base_url: baseUrl || null,
        enabled,
      })
      setConfig(cfg)
      setToken('') // clear token from form after save
    } catch (err) {
      setError(errMsg(err))
    } finally {
      setSaving(false)
    }
  }

  async function handleTest() {
    if (!token || !projectName) return
    setTesting(true)
    setTestResult(null)
    try {
      const result = await testDeploymentConfig(projectId, {
        provider,
        token,
        project_name: projectName,
        team_id: teamId || null,
      })
      setTestResult(result)
    } catch (err) {
      setTestResult({ ok: false, message: errMsg(err) })
    } finally {
      setTesting(false)
    }
  }

  async function handleDelete() {
    if (!window.confirm('Remove deployment configuration? This cannot be undone.')) return
    setDeleting(true)
    try {
      await deleteDeploymentConfig(projectId)
      setConfig(null)
      setProvider('none')
      setToken('')
      setProjectName('')
      setTeamId('')
      setBaseUrl('')
    } catch (err) {
      setError(errMsg(err))
    } finally {
      setDeleting(false)
    }
  }

  if (loading) return <div className={styles.loading}><Spinner /> Loading…</div>

  return (
    <div className={styles.root}>
      <div className={styles.header}>
        <Rocket size={18} className={styles.headerIcon} aria-hidden />
        <div>
          <h2 className={styles.title}>Deployment Provider</h2>
          <p className={styles.sub}>
            Configure automatic preview deployments after every successful CI run.
          </p>
        </div>
      </div>

      {config && (
        <div className={styles.currentCard}>
          <span className={`${styles.providerBadge} ${styles[`badge_${config.provider}`]}`}>
            {config.provider.toUpperCase()}
          </span>
          <span className={styles.currentProject}>{config.project_name}</span>
          {config.enabled ? (
            <span className={styles.enabledPill}>Active</span>
          ) : (
            <span className={styles.disabledPill}>Disabled</span>
          )}
          <button
            type="button"
            className={styles.deleteBtn}
            onClick={() => void handleDelete()}
            disabled={deleting}
            title="Remove configuration"
          >
            {deleting ? <Spinner /> : <Trash2 size={14} />}
          </button>
        </div>
      )}

      <form className={styles.form} onSubmit={(e) => void handleSave(e)}>
        {/* Provider */}
        <div className={styles.field}>
          <label className={styles.label} htmlFor="deploy-provider">Provider</label>
          <select
            id="deploy-provider"
            className={styles.select}
            value={provider}
            onChange={(e) => setProvider(e.target.value as 'vercel' | 'railway' | 'none')}
          >
            <option value="none">None (disable deployments)</option>
            <option value="vercel">Vercel</option>
            <option value="railway">Railway</option>
          </select>
        </div>

        {provider !== 'none' && (
          <>
            {/* API Token */}
            <div className={styles.field}>
              <label className={styles.label} htmlFor="deploy-token">
                {provider === 'vercel' ? 'Vercel API Token' : 'Railway API Token'}
                <span className={styles.required}>*</span>
              </label>
              <input
                id="deploy-token"
                type="password"
                className={styles.input}
                placeholder={config ? '••••••••  (leave blank to keep existing)' : 'Enter API token'}
                value={token}
                onChange={(e) => setToken(e.target.value)}
                required={!config}
                autoComplete="new-password"
              />
              <p className={styles.hint}>
                {provider === 'vercel' ? (
                  <>Get your token at{' '}
                    <a href="https://vercel.com/account/tokens" target="_blank" rel="noopener noreferrer"
                       className={styles.link}>vercel.com/account/tokens <ExternalLink size={10} /></a>
                  </>
                ) : (
                  <>Get your token at{' '}
                    <a href="https://railway.app/account/tokens" target="_blank" rel="noopener noreferrer"
                       className={styles.link}>railway.app/account/tokens <ExternalLink size={10} /></a>
                  </>
                )}
              </p>
            </div>

            {/* Project name / ID */}
            <div className={styles.field}>
              <label className={styles.label} htmlFor="deploy-project">
                {provider === 'vercel' ? 'Vercel Project Name' : 'Railway Service ID'}
                <span className={styles.required}>*</span>
              </label>
              <input
                id="deploy-project"
                type="text"
                className={styles.input}
                placeholder={provider === 'vercel' ? 'my-app' : 'service-id-here'}
                value={projectName}
                onChange={(e) => setProjectName(e.target.value)}
                required
              />
            </div>

            {/* Team ID */}
            <div className={styles.field}>
              <label className={styles.label} htmlFor="deploy-team">
                {provider === 'vercel' ? 'Team ID (optional)' : 'Environment ID (optional)'}
              </label>
              <input
                id="deploy-team"
                type="text"
                className={styles.input}
                placeholder={provider === 'vercel' ? 'team_xxxxxxxx' : 'environment-id'}
                value={teamId}
                onChange={(e) => setTeamId(e.target.value)}
              />
            </div>

            {/* Base URL */}
            <div className={styles.field}>
              <label className={styles.label} htmlFor="deploy-base-url">
                Preview base URL (optional)
              </label>
              <input
                id="deploy-base-url"
                type="url"
                className={styles.input}
                placeholder="https://myapp.vercel.app"
                value={baseUrl}
                onChange={(e) => setBaseUrl(e.target.value)}
              />
            </div>

            {/* Enabled toggle */}
            <div className={styles.fieldRow}>
              <input
                id="deploy-enabled"
                type="checkbox"
                checked={enabled}
                onChange={(e) => setEnabled(e.target.checked)}
                className={styles.checkbox}
              />
              <label htmlFor="deploy-enabled" className={styles.checkboxLabel}>
                Enable auto-deploy on CI success
              </label>
            </div>

            {/* Test connection */}
            {testResult && (
              <div className={testResult.ok ? styles.testOk : styles.testFail}>
                {testResult.ok
                  ? <CheckCircle2 size={13} aria-hidden />
                  : <XCircle size={13} aria-hidden />}
                {testResult.message}
              </div>
            )}

            <div className={styles.actions}>
              <button
                type="button"
                className={styles.testBtn}
                onClick={() => void handleTest()}
                disabled={testing || !token || !projectName}
              >
                {testing ? <Spinner /> : <TestTube2 size={14} aria-hidden />}
                {testing ? 'Testing…' : 'Test connection'}
              </button>
              <button
                type="submit"
                className={styles.saveBtn}
                disabled={saving}
              >
                {saving ? <Spinner /> : <Save size={14} aria-hidden />}
                {saving ? 'Saving…' : config ? 'Update config' : 'Save config'}
              </button>
            </div>
          </>
        )}

        {provider === 'none' && config && (
          <div className={styles.actions}>
            <button type="submit" className={styles.saveBtn} disabled={saving}>
              {saving ? <Spinner /> : <Save size={14} aria-hidden />}
              {saving ? 'Saving…' : 'Disable deployments'}
            </button>
          </div>
        )}

        {error && <p className={styles.error} role="alert">{error}</p>}
      </form>

      {/* ── Alert & monitoring config ──────────────────────────────────────── */}
      {config && config.provider !== 'none' && (
        <div className={styles.alertSection}>
          <div className={styles.header}>
            <Bell size={16} className={styles.headerIcon} aria-hidden />
            <div>
              <h2 className={styles.title}>Health Monitoring &amp; Alerts</h2>
              <p className={styles.sub}>
                Configure post-deploy health checks and incident notifications.
              </p>
            </div>
          </div>

          <form className={styles.form} onSubmit={(e) => void handleSaveAlert(e)}>
            {/* Health check path */}
            <div className={styles.field}>
              <label className={styles.label} htmlFor="health-path">Health check path</label>
              <input
                id="health-path"
                type="text"
                className={styles.input}
                placeholder="/health"
                value={healthPath}
                onChange={(e) => setHealthPath(e.target.value)}
              />
              <p className={styles.hint}>Endpoint polled after every successful deploy.</p>
            </div>

            {/* Monitor duration */}
            <div className={styles.field}>
              <label className={styles.label} htmlFor="monitor-mins">Monitor duration (minutes)</label>
              <input
                id="monitor-mins"
                type="number"
                min={1}
                max={60}
                className={styles.input}
                value={monitorMins}
                onChange={(e) => setMonitorMins(Number(e.target.value))}
              />
            </div>

            {/* Alert on anomaly toggle */}
            <div className={styles.fieldRow}>
              <input
                id="alert-anomaly"
                type="checkbox"
                checked={alertOnAnomaly}
                onChange={(e) => setAlertOnAnomaly(e.target.checked)}
                className={styles.checkbox}
              />
              <label htmlFor="alert-anomaly" className={styles.checkboxLabel}>
                Send alerts on anomaly / rollback events
              </label>
            </div>

            {/* Discord webhook */}
            <div className={styles.field}>
              <label className={styles.label} htmlFor="discord-url">
                Discord webhook URL
                <span className={styles.optionalTag}>optional</span>
              </label>
              <input
                id="discord-url"
                type="url"
                className={styles.input}
                placeholder="https://discord.com/api/webhooks/…"
                value={discordUrl}
                onChange={(e) => setDiscordUrl(e.target.value)}
              />
            </div>

            {/* Slack webhook */}
            <div className={styles.field}>
              <label className={styles.label} htmlFor="slack-url">
                Slack webhook URL
                <span className={styles.optionalTag}>optional</span>
              </label>
              <input
                id="slack-url"
                type="url"
                className={styles.input}
                placeholder="https://hooks.slack.com/services/…"
                value={slackUrl}
                onChange={(e) => setSlackUrl(e.target.value)}
              />
              <p className={styles.hint}>
                Create a webhook at{' '}
                <a
                  href="https://api.slack.com/messaging/webhooks"
                  target="_blank"
                  rel="noopener noreferrer"
                  className={styles.link}
                >
                  api.slack.com/messaging/webhooks <ExternalLink size={10} />
                </a>
              </p>
            </div>

            {alertSaved && (
              <div className={styles.testOk}>
                <CheckCircle2 size={13} aria-hidden />
                Alert config saved successfully.
              </div>
            )}

            <div className={styles.actions}>
              <button type="submit" className={styles.saveBtn} disabled={savingAlert}>
                {savingAlert ? <Spinner /> : <Save size={14} aria-hidden />}
                {savingAlert ? 'Saving…' : 'Save alert config'}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  )
}
