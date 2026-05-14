import { Link, useParams } from 'react-router-dom'

import styles from './page-shell.module.css'

/** Stub until `ConstitutionEditor` (US3 / later tasks). */
export default function ConstitutionStub() {
  const { id } = useParams()

  return (
    <div className={styles.shell}>
      <h1 className={styles.title}>Constitution</h1>
      <p className={styles.lead}>
        Stub editor for project <code>{id ?? '—'}</code>. Markdown editor and save flow will be added later.
      </p>
      <nav className={styles.nav} aria-label="Constitution navigation">
        <Link to="/projects">All projects</Link>
        {id ? <Link to={`/projects/${id}`}>Workspace</Link> : null}
      </nav>
    </div>
  )
}
