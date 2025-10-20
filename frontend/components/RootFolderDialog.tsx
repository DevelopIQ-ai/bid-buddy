'use client'

import { useState, useEffect } from 'react'
import { apiClient } from '@/lib/api-client'

interface DriveFolder {
  id: string
  name: string
  path?: string
}

interface RootFolderDialogProps {
  isOpen: boolean
  onClose: () => void
  onSave: (folderId: string, folderName: string) => void
  currentRootFolder?: { id: string; name: string } | null
}

export default function RootFolderDialog({ 
  isOpen, 
  onClose, 
  onSave, 
  currentRootFolder 
}: RootFolderDialogProps) {
  const [folders, setFolders] = useState<DriveFolder[]>([])
  const [loading, setLoading] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedFolder, setSelectedFolder] = useState<DriveFolder | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (isOpen) {
      if (currentRootFolder) {
        setSelectedFolder(currentRootFolder)
      }
      fetchRootFolders()
    }
  }, [isOpen, currentRootFolder])

  const fetchRootFolders = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await apiClient.getDriveFolders()
      setFolders(data.folders || [])
    } catch (error) {
      setError('Failed to load Drive folders. Please check your connection.')
      console.error('Error fetching folders:', error)
    } finally {
      setLoading(false)
    }
  }

  const searchFolders = async () => {
    if (!searchQuery.trim()) {
      fetchRootFolders()
      return
    }

    setLoading(true)
    setError(null)
    try {
      const data = await apiClient.searchDriveFolders(searchQuery)
      setFolders(data.folders || [])
    } catch (error) {
      setError('Failed to search folders.')
      console.error('Error searching folders:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleSave = async () => {
    if (!selectedFolder) return

    try {
      onSave(selectedFolder.id, selectedFolder.name)
      onClose()
    } catch (error) {
      setError('Failed to save root folder configuration.')
    }
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full mx-4 max-h-[90vh] overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">
            Select Root Directory
          </h2>
          <p className="text-sm text-gray-600 mt-1">
            Choose a Google Drive folder to use as the root directory for your projects.
          </p>
        </div>

        <div className="p-6">
          {/* Search */}
          <div className="mb-4">
            <div className="flex gap-2">
              <input
                type="text"
                placeholder="Search for folders..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && searchFolders()}
                className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <button
                onClick={searchFolders}
                disabled={loading}
                className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
              >
                Search
              </button>
            </div>
          </div>

          {/* Current Selection */}
          {selectedFolder && (
            <div className="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-md">
              <p className="text-sm font-medium text-blue-900">Selected:</p>
              <p className="text-sm text-blue-700">{selectedFolder.name}</p>
            </div>
          )}

          {/* Error Message */}
          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md">
              <p className="text-sm text-red-700">{error}</p>
            </div>
          )}

          {/* Folders List */}
          <div className="border border-gray-200 rounded-md max-h-96 overflow-y-auto">
            {loading ? (
              <div className="p-4 text-center text-gray-500">
                Loading folders...
              </div>
            ) : folders.length === 0 ? (
              <div className="p-4 text-center text-gray-500">
                No folders found. Try searching for a specific folder name.
              </div>
            ) : (
              <div className="divide-y divide-gray-200">
                {folders.map((folder) => (
                  <div
                    key={folder.id}
                    onClick={() => setSelectedFolder(folder)}
                    className={`p-3 cursor-pointer hover:bg-gray-50 transition-colors ${
                      selectedFolder?.id === folder.id ? 'bg-blue-50 border-l-4 border-blue-500' : ''
                    }`}
                  >
                    <div className="flex items-center">
                      <svg className="w-5 h-5 text-yellow-500 mr-3" fill="currentColor" viewBox="0 0 20 20">
                        <path d="M2 6a2 2 0 012-2h5l2 2h5a2 2 0 012 2v6a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" />
                      </svg>
                      <span className="text-sm font-medium text-gray-900">{folder.name}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Actions */}
        <div className="px-6 py-4 border-t border-gray-200 flex justify-end space-x-3">
          <button
            onClick={onClose}
            className="px-4 py-2 text-gray-700 border border-gray-300 rounded-md hover:bg-gray-50"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={!selectedFolder}
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Save
          </button>
        </div>
      </div>
    </div>
  )
}