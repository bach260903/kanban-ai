import { isAxiosError } from 'axios'
import {
  Bell,
  ChevronLeft,
  MoreHorizontal,
  Settings,
  Trash2,
} from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link, NavLink, useNavigate } from 'react-router-dom'

import { Badge } from '../atoms/badge'
import { BackendBadge } from '../atoms/backend-badge'
import { NotificationBadge } from '../atoms/notification-badge'
import { ConfirmDialog } from '../molecules/confirm-dialog'
import { NotificationPanel } from '../molecules/notification-panel'
import { useAuth } from '../../contexts/auth-context'
import { showErrorToast, showSuccessToast } from '../../lib/toast'
import { getMembers } from '../../services/member-api'
import { getNotifications } from '../../services/notification-api'
import { deleteProject } from '../../services/project-api'
import type { Project, ProjectMember } from '../../types'

import styles from './project-header.module.css'

export type WorkspaceTab = 'documents' | 'kanban' | 'memory' | 'audit' | 'dependencies'

type ProjectHeaderProps = {
  project: Project
  activeTab?: WorkspaceTab
  onTabChange?: (tab: WorkspaceTab) => void
  onOpenTask?: (taskId: string) => void
}

const TABS: { id: WorkspaceTab; label: string }[] = [
  { id: 'documents', label: 'Documents' },
  { id: 'kanban', label: 'Kanban' },
  { id: 'dependencies', label: 'Dependencies' },
  { id: 'memory', label: 'Memory' },
  { id: 'audit', label: 'Audit log' },
]

const MAX_AVATARS = 5

function memberInitials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  if (parts.length >= 2) {
    return `${parts[0][0] ?? ''}${parts[parts.length - 1][0] ?? ''}`.toUpperCase()
  }
  return (parts[0] ?? '?').slice(0, 2).toUpperCase()
}

/**
 * Curated palette of dark backgrounds. Every color was verified to clear
 * the WCAG AA 4.5:1 contrast bar against the white avatar foreground —
 * including yellow/lime hues that HSL(L ≈ 30%) would otherwise wash out.
 */
const AVATAR_PALETTE: ReadonlyArray<string> = [
  '#1e40af', // blue-800
  '#6b21a8', // purple-800
  '#9d174d', // pink-800
  '#9f1239', // rose-800
  '#991b1b', // red-800
  '#9a3412', // orange-800
  '#854d0e', // amber-800
  '#3f6212', // lime-800
  '#166534', // green-800
  '#115e59', // teal-800
  '#155e75', // cyan-800
  '#1e3a8a', // indigo-900
  '#312e81', // indigo-800
  '#7c2d12', // orange-900
  '#581c87', // purple-900
]

function avatarColor(name: string): string {
  const trimmed = name.trim()
  if (!trimmed) return AVATAR_PALETTE[0]
  let hash = 0
  for (let i = 0; i < trimmed.length; i += 1) {
    hash = (hash * 31 + trimmed.charCodeAt(i)) >>> 0
  }
  return AVATAR_PALETTE[hash % AVATAR_PALETTE.length]
}

