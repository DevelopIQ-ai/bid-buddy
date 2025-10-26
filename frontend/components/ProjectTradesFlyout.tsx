'use client'

import { Fragment, useState, useEffect } from 'react'
import { Dialog, Transition } from '@headlessui/react'
import { apiClient } from '@/lib/api-client'

interface UserTrade {
  id: string
  name: string
  is_active: boolean
}

interface ProjectTrade {
  id: string
  trade_id: string
  custom_name?: string
  is_active: boolean
  trades: UserTrade
}

interface ProjectTradesFlyoutProps {
  isOpen: boolean
  onClose: () => void
  projectId: string
}

export default function ProjectTradesFlyout({ isOpen, onClose, projectId }: ProjectTradesFlyoutProps) {
  const [projectTrades, setProjectTrades] = useState<ProjectTrade[]>([])
  const [allTrades, setAllTrades] = useState<UserTrade[]>([])
  const [loading, setLoading] = useState(true)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editingName, setEditingName] = useState('')
  const [newTradeId, setNewTradeId] = useState('')
  const [newTradeName, setNewTradeName] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (isOpen) {
      fetchData()
    }
  }, [isOpen, projectId])

  const fetchData = async () => {
    try {
      setLoading(true)
      const [trades, projectTradesData] = await Promise.all([
        apiClient.getTrades() as Promise<UserTrade[]>,
        apiClient.getProjectTrades(projectId) as Promise<ProjectTrade[]>
      ])
      setAllTrades(trades)
      setProjectTrades(projectTradesData)
    } catch (error) {
      console.error('Error fetching data:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleEdit = (projectTrade: ProjectTrade) => {
    setEditingId(projectTrade.id)
    setEditingName(projectTrade.custom_name || projectTrade.trades.name)
  }

  const handleSaveEdit = async () => {
    if (!editingId || !editingName.trim()) return

    setSaving(true)
    try {
      const projectTrade = projectTrades.find(pt => pt.id === editingId)
      if (projectTrade) {
        await apiClient.updateProjectTrade(
          projectId,
          editingId,
          projectTrade.trade_id,
          editingName.trim()
        )
      }
      await fetchData()
      setEditingId(null)
      setEditingName('')
    } catch (error) {
      console.error('Error updating trade:', error)
    } finally {
      setSaving(false)
    }
  }

  const handleCancelEdit = () => {
    setEditingId(null)
    setEditingName('')
  }

  const handleAddTrade = async () => {
    if (!newTradeId) return

    setSaving(true)
    try {
      await apiClient.addProjectTrade(projectId, newTradeId)
      await fetchData()
      setNewTradeId('')
    } catch (error) {
      console.error('Error adding trade:', error)
    } finally {
      setSaving(false)
    }
  }

  const handleCreateAndAddTrade = async () => {
    if (!newTradeName.trim()) return

    setSaving(true)
    try {
      // First create the trade
      const newTrade = await apiClient.createTrade({ name: newTradeName.trim() }) as { id: string }
      
      // Then add it to the project
      await apiClient.addProjectTrade(projectId, newTrade.id)
      await fetchData()
      setNewTradeName('')
    } catch (error) {
      console.error('Error creating trade:', error)
    } finally {
      setSaving(false)
    }
  }

  const handleRemoveTrade = async (projectTradeId: string) => {
    if (!confirm('Are you sure you want to remove this trade from this project?')) {
      return
    }

    setSaving(true)
    try {
      await apiClient.removeProjectTrade(projectId, projectTradeId)
      await fetchData()
    } catch (error) {
      console.error('Error removing trade:', error)
    } finally {
      setSaving(false)
    }
  }

  const availableTrades = allTrades.filter(trade => 
    !projectTrades.some(pt => pt.trade_id === trade.id)
  )

  return (
    <Transition.Root show={isOpen} as={Fragment}>
      <Dialog as="div" className="relative z-50" onClose={onClose}>
        <Transition.Child
          as={Fragment}
          enter="ease-in-out duration-300"
          enterFrom="opacity-0"
          enterTo="opacity-100"
          leave="ease-in-out duration-300"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
        >
          <div className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" />
        </Transition.Child>

        <div className="fixed inset-0 overflow-hidden">
          <div className="absolute inset-0 overflow-hidden">
            <div className="pointer-events-none fixed inset-y-0 right-0 flex max-w-full pl-10">
              <Transition.Child
                as={Fragment}
                enter="transform transition ease-in-out duration-300"
                enterFrom="translate-x-full"
                enterTo="translate-x-0"
                leave="transform transition ease-in-out duration-300"
                leaveFrom="translate-x-0"
                leaveTo="translate-x-full"
              >
                <Dialog.Panel className="pointer-events-auto relative w-screen max-w-md">
                  <div className="flex h-full flex-col overflow-y-scroll bg-white shadow-xl">
                    {/* Header */}
                    <div className="px-6 py-4 bg-gray-50 border-b">
                      <div className="flex items-center justify-between">
                        <Dialog.Title className="text-lg font-medium text-gray-900">
                          Project Trades
                        </Dialog.Title>
                        <button
                          type="button"
                          className="rounded-md text-gray-400 hover:text-gray-500"
                          onClick={onClose}
                        >
                          <span className="sr-only">Close panel</span>
                          <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                          </svg>
                        </button>
                      </div>
                      <p className="mt-1 text-sm text-gray-600">
                        Manage trades for this specific project.
                      </p>
                    </div>

                    {/* Content */}
                    <div className="flex-1 px-6 py-4">
                      {loading ? (
                        <div className="text-center py-4">
                          <div className="text-gray-500">Loading trades...</div>
                        </div>
                      ) : (
                        <div className="space-y-2">
                          {projectTrades.map((projectTrade) => (
                            <div key={projectTrade.id} className="flex items-center space-x-2 group">
                              {/* Trade name */}
                              {editingId === projectTrade.id ? (
                                <input
                                  type="text"
                                  value={editingName}
                                  onChange={(e) => setEditingName(e.target.value)}
                                  onKeyDown={(e) => {
                                    if (e.key === 'Enter') handleSaveEdit()
                                    if (e.key === 'Escape') handleCancelEdit()
                                  }}
                                  className="flex-1 px-2 py-1 border rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 text-black"
                                  autoFocus
                                />
                              ) : (
                                <div className="flex-1 py-1 text-sm text-black">
                                  {projectTrade.custom_name || projectTrade.trades.name}
                                </div>
                              )}

                              {/* Action buttons */}
                              {editingId === projectTrade.id ? (
                                <div className="flex space-x-1">
                                  <button
                                    onClick={handleSaveEdit}
                                    disabled={saving}
                                    className="p-1 text-green-600 hover:text-green-700"
                                    title="Save"
                                  >
                                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                                    </svg>
                                  </button>
                                  <button
                                    onClick={handleCancelEdit}
                                    className="p-1 text-gray-400 hover:text-gray-600"
                                    title="Cancel"
                                  >
                                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                    </svg>
                                  </button>
                                </div>
                              ) : (
                                <div className="flex space-x-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                  <button
                                    onClick={() => handleEdit(projectTrade)}
                                    className="p-1 text-gray-400 hover:text-gray-600"
                                    title="Edit"
                                  >
                                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                                    </svg>
                                  </button>
                                  <button
                                    onClick={() => handleRemoveTrade(projectTrade.id)}
                                    disabled={saving}
                                    className="p-1 text-red-400 hover:text-red-600"
                                    title="Remove"
                                  >
                                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                    </svg>
                                  </button>
                                </div>
                              )}
                            </div>
                          ))}

                          {/* Add existing trade */}
                          {availableTrades.length > 0 && (
                            <div className="flex items-center space-x-2 pt-2 border-t">
                              <select
                                value={newTradeId}
                                onChange={(e) => setNewTradeId(e.target.value)}
                                className="flex-1 px-2 py-1 border rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 text-black"
                              >
                                <option value="">Select a trade...</option>
                                {availableTrades.map(trade => (
                                  <option key={trade.id} value={trade.id}>{trade.name}</option>
                                ))}
                              </select>
                              <button
                                onClick={handleAddTrade}
                                disabled={!newTradeId || saving}
                                className="px-3 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                              >
                                Add
                              </button>
                            </div>
                          )}

                          {/* Create and add new trade */}
                          <div className="flex items-center space-x-2 pt-2 border-t">
                            <input
                              type="text"
                              value={newTradeName}
                              onChange={(e) => setNewTradeName(e.target.value)}
                              onKeyDown={(e) => {
                                if (e.key === 'Enter') handleCreateAndAddTrade()
                              }}
                              placeholder="Create new trade..."
                              className="flex-1 px-2 py-1 border rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 text-black"
                            />
                            <button
                              onClick={handleCreateAndAddTrade}
                              disabled={!newTradeName.trim() || saving}
                              className="px-3 py-1 text-sm bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                              Create
                            </button>
                          </div>
                        </div>
                      )}
                    </div>

                    {/* Footer */}
                    <div className="px-6 py-4 bg-gray-50 border-t">
                      <p className="text-xs text-gray-500">
                        {projectTrades.length} trades enabled for this project.
                      </p>
                    </div>
                  </div>
                </Dialog.Panel>
              </Transition.Child>
            </div>
          </div>
        </div>
      </Dialog>
    </Transition.Root>
  )
}
