import { google } from 'googleapis'

export interface DriveFolder {
  id: string
  name: string
  modifiedTime?: string
  parents?: string[]
}

export class GoogleDriveAPI {
  private drive
  
  constructor(accessToken: string) {
    const auth = new google.auth.OAuth2()
    auth.setCredentials({ access_token: accessToken })
    
    this.drive = google.drive({ version: 'v3', auth })
  }

  async listFolders(parentFolderId?: string, pageToken?: string): Promise<{
    folders: DriveFolder[]
    nextPageToken?: string
  }> {
    try {
      const query = parentFolderId 
        ? `'${parentFolderId}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false`
        : `mimeType='application/vnd.google-apps.folder' and trashed=false`

      const response = await this.drive.files.list({
        q: query,
        fields: 'nextPageToken, files(id, name, modifiedTime, parents)',
        pageSize: 100,
        pageToken,
        orderBy: 'name'
      })

      const folders = response.data.files?.map(file => ({
        id: file.id!,
        name: file.name!,
        modifiedTime: file.modifiedTime || undefined,
        parents: file.parents || undefined
      })) || []

      return {
        folders,
        nextPageToken: response.data.nextPageToken || undefined
      }
    } catch (error) {
      console.error('Error listing folders:', error)
      throw new Error('Failed to list Drive folders')
    }
  }

  async getFolderById(folderId: string): Promise<DriveFolder | null> {
    try {
      const response = await this.drive.files.get({
        fileId: folderId,
        fields: 'id, name, modifiedTime, parents'
      })

      const file = response.data
      if (!file.id || !file.name) return null

      return {
        id: file.id,
        name: file.name,
        modifiedTime: file.modifiedTime || undefined,
        parents: file.parents || undefined
      }
    } catch (error) {
      console.error('Error getting folder:', error)
      return null
    }
  }

  async searchFolders(query: string): Promise<DriveFolder[]> {
    try {
      const searchQuery = `name contains '${query}' and mimeType='application/vnd.google-apps.folder' and trashed=false`
      
      const response = await this.drive.files.list({
        q: searchQuery,
        fields: 'files(id, name, modifiedTime, parents)',
        pageSize: 50,
        orderBy: 'name'
      })

      return response.data.files?.map(file => ({
        id: file.id!,
        name: file.name!,
        modifiedTime: file.modifiedTime || undefined,
        parents: file.parents || undefined
      })) || []
    } catch (error) {
      console.error('Error searching folders:', error)
      throw new Error('Failed to search Drive folders')
    }
  }

  async getSubfolders(parentFolderId: string): Promise<DriveFolder[]> {
    try {
      const result = await this.listFolders(parentFolderId)
      return result.folders
    } catch (error) {
      console.error('Error getting subfolders:', error)
      throw new Error('Failed to get subfolders')
    }
  }
}