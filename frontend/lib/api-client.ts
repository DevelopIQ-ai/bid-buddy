import { createClient } from '@/lib/supabase/client'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

class APIClient {
  private getAuthHeaders = async (includeGoogleToken = false) => {
    const supabase = createClient()
    const { data: { session } } = await supabase.auth.getSession()

    if (!session?.access_token) {
      throw new Error('No access token available')
    }

    const headers: any = {
      'Authorization': `Bearer ${session.access_token}`,
      'Content-Type': 'application/json',
    }

    // Include Google tokens if requested and available
    if (includeGoogleToken && session.provider_token) {
      headers['x-google-token'] = session.provider_token

      // Also include refresh token if available (required for auto-refresh capability)
      if (session.provider_refresh_token) {
        headers['x-google-refresh-token'] = session.provider_refresh_token
      }
    }

    return headers
  }

  private async request<T>(endpoint: string, options: RequestInit & { includeGoogleToken?: boolean } = {}): Promise<T> {
    const { includeGoogleToken, ...fetchOptions } = options
    const headers = await this.getAuthHeaders(includeGoogleToken)
    
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...fetchOptions,
      headers: {
        ...headers,
        ...fetchOptions.headers,
      },
    })

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Unknown error' }))
      throw new Error(error.detail || `HTTP ${response.status}`)
    }

    return response.json()
  }

  // Project endpoints
  async getProjects() {
    return this.request('/api/projects/')
  }

  async createProject(projectData: any) {
    return this.request('/api/projects/', {
      method: 'POST',
      body: JSON.stringify(projectData),
    })
  }

  async updateProject(projectId: string, updateData: any) {
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