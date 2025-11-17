import { createClient } from '@/lib/supabase/client'
import type { Session } from '@supabase/supabase-js'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const SESSION_EXPIRY_BUFFER_MS = 60_000 // Refresh 1 minute before Supabase JWT expiry

class APIClient {
  private supabase = createClient()
  private refreshPromise: Promise<Session | null> | null = null

  private isSessionExpiring(session: Session | null): boolean {
    if (!session?.expires_at) return false
    const expiryMs = session.expires_at * 1000
    return expiryMs - Date.now() <= SESSION_EXPIRY_BUFFER_MS
  }

  private async refreshSupabaseSession(): Promise<Session | null> {
    if (!this.refreshPromise) {
      this.refreshPromise = (async () => {
        const { data, error } = await this.supabase.auth.refreshSession()
        if (error) {
          throw new Error(error.message || 'Failed to refresh Supabase session')
        }
        return data.session ?? null
      })()
    }

    try {
      return await this.refreshPromise
    } finally {
      this.refreshPromise = null
    }
  }

  private async getSession(forceRefresh = false): Promise<Session | null> {
    if (forceRefresh) {
      return this.refreshSupabaseSession()
    }

    const { data } = await this.supabase.auth.getSession()
    let session = data.session ?? null

    if (!session || this.isSessionExpiring(session)) {
      session = await this.refreshSupabaseSession()
    }

    return session
  }

  private async getAuthHeaders(includeGoogleToken = false, forceRefresh = false): Promise<Record<string, string>> {
    let session = await this.getSession(forceRefresh)

    if (!session?.access_token) {
      // Final attempt: force refresh before failing
      session = await this.getSession(true)
    }

    if (!session?.access_token) {
      throw new Error('No access token available')
    }

    const headers: Record<string, string> = {
      'Authorization': `Bearer ${session.access_token}`,
      'Content-Type': 'application/json',
    }

    // Include Google OAuth tokens if requested and available
    if (includeGoogleToken && session.provider_token) {
      headers['x-google-token'] = session.provider_token
      if (session.provider_refresh_token) {
        headers['x-google-refresh-token'] = session.provider_refresh_token
      }
    }

    return headers
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit & { includeGoogleToken?: boolean } = {},
    attempt = 1
  ): Promise<T> {
    const { includeGoogleToken, ...fetchOptions } = options
    const headers = await this.getAuthHeaders(includeGoogleToken, attempt > 1)

    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...fetchOptions,
      headers: {
        ...headers,
        ...fetchOptions.headers,
      },
    })

    if (!response.ok) {
      if (response.status === 401 && includeGoogleToken && attempt === 1) {
        // Force refresh Supabase + provider tokens and retry once
        await this.getAuthHeaders(includeGoogleToken, true)
        return this.request<T>(endpoint, options, attempt + 1)
      }

      const error = await response.json().catch(() => ({ detail: 'Unknown error' }))
      throw new Error(error.detail || `HTTP ${response.status}`)
    }

    return response.json()
  }

  // Project endpoints
  async getProjects() {
    return this.request('/api/projects')
  }

  async createProject(projectData: Record<string, unknown>) {
    return this.request('/api/projects', {
      method: 'POST',
      body: JSON.stringify(projectData),
    })
  }

  async updateProject(projectId: string, updateData: Record<string, unknown>) {
    return this.request(`/api/projects/${projectId}`, {
      method: 'PATCH',
      body: JSON.stringify(updateData),
    })
  }

  async toggleProject(projectId: string, enabled: boolean) {
    return this.request(`/api/projects/${projectId}/toggle`, {
      method: 'PATCH',
      body: JSON.stringify({ enabled }),
    })
  }

  async deleteProject(projectId: string) {
    return this.request(`/api/projects/${projectId}`, {
      method: 'DELETE',
    })
  }

  // Drive endpoints
  async getDriveFolders(parentId?: string, pageToken?: string) {
    const params = new URLSearchParams()
    if (parentId) params.append('parent', parentId)
    if (pageToken) params.append('pageToken', pageToken)
    
    const query = params.toString() ? `?${params.toString()}` : ''
    return this.request(`/api/drive/folders${query}`, {
      includeGoogleToken: true
    })
  }

  async searchDriveFolders(query: string) {
    return this.request(`/api/drive/folders/search?q=${encodeURIComponent(query)}`, {
      includeGoogleToken: true
    })
  }

  async getRootFolder() {
    return this.request('/api/drive/root-folder')
  }

  async setRootFolder(folderId: string, folderName: string) {
    return this.request('/api/drive/root-folder', {
      method: 'POST',
      body: JSON.stringify({ folderId, folderName }),
    })
  }

  async syncDriveFolders() {
    return this.request('/api/drive/sync', {
      method: 'POST',
      includeGoogleToken: true
    })
  }

  // Trade endpoints
  async getTrades() {
    return this.request('/api/trades')
  }

  async createTrade(trade: { name: string; display_order?: number }) {
    return this.request('/api/trades', {
      method: 'POST',
      body: JSON.stringify(trade),
    })
  }

  async updateTrade(tradeId: string, trade: { name: string; display_order?: number; is_active?: boolean }) {
    return this.request(`/api/trades/${tradeId}`, {
      method: 'PUT',
      body: JSON.stringify(trade),
    })
  }

  async deleteTrade(tradeId: string) {
    return this.request(`/api/trades/${tradeId}`, {
      method: 'DELETE',
    })
  }

  // Project trades endpoints
  async getProjectTrades(projectId: string) {
    return this.request(`/api/projects/${projectId}/trades`)
  }

  async addProjectTrade(projectId: string, tradeId: string, customName?: string) {
    return this.request(`/api/projects/${projectId}/trades`, {
      method: 'POST',
      body: JSON.stringify({ trade_id: tradeId, custom_name: customName }),
    })
  }

  async updateProjectTrade(projectId: string, projectTradeId: string, tradeId: string, customName?: string, isActive?: boolean) {
    return this.request(`/api/projects/${projectId}/trades/${projectTradeId}`, {
      method: 'PUT',
      body: JSON.stringify({ trade_id: tradeId, custom_name: customName, is_active: isActive }),
    })
  }

  async removeProjectTrade(projectId: string, projectTradeId: string) {
    return this.request(`/api/projects/${projectId}/trades/${projectTradeId}`, {
      method: 'DELETE',
    })
  }

  async getProjectStats(projectId: string) {
    return this.request(`/api/projects/${projectId}/stats`)
  }

  async syncProjectDrive(projectId: string) {
    return this.request(`/api/projects/${projectId}/sync-drive`, {
      method: 'POST',
      includeGoogleToken: true
    })
  }

  async syncBuildingConnected(projectId: string) {
    return this.request(`/api/projects/${projectId}/sync-buildingconnected`, {
      method: 'POST'
    })
  }

  // Auth endpoints
  async getCurrentUser() {
    return this.request('/api/auth/user')
  }

  async signOut() {
    return this.request('/api/auth/signout', {
      method: 'POST',
    })
  }
}

export const apiClient = new APIClient()