import type { ProjectRole } from '../../types'

const ROLE_STYLES: Record<ProjectRole, string> = {
  owner: 'bg-purple-100 text-purple-700',
  leader: 'bg-blue-100 text-blue-700',
  developer: 'bg-green-100 text-green-700',
  viewer: 'bg-gray-100 text-gray-500',
}

export function RoleBadge({ role }: { role: ProjectRole }) {
  return (
    <span
      className={`inline-block text-xs font-medium px-2 py-0.5 rounded-full ${ROLE_STYLES[role]}`}
    >
      {role}
    </span>
  )
}
