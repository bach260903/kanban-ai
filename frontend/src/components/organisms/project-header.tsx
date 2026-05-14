import { NavLink } from 'react-router-dom'

import type { Project } from '../../types'

import styles from './project-header.module.css'

type ProjectHeaderProps = {
  project: Project
}

function tabClassName({ isActive }: { isActive: boolean }): string {
  return isActive ? `${styles.tab} ${styles.tabActive}` : styles.tab
}

export function ProjectHeader({ project }: ProjectHeaderProps) {
  return (
    <header className={styles.header}>
      <div className={styles.titleRow}>
        <h1 className={styles.title}>{project.name}</h1>
        <span className={styles.lang}>{project.primary_language}</span>
      </div>
      {project.description ? <p className={styles.description}>{project.description}</p> : null}
      <nav className={styles.tabs} aria-label="Workspace tabs">
        <NavLink className={tabClassName} to={`/projects/${project.id}`} end>
          Kanban
        </NavLink>
        <NavLink className={tabClassName} to={`/projects/${project.id}/documents`}>
          Documents
        </NavLink>
        <NavLink className={tabClassName} to={`/projects/${project.id}/constitution`}>
          Constitution
        </NavLink>
      </nav>
    </header>
  )
}
