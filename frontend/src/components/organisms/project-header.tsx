import { Link, NavLink } from 'react-router-dom'

import { Badge } from '../atoms/badge'

import type { Project } from '../../types'

import styles from './project-header.module.css'

export type WorkspaceTab = 'documents' | 'kanban' | 'memory' | 'audit'

type ProjectHeaderProps = {
  project: Project
  activeTab?: WorkspaceTab
  onTabChange?: (tab: WorkspaceTab) => void
}

const TABS: { id: WorkspaceTab; label: string }[] = [
  { id: 'documents', label: 'Documents' },
  { id: 'kanban', label: 'Kanban' },
  { id: 'memory', label: 'Memory' },
  { id: 'audit', label: 'Audit log' },
]

export function ProjectHeader({ project, activeTab, onTabChange }: ProjectHeaderProps) {
  const showWorkspaceTabs = activeTab != null && onTabChange != null

  return (
    <header className={styles.header}>
      <div className={styles.bar}>
        <div className={styles.left}>
          <Link to="/projects" className={styles.projectLink}>
            {project.name}
          </Link>
          <Badge
            kind="document"
            status="draft"
            label={project.primary_language.toUpperCase()}
            className={styles.langBadge}
          />
        </div>
        <div className={styles.right}>
          {showWorkspaceTabs ? (
            <nav className={styles.tabs} role="tablist" aria-label="Workspace tabs">
              {TABS.map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  role="tab"
                  className={activeTab === tab.id ? styles.tabActive : styles.tab}
                  aria-selected={activeTab === tab.id}
                  onClick={() => onTabChange(tab.id)}
                >
                  {tab.label}
                </button>
              ))}
            </nav>
          ) : null}
          <NavLink
            to={`/projects/${project.id}/constitution`}
            className={({ isActive }) =>
              isActive ? `${styles.constitution} ${styles.constitutionActive}` : styles.constitution
            }
          >
            Constitution
          </NavLink>
        </div>
      </div>
      {project.description ? <p className={styles.description}>{project.description}</p> : null}
    </header>
  )
}
