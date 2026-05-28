import { FolderKanban, LayoutDashboard, LogOut, Zap } from 'lucide-react'
import { Link, NavLink, useNavigate } from 'react-router-dom'

import { useAuth } from '../../contexts/auth-context'
import { Avatar } from '../atoms/avatar'
import { NotificationBell } from '../molecules/notification-bell'

import styles from './app-shell.module.css'

export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  function handleLogout() {
    logout()
    navigate('/login', { replace: true })
  }

  return (
    <div className={styles.shell}>
      <nav className={styles.topNav} aria-label="Main navigation">
        <div className={styles.navLeft}>
          <Link to="/dashboard" className={styles.brand} aria-label="NeoKanban home">
            <span className={styles.brandMark} aria-hidden="true">
              <Zap size={16} strokeWidth={2.5} />
            </span>
            <span className={styles.brandWord}>
              Neo<span>Kanban</span>
            </span>
          </Link>

          <NavLink
            to="/dashboard"
            className={({ isActive }) =>
              isActive ? `${styles.navLink} ${styles.navLinkActive}` : styles.navLink
            }
          >
            <LayoutDashboard size={15} aria-hidden="true" />
            <span>Dashboard</span>
          </NavLink>

          <NavLink
            to="/projects"
            className={({ isActive }) =>
              isActive ? `${styles.navLink} ${styles.navLinkActive}` : styles.navLink
            }
          >
            <FolderKanban size={15} aria-hidden="true" />
            <span>Projects</span>
          </NavLink>
        </div>

        <div className={styles.navRight}>
          <NotificationBell />

          {user ? (
            <div className={styles.userChip} aria-label={`Signed in as ${user.display_name}`}>
              <Avatar name={user.display_name} size="sm" />
              <span className={styles.displayName}>{user.display_name}</span>
            </div>
          ) : null}

          <button
            type="button"
            className={styles.logoutBtn}
            onClick={handleLogout}
            aria-label="Sign out"
          >
            <LogOut size={15} aria-hidden="true" />
            <span className={styles.logoutLabel}>Sign out</span>
          </button>
        </div>
      </nav>

      <div className={styles.content}>{children}</div>
    </div>
  )
}
