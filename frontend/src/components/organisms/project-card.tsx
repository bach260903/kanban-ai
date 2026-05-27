import { Clock, Code2, LayoutList, Sparkles, Users } from 'lucide-react'
import { Link } from 'react-router-dom'

import type { CodingBackend, ProjectListItem } from '../../types'
import { relativeTime } from '../../utils/relative-time'

import styles from './project-card.module.css'

const BACKEND_LABEL: Record<CodingBackend, string> = {
  groq: 'Groq',
  claude_code: 'Claude',
  openai: 'OpenAI',
  gemini: 'Gemini',
}

export type ProjectCardProps = {
  project: ProjectListItem
}

export function ProjectCard({ project }: ProjectCardProps) {
  const titleId = `project-${project.id}-title`
  const description = project.description?.trim() || ''
  const hasDescription = description.length > 0
  const isActive = project.status === 'active'

  return (
    <article
      role="article"
      aria-labelledby={titleId}
      className={styles.card}
    >
      <Link
        to={`/projects/${project.id}`}
        className={styles.cardLink}
        aria-label={`Open project ${project.name}`}
      />
      <div className={styles.header}>
        <span id={titleId} className={styles.title}>
          {project.name}
        </span>
        <span
          className={`${styles.statusBadge} ${isActive ? styles.statusActive : styles.statusArchived}`}
        >
          {project.status}
        </span>
      </div>

      <p
        className={`${styles.description} ${hasDescription ? '' : styles.descriptionEmpty}`}
      >
        {hasDescription ? description : 'No description'}
      </p>

      <div className={styles.badges}>
        <span className={`${styles.badge} ${styles.langBadge}`}>
          <Code2 aria-hidden="true" />
          {project.primary_language}
        </span>
        <span className={`${styles.badge} ${styles.backendBadge}`}>
          <Sparkles aria-hidden="true" />
          {BACKEND_LABEL[project.coding_backend]}
        </span>
      </div>

      <div className={styles.footer}>
        {typeof project.member_count === 'number' ? (
          <span className={styles.footerItem}>
            <Users aria-hidden="true" />
            {project.member_count} {project.member_count === 1 ? 'member' : 'members'}
          </span>
        ) : null}
        {typeof project.task_count === 'number' ? (
          <span className={styles.footerItem}>
            <LayoutList aria-hidden="true" />
            {project.task_count} {project.task_count === 1 ? 'task' : 'tasks'}
          </span>
        ) : null}
        <span className={`${styles.footerItem} ${styles.footerTime}`}>
          <Clock aria-hidden="true" />
          <time dateTime={project.updated_at}>{relativeTime(project.updated_at)}</time>
        </span>
      </div>
    </article>
  )
}
