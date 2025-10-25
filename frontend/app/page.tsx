'use client'

import { useAuth } from './providers'
import { useEffect, useState, Fragment } from 'react'
import { useRouter } from 'next/navigation'
import RootFolderDialog from '@/components/RootFolderDialog'
import { apiClient } from '@/lib/api-client'
import Image from 'next/image'
import Toggle from '@/components/Toggle'
import { Menu, Transition } from '@headlessui/react'

interface Project {
  id: string
  name: string
  enabled: boolean
  drive_folder_id?: string
  is_drive_folder?: boolean
}

interface RootFolder {
  id: string
  name: string
}

export default function Dashboard() {
  const { user, loading, signInWithGoogle, signOut } = useAuth()
  const router = useRouter()
  const [projects, setProjects] = useState<Project[]>([])
  const [loadingProjects, setLoadingProjects] = useState(true)
  const [rootFolder, setRootFolder] = useState<RootFolder | null>(null)
  const [lastSync, setLastSync] = useState<string | null>(null)
  const [showRootFolderDialog, setShowRootFolderDialog] = useState(false)
  const [syncing, setSyncing] = useState(false)

  useEffect(() => {
    if (user) {
      fetchProjects()
      fetchRootFolder()
    }
  }, [user])

  const fetchProjects = async () => {
    try {
      const data = await apiClient.getProjects() as Project[]
      setProjects(data || [])
    } catch (error) {
      console.error('Error fetching projects:', error)
    } finally {
      setLoadingProjects(false)
    }
  }

  const toggleProject = async (id: string) => {
    const project = projects.find(p => p.id === id)
    if (!project) return

    // Prevent disabling "Uncertain Bids" folder
    if (project.name === 'Uncertain Bids') {
      return
    }

    const newEnabled = !project.enabled

    // Optimistic update
    setProjects(prev => prev.map(p =>
      p.id === id ? { ...p, enabled: newEnabled } : p
    ))

    try {
      await apiClient.toggleProject(id, newEnabled)
    } catch (error) {
      console.error('Error updating project:', error)
      // Revert optimistic update on error
      setProjects(prev => prev.map(p =>
        p.id === id ? { ...p, enabled: !newEnabled } : p
      ))
    }
  }

  const fetchRootFolder = async () => {
    try {
      const data = await apiClient.getRootFolder() as { rootFolder: { id: string; name: string } | null; lastSync: string | null }
      setRootFolder(data.rootFolder)
      setLastSync(data.lastSync)
    } catch (error) {
      console.error('Error fetching root folder:', error)
    }
  }

  const handleSaveRootFolder = async (folderId: string, folderName: string) => {
    try {
      await apiClient.setRootFolder(folderId, folderName)
      setRootFolder({ id: folderId, name: folderName })
      // Auto-sync after setting root folder
      await handleSync()
    } catch (error) {
      console.error('Error saving root folder:', error)
      alert('Failed to save root folder configuration')
    }
  }

  const handleSync = async () => {
    if (!rootFolder) return

    setSyncing(true)
    try {
      const data = await apiClient.syncDriveFolders() as { added: number; removed: number }
      await fetchProjects()
      await fetchRootFolder()
      
      if (data.added > 0 || data.removed > 0) {
        alert(`Sync complete: ${data.added} projects added, ${data.removed} removed`)
      }
    } catch (error) {
      console.error('Error syncing folders:', error)
      alert('Failed to sync with Google Drive')
    } finally {
      setSyncing(false)
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-lg">Loading...</div>
      </div>
    )
  }

  if (!user) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="max-w-md w-full bg-white rounded-lg shadow-md p-6">
          <h1 className="text-2xl font-bold text-center mb-6">Bid Buddy</h1>
          <p className="text-gray-600 text-center mb-6">
            Sign in with Google to access your dashboard
          </p>
          <button
            onClick={signInWithGoogle}
            className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded-lg transition-colors"
          >
            Sign in with Google
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <h1 className="text-xl font-semibold text-black">Bid Buddy</h1>
            <div className="flex items-center space-x-4">
              {/* User Dropdown */}
              <Menu as="div" className="relative inline-block text-left">
                <Menu.Button className="flex items-center space-x-2">
                  {user.user_metadata?.avatar_url && (
                    <Image
                      src={user.user_metadata.avatar_url}
                      alt="Profile"
                      width={32}
                      height={32}
                      className="rounded-full"
                    />
                  )}
                  <span className="text-sm font-medium text-gray-700">{user.user_metadata?.full_name || user.email}</span>
                  <svg className="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </Menu.Button>

                <Transition
                  as={Fragment}
                  enter="transition ease-out duration-100"
                  enterFrom="transform opacity-0 scale-95"
                  enterTo="transform opacity-100 scale-100"
                  leave="transition ease-in duration-75"
                  leaveFrom="transform opacity-100 scale-100"
                  leaveTo="transform opacity-0 scale-95"
                >
                  <Menu.Items className="absolute right-0 z-10 mt-2 w-56 origin-top-right rounded-md bg-white shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none">
                    <div className="p-1">
                      <div className="px-3 py-2 border-b">
                        <p className="text-sm font-medium text-gray-900">{user.user_metadata?.full_name || 'User'}</p>
                        <p className="text-xs text-gray-500">{user.email}</p>
                        {user.app_metadata?.provider === 'google' && (
                          <span className="inline-flex items-center mt-2 text-xs px-2 py-0.5 bg-green-100 text-green-700 rounded-full">
                            <svg className="w-3 h-3 mr-1" fill="currentColor" viewBox="0 0 20 20">
                              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                            </svg>
                            Google Connected
                          </span>
                        )}
                      </div>
                      <Menu.Item>
                        {({ active }) => (
                          <button
                            onClick={signOut}
                            className={`${
                              active ? 'bg-gray-100' : ''
                            } flex w-full px-3 py-2 text-sm text-gray-700`}
                          >
                            Sign out
                          </button>
                        )}
                      </Menu.Item>
                    </div>
                  </Menu.Items>
                </Transition>
              </Menu>
            </div>
          </div>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <div className="px-4 py-6 sm:px-0">
          <div className="bg-white rounded-lg shadow">
            <div className="px-6 py-4 border-b border-gray-200">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-lg font-medium text-black">Projects</h2>
                </div>
                <div className="flex items-center space-x-3">
                  {/* Root Folder Info */}
                  <div className="text-right">
                    {rootFolder ? (
                      <>
                        <p className="text-sm font-medium text-gray-700">Root: {rootFolder.name}</p>
                        {lastSync && (
                          <p className="text-xs text-gray-500">
                            Last sync: {new Date(lastSync).toLocaleTimeString()}
                          </p>
                        )}
                      </>
                    ) : (
                      <p className="text-sm text-gray-500">No root folder configured</p>
                    )}
                  </div>
                  
                  {/* Action Buttons */}
                  <div className="flex space-x-2">
                    <button
                      onClick={() => setShowRootFolderDialog(true)}
                      className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
                    >
                      {rootFolder ? '📁 Change Folder' : '📁 Configure Folder'}
                    </button>
                    {rootFolder && (
                      <button
                        onClick={handleSync}
                        disabled={syncing}
                        className="px-3 py-1.5 text-sm bg-green-600 text-white rounded-md hover:bg-green-700 disabled:opacity-50 transition-colors"
                      >
                        {syncing ? '🔄 Syncing...' : '🔄 Sync'}
                      </button>
                    )}
                  </div>
                </div>
              </div>
            </div>
            
            <div className="overflow-hidden">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 tracking-wider">
                      Project Name
                    </th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 tracking-wider">
                      Enabled
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {loadingProjects ? (
                    <tr>
                      <td colSpan={2} className="px-6 py-4 text-center text-sm text-gray-500">
                        Loading projects...
                      </td>
                    </tr>
                  ) : projects.length === 0 ? (
                    <tr>
                      <td colSpan={2} className="px-6 py-4 text-center text-sm text-gray-500">
                        No projects found
                      </td>
                    </tr>
                  ) : (
                    projects.map((project) => (
                      <tr key={project.id} className="hover:bg-gray-50">
                        <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                          {project.enabled && project.name !== 'Uncertain Bids' ? (
                            <button
                              onClick={() => router.push(`/projects/${project.id}`)}
                              className="flex items-center space-x-2 hover:text-blue-600 transition-colors"
                            >
                              {project.is_drive_folder && (
                                <svg className="w-4 h-4 text-blue-500" fill="currentColor" viewBox="0 0 20 20">
                                  <path d="M2 6a2 2 0 012-2h5l2 2h5a2 2 0 012 2v6a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" />
                                </svg>
                              )}
                              <span>{project.name}</span>
                            </button>
                          ) : project.name === 'Uncertain Bids' ? (
                            <div className="flex items-center space-x-2">
                              {project.is_drive_folder && (
                                <svg className="w-4 h-4 text-blue-500" fill="currentColor" viewBox="0 0 20 20">
                                  <path d="M2 6a2 2 0 012-2h5l2 2h5a2 2 0 012 2v6a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" />
                                </svg>
                              )}
                              <span>{project.name}</span>
                            </div>
                          ) : (
                            <div className="flex items-center space-x-2">
                              {project.is_drive_folder && (
                                <svg className="w-4 h-4 text-gray-400" fill="currentColor" viewBox="0 0 20 20">
                                  <path d="M2 6a2 2 0 012-2h5l2 2h5a2 2 0 012 2v6a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" />
                                </svg>
                              )}
                              <span className="text-gray-500">{project.name}</span>
                            </div>
                          )}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="flex justify-end">
                            <Toggle
                              enabled={project.enabled}
                              onChange={() => toggleProject(project.id)}
                              locked={project.name === 'Uncertain Bids'}
                            />
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </main>

      {/* Root Folder Dialog */}
      <RootFolderDialog
        isOpen={showRootFolderDialog}
        onClose={() => setShowRootFolderDialog(false)}
        onSave={handleSaveRootFolder}
        currentRootFolder={rootFolder}
      />
    </div>
  )
}
