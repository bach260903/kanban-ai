import { Link, useParams } from 'react-router-dom'

import styles from './page-shell.module.css'

/** Stub workspace until Kanban / documents UI (later tasks). */
export default function ProjectWorkspace() {
  const { id } = useParams()

  return (
    <div className={styles.shell}>
      <h1 className={styles.title}>Project workspace</h1>
      <p className={styles.lead}>
        Stub view for project <code>{id ?? '—'}</code>. Kanban board and documents will load here.
      </p>
      <nav className={styles.nav} aria-label="Project navigation">
        <Link to="/projects">All projects</Link>
        {id ? <Link to={`/projects/${id}/constitution`}>Constitution</Link> : null}
      </nav>
    </div>
  )
}
