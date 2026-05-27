import { api } from './api'
import type { ProjectMember } from '../types'

export interface InvitationResponse {
  invitation_id: string
  invite_url: string
  expires_at: string
}

export async function getMembers(projectId: string): Promise<ProjectMember[]> {
  const res = await api.get<ProjectMember[]>(`/api/v1/projects/${projectId}/members`)
  return res.data
}

export async function inviteMember(
  projectId: string,
  role: string,
  inviteeEmail?: string,
): Promise<InvitationResponse> {
  const res = await api.post<InvitationResponse>(
    `/api/v1/projects/${projectId}/members/invite`,
    { role, invitee_email: inviteeEmail ?? null },
  )
  return res.data
}

export async function acceptInvite(token: string): Promise<{ project_id: string; role: string }> {
  const res = await api.post<{ project_id: string; role: string }>(
    `/api/v1/invitations/${token}/accept`,
  )
  return res.data
}

export async function changeMemberRole(
  projectId: string,
  userId: string,
  role: string,
): Promise<void> {
  await api.patch(`/api/v1/projects/${projectId}/members/${userId}`, { role })
}

export async function removeMember(projectId: string, userId: string): Promise<void> {
  await api.delete(`/api/v1/projects/${projectId}/members/${userId}`)
}
