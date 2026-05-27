import type { TaskColumns } from '../store/task-store'

/** Single-user projects use per-project WIP; multi-user uses per-developer WIP (spec 003 / T056). */
export function isMultiUserWipMode(memberCount: number): boolean {
  return memberCount > 0
}

export function isUserWipFull(
  columns: TaskColumns,
  userId: string | undefined,
  multiUser: boolean,
): boolean {
  if (multiUser) {
    if (!userId) return false
    return columns.in_progress.some((t) => t.assigned_to === userId)
  }
  return columns.in_progress.length >= 1
}
