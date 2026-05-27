import { useEffect, useRef, useState } from 'react'

import { Avatar } from '../atoms/avatar'
import type { ProjectMember } from '../../types'

export type AssignMemberProps = {
  members: ProjectMember[]
  currentAssigneeId: string | null
  onAssign: (userId: string | null) => void
}

export function AssignMember({ members, currentAssigneeId, onAssign }: AssignMemberProps) {
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)

  const assignee = members.find((m) => m.user_id === currentAssigneeId) ?? null

  useEffect(() => {
    if (!open) return

    function handlePointerDown(event: MouseEvent) {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false)
      }
    }

    document.addEventListener('mousedown', handlePointerDown)
    return () => document.removeEventListener('mousedown', handlePointerDown)
  }, [open])

  function pick(userId: string | null) {
    onAssign(userId)
    setOpen(false)
  }

  return (
    <div
      ref={rootRef}
      className="relative inline-flex"
      data-no-dnd="true"
      onPointerDown={(e) => e.stopPropagation()}
    >
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation()
          setOpen((v) => !v)
        }}
        className="inline-flex cursor-pointer items-center gap-1.5 rounded-md border border-slate-200 bg-white px-2 py-1 text-left text-[11px] font-medium text-slate-700 transition-colors hover:border-brand-300 hover:bg-brand-50/40 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-300"
        aria-expanded={open}
        aria-haspopup="listbox"
      >
        {assignee ? (
          <>
            <Avatar name={assignee.display_name} size="sm" />
            <span className="max-w-[96px] truncate">{assignee.display_name}</span>
          </>
        ) : (
          <span className="text-slate-500">Assign…</span>
        )}
      </button>

      {open ? (
        <ul
          role="listbox"
          className="absolute left-0 top-full z-50 mt-1 min-w-[180px] overflow-hidden rounded-lg border border-slate-200 bg-white py-1 shadow-elev-2"
        >
          {members.map((member) => (
            <li key={member.user_id} role="option">
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation()
                  pick(member.user_id)
                }}
                className="flex w-full cursor-pointer items-center gap-2 px-3 py-2 text-left text-xs text-slate-700 hover:bg-slate-50 focus:outline-none focus-visible:bg-slate-50"
              >
                <Avatar name={member.display_name} size="sm" />
                <span className="truncate">{member.display_name}</span>
              </button>
            </li>
          ))}
          <li role="option">
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation()
                pick(null)
              }}
              className="w-full cursor-pointer px-3 py-2 text-left text-xs text-slate-500 hover:bg-slate-50 focus:outline-none focus-visible:bg-slate-50"
            >
              Unassign
            </button>
          </li>
        </ul>
      ) : null}
    </div>
  )
}
