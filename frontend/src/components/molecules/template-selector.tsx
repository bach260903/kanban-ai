import { useEffect, useState } from 'react'

import { listTemplates, type TemplateResponse } from '../../services/template-api'

export type TemplateSelectorProps = {
  projectId: string
  onSelect: (title: string, description: string) => void
}

export function TemplateSelector({ projectId, onSelect }: TemplateSelectorProps) {
  const [globalTemplates, setGlobalTemplates] = useState<TemplateResponse[]>([])
  const [projectTemplates, setProjectTemplates] = useState<TemplateResponse[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedId, setSelectedId] = useState('')

  useEffect(() => {
    let cancelled = false
    void (async () => {
      setLoading(true)
      setSelectedId('')
      try {
        const [globalRows, projectRows] = await Promise.all([
          listTemplates('global'),
          listTemplates('project', projectId),
        ])
        if (!cancelled) {
          setGlobalTemplates(globalRows)
          setProjectTemplates(projectRows)
        }
      } catch {
        if (!cancelled) {
          setGlobalTemplates([])
          setProjectTemplates([])
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [projectId])

  const allTemplates = [...globalTemplates, ...projectTemplates]
  if (loading || allTemplates.length === 0) {
    return null
  }

  function handleChange(event: React.ChangeEvent<HTMLSelectElement>) {
    const id = event.target.value
    setSelectedId(id)
    if (!id) return
    const row = allTemplates.find((t) => t.id === id)
    if (row) {
      onSelect(row.title_template, row.description_template ?? '')
    }
  }

  return (
    <label className="mb-4 flex flex-col gap-1">
      <span className="font-mono text-[11px] font-semibold uppercase tracking-wider text-slate-500">
        Template
      </span>
      <select
        value={selectedId}
        onChange={handleChange}
        className="h-9 w-full rounded-lg border border-slate-200 bg-white px-3 font-sans text-sm text-slate-800 focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-200"
      >
        <option value="">— Chọn template —</option>
        {globalTemplates.length > 0 ? (
          <optgroup label="Global">
            {globalTemplates.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </optgroup>
        ) : null}
        {projectTemplates.length > 0 ? (
          <optgroup label="Project này">
            {projectTemplates.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </optgroup>
        ) : null}
      </select>
    </label>
  )
}