export function ProjectHeader({ project, activeTab, onTabChange, onOpenTask }: ProjectHeaderProps) {
  const navigate = useNavigate()
  const { user } = useAuth()
  const showWorkspaceTabs = activeTab != null && onTabChange != null
  const [members, setMembers] = useState<ProjectMember[]>([])
  const [notifOpen, setNotifOpen] = useState(false)
  const [unreadCount, setUnreadCount] = useState(0)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)
  const notifRef = useRef<HTMLDivElement>(null)

  const currentMember = members.find((member) => member.user_id === user?.id)
  const canDeleteProject = currentMember?.role === 'owner'
  const canViewAnalytics =
    currentMember?.role === 'owner' || currentMember?.role === 'leader'

  useEffect(() => {
    let cancelled = false
    void (async () => {
      try {
        const rows = await getMembers(project.id)
        if (!cancelled) setMembers(rows)
      } catch {
        if (!cancelled) setMembers([])
      }
    })()
    return () => {
      cancelled = true
    }
  }, [project.id])

  useEffect(() => {
    if (notifOpen) return undefined
    let cancelled = false
    async function pollUnread() {
      try {
        const res = await getNotifications({ unread_only: true, limit: 1 })
        if (!cancelled) setUnreadCount(res.total_unread)
      } catch {
        /* ignore poll errors */
      }
    }
    void pollUnread()
    const id = window.setInterval(() => void pollUnread(), 30_000)
    return () => {
      cancelled = true
      window.clearInterval(id)
    }
  }, [notifOpen])

  useEffect(() => {
    if (!notifOpen) return undefined
    function onDocClick(e: MouseEvent) {
      if (!notifRef.current) return
      if (!notifRef.current.contains(e.target as Node)) setNotifOpen(false)
    }
    function onEsc(e: KeyboardEvent) {
      if (e.key === 'Escape') setNotifOpen(false)
    }
    document.addEventListener('mousedown', onDocClick)
    document.addEventListener('keydown', onEsc)
    return () => {
      document.removeEventListener('mousedown', onDocClick)
      document.removeEventListener('keydown', onEsc)
    }
  }, [notifOpen])

  useEffect(() => {
    if (!menuOpen) return undefined
    function onDocClick(e: MouseEvent) {
      if (!menuRef.current) return
      if (!menuRef.current.contains(e.target as Node)) setMenuOpen(false)
    }
    function onEsc(e: KeyboardEvent) {
      if (e.key === 'Escape') setMenuOpen(false)
    }
    document.addEventListener('mousedown', onDocClick)
    document.addEventListener('keydown', onEsc)
    return () => {
      document.removeEventListener('mousedown', onDocClick)
      document.removeEventListener('keydown', onEsc)
    }
  }, [menuOpen])

  const visibleMembers = members.slice(0, MAX_AVATARS)
  const overflowCount = Math.max(0, members.length - MAX_AVATARS)

  async function confirmDeleteProject() {
    try {
      setDeleting(true)
      await deleteProject(project.id)
      showSuccessToast('Project deleted')
      setDeleteOpen(false)
      navigate('/dashboard', { replace: true })
    } catch (err) {
      const detail = isAxiosError(err)
        ? (err.response?.data as { detail?: string })?.detail
        : null
      showErrorToast(detail ?? 'Failed to delete project')
    } finally {
      setDeleting(false)
    }
  }

  return (
    <header className={styles.header}>
      {/* Top row: breadcrumb · project name (H1) · bell · avatars · overflow */}
      <div className={styles.topRow}>
        <nav className={styles.breadcrumb} aria-label="Project navigation">
          <Link to="/dashboard" className={styles.breadcrumbBack}>
            <ChevronLeft size={16} aria-hidden="true" />
            <span>Dashboard</span>
          </Link>
          <span className={styles.breadcrumbSep} aria-hidden="true">
            /
          </span>
          <h1 className={styles.projectName} aria-current="page">
            {project.name}
          </h1>
        </nav>

        <div className={styles.topRight}>
          <div ref={notifRef} className={styles.notifWrap}>
            <button
              type="button"
              className={styles.iconButton}
              onClick={() => setNotifOpen((open) => !open)}
              aria-label={
                unreadCount > 0
                  ? `Notifications, ${unreadCount} unread`
                  : 'Notifications'
              }
              aria-expanded={notifOpen}
              aria-haspopup="dialog"
            >
              <Bell size={16} aria-hidden="true" />
              <NotificationBadge count={unreadCount} />
            </button>
            {notifOpen ? (
              <NotificationPanel
                projectId={project.id}
                onClose={() => setNotifOpen(false)}
                onUnreadChange={setUnreadCount}
                onTaskClick={(taskId) => {
                  if (onOpenTask) {
                    onOpenTask(taskId)
                  } else {
                    navigate(`/projects/${project.id}`)
                  }
                }}
              />
            ) : null}
          </div>

          <ul className={styles.avatars} aria-label="Project members">
            {visibleMembers.map((m) => (
              <li key={m.user_id}>
                <span
                  className={styles.avatar}
                  style={{ backgroundColor: avatarColor(m.display_name) }}
                  title={m.display_name}
                  aria-label={m.display_name}
                >
                  {memberInitials(m.display_name)}
                </span>
              </li>
            ))}
            {overflowCount > 0 ? (
              <li>
                <span className={styles.avatarOverflow} title={`${overflowCount} more members`}>
                  +{overflowCount}
                </span>
              </li>
            ) : null}
          </ul>

          <div ref={menuRef} className={styles.menuWrap}>
            <button
              type="button"
              className={styles.iconButton}
              aria-haspopup="menu"
              aria-expanded={menuOpen}
              aria-label="Project options"
              onClick={() => setMenuOpen((v) => !v)}
            >
              <MoreHorizontal size={16} aria-hidden="true" />
            </button>
            {menuOpen ? (
              <div className={styles.menu} role="menu">
                <button
                  type="button"
                  role="menuitem"
                  className={styles.menuItem}
                  onClick={() => {
                    setMenuOpen(false)
                    navigate(`/projects/${project.id}/settings`)
                  }}
                >
                  <Settings size={14} aria-hidden="true" />
                  Project settings
                </button>
                <div className={styles.menuMetaRow}>
                  <Badge
                    kind="document"
                    status="draft"
                    label={project.primary_language.toUpperCase()}
                    className={styles.langBadge}
                  />
                  <BackendBadge backend={project.coding_backend} />
                </div>
                {canDeleteProject ? (
                  <>
                    <div className={styles.menuSep} aria-hidden="true" />
                    <button
                      type="button"
                      role="menuitem"
                      className={`${styles.menuItem} ${styles.menuItemDanger}`}
                      onClick={() => {
                        setMenuOpen(false)
                        setDeleteOpen(true)
                      }}
                    >
                      <Trash2 size={14} aria-hidden="true" />
                      Delete project
                    </button>
                  </>
                ) : null}
              </div>
            ) : null}
          </div>
        </div>
      </div>

      {/* Bottom row: workspace tabs (scrollable on mobile) */}
      {showWorkspaceTabs ? (
        <nav className={styles.tabsRow} aria-label="Workspace sections">
          <div className={styles.tabs} role="tablist">
            {TABS.map((tab) => (
              <button
                key={tab.id}
                type="button"
                role="tab"
                className={activeTab === tab.id ? styles.tabActive : styles.tab}
                aria-selected={activeTab === tab.id}
                aria-current={activeTab === tab.id ? 'page' : undefined}
                onClick={() => onTabChange(tab.id)}
              >
                {tab.label}
              </button>
            ))}
            <NavLink
              to={`/projects/${project.id}/constitution`}
              role="tab"
              className={({ isActive }) =>
                isActive ? `${styles.tabActive} ${styles.tabLink}` : `${styles.tab} ${styles.tabLink}`
              }
              aria-current={undefined}
            >
              Constitution
            </NavLink>
            {canViewAnalytics ? (
              <NavLink
                to={`/projects/${project.id}/analytics`}
                role="tab"
                className={({ isActive }) =>
                  isActive ? `${styles.tabActive} ${styles.tabLink}` : `${styles.tab} ${styles.tabLink}`
                }
              >
                Analytics
              </NavLink>
            ) : null}
          </div>
        </nav>
      ) : null}

      {project.description ? <p className={styles.description}>{project.description}</p> : null}
      <ConfirmDialog
        open={deleteOpen}
        title="Delete project"
        message={`Are you sure you want to delete "${project.name}"?\n\nThe project will be archived and removed from your list. Only owners can perform this action.`}
        confirmLabel="Delete project"
        confirmVariant="danger"
        busy={deleting}
        onConfirm={() => void confirmDeleteProject()}
        onCancel={() => setDeleteOpen(false)}
      />
    </header>
  )
}
