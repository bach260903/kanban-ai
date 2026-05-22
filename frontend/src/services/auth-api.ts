import api from './api'

export type DevTokenResponse = {
  access_token: string
  token_type: string
}

export async function fetchDevToken(): Promise<DevTokenResponse> {
  const { data } = await api.post<DevTokenResponse>('/api/v1/dev/token', {})
  return data
}
