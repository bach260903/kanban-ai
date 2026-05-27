import { isAxiosError } from 'axios'
import { useCallback, useEffect, useState } from 'react'

import { Button } from '../atoms/button'
import { RoleBadge } from '../atoms/role-badge'
import { Spinner } from '../atoms/spinner'
import { useAuth } from '../../contexts/auth-context'
import { showErrorToast, showSuccessToast } from '../../lib/toast'
import {
  changeMemberRole,
  getMembers,
  inviteMember,
  removeMember,
} from '../../services/member-api'
import type { ProjectMember, ProjectRole } from '../../types'

import styles from './project-members.module.css'

const INVITE_ROLES: ProjectRole[] = ['leader', 'developer', 'viewer']
const CHANGEABLE_ROLES: ProjectRole[] = ['leader', 'developer', 'viewer']

type ProjectMembersProps = {
  projectId: string
}

export function ProjectMembers({ projectId }: ProjectMembersProps) {
  const { user } = useAuth()
  const [members, setMembers] = useState<ProjectMember[]>([])
  const [loading, setLoading] = useState(true)
  const [inviteRole, setInviteRole] = useState<ProjectRole>('developer')
  const [inviteEmail, setInviteEmail] = useState('')
  const [inviteLink, setInviteLink] = useState<string | null>(null)
  const [inviting, setInviting] = useState(false)
  const [busyUserId, setBusyUserId] = useState<string | null>(null)
  const currentMember = members.find((member) => member.user_id === user?.id)
  const canInvite = currentMember?.role === 'owner'
  const canChangeRoles = currentMember?.role === 'owner' || currentMember?.role === 'leader'
  const canRemoveMembers = currentMember?.role === 'owner'

  const load = useCallback(async (showLoading = true) => {
    if (showLoading) setLoading(true)
    try {
      const rows = await getMembers(projectId)
      setMembers(rows)
    } catch (err) {
      showErrorToast(isAxiosError(err) ? loadError(err) : 'Không tải được danh sách thành viên')
    } finally {
      setLoading(false)
    }
  }, [projectId])

  useEffect(() => {
    void load()
  }, [load])

  async function handleInvite() {
    if (!canInvite) {
      showErrorToast('Chỉ owner mới có thể mời thành viên')
      return
    }
    setInviting(true)
    setInviteLink(null)
    try {
      const res = await inviteMember(
        projectId,
        inviteRole,
        inviteEmail.trim() || undefined,
      )
      setInviteLink(res.invite_url)
      showSuccessToast('Đã tạo link mời')
    } catch (err) {
      showErrorToast(isAxiosError(err) ? loadError(err) : 'Không tạo được link mời')
    } finally {
      setInviting(false)
    }
  }

  async function handleRoleChange(member: ProjectMember, role: ProjectRole) {
    if (role === member.role) return
    setBusyUserId(member.user_id)
    try {
      await changeMemberRole(projectId, member.user_id, role)
      showSuccessToast('Đã cập nhật vai trò')
      await load(false)
    } catch (err) {
      showErrorToast(isAxiosError(err) ? loadError(err) : 'Không cập nhật được vai trò')
    } finally {
      setBusyUserId(null)
    }
  }

  async function handleRemove(member: ProjectMember) {
    if (!window.confirm(`Xóa ${member.display_name} khỏi project?`)) return
    setBusyUserId(member.user_id)
    try {
      await removeMember(projectId, member.user_id)
      showSuccessToast('Đã xóa thành viên')
      await load(false)
    } catch (err) {
      showErrorToast(isAxiosError(err) ? loadError(err) : 'Không xóa được thành viên')
    } finally {
      setBusyUserId(null)
    }
  }

  async function copyInviteLink() {
    if (!inviteLink) return
    try {
      await navigator.clipboard.writeText(inviteLink)
      showSuccessToast('Đã sao chép link')
    } catch {
      showErrorToast('Không sao chép được link')
    }
  }

  if (loading) {
    return (
      <p className={styles.loading}>
        <Spinner aria-label="Loading members" />
        Đang tải thành viên…
      </p>
    )
  }

  return (
    <div className={styles.root}>
      <div className={styles.tableWrap}>
        {members.length === 0 ? (
          <p className={styles.empty}>Chưa có thành viên nào.</p>
        ) : (
          <table className={styles.table}>
            <thead>
              <tr>
                <th scope="col">Tên</th>
                <th scope="col">Email</th>
                <th scope="col">Vai trò</th>
                <th scope="col">Thao tác</th>
              </tr>
            </thead>
            <tbody>
              {members.map((member) => {
                const isSelf = user?.id === member.user_id
                const isOwner = member.role === 'owner'
                const roleDisabled =
                  !canChangeRoles || isSelf || isOwner || busyUserId === member.user_id
                const removeDisabled =
                  !canRemoveMembers || isSelf || isOwner || busyUserId === member.user_id
                return (
                  <tr key={member.user_id}>
                    <td>{member.display_name}</td>
                    <td>{member.email}</td>
                    <td>
                      <RoleBadge role={member.role} />
                    </td>
                    <td>
                      <div className={styles.actions}>
                        <select
                          className={styles.roleSelect}
                          value={member.role}
                          disabled={roleDisabled}
                          aria-label={`Đổi vai trò ${member.display_name}`}
                          onChange={(e) =>
                            void handleRoleChange(member, e.target.value as ProjectRole)
                          }
                        >
                          {CHANGEABLE_ROLES.map((r) => (
                            <option key={r} value={r}>
                              {r}
                            </option>
                          ))}
                          {isOwner ? (
                            <option value="owner">owner</option>
                          ) : null}
                        </select>
                        <Button
                          type="button"
                          variant="danger"
                          disabled={removeDisabled}
                          onClick={() => void handleRemove(member)}
                        >
                          Xóa
                        </Button>
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>

      <section className={styles.invite} aria-labelledby="invite-members-heading">
        <h3 id="invite-members-heading" className={styles.inviteTitle}>
          Mời thành viên
        </h3>
        <div className={styles.inviteForm}>
          <div className={styles.field}>
            <label htmlFor="invite-email">Email (tùy chọn)</label>
            <input
              id="invite-email"
              type="email"
              value={inviteEmail}
              onChange={(e) => setInviteEmail(e.target.value)}
              placeholder="để trống = link công khai"
              disabled={inviting || !canInvite}
            />
          </div>
          <div className={styles.field}>
            <label htmlFor="invite-role">Vai trò</label>
            <select
              id="invite-role"
              value={inviteRole}
              onChange={(e) => setInviteRole(e.target.value as ProjectRole)}
              disabled={inviting || !canInvite}
            >
              {INVITE_ROLES.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </select>
          </div>
          <Button
            type="button"
            variant="primary"
            disabled={inviting || !canInvite}
            onClick={() => void handleInvite()}
          >
            {inviting ? 'Đang tạo…' : 'Tạo link'}
          </Button>
        </div>
        {!canInvite ? (
          <p className={styles.inviteHint}>Chỉ owner mới có thể tạo link mời.</p>
        ) : null}
        {inviteLink ? (
          <div className={styles.inviteLink}>
            <code>{inviteLink}</code>
            <Button type="button" variant="secondary" onClick={() => void copyInviteLink()}>
              Sao chép
            </Button>
          </div>
        ) : null}
      </section>
    </div>
  )
}

function loadError(err: { response?: { data?: { detail?: unknown }; status?: number } }): string {
  const detail = err.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (err.response?.status === 403) return 'Bạn không có quyền thực hiện thao tác này'
  return 'Yêu cầu thất bại'
}
