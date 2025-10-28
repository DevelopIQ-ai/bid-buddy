'use client'

import { Fragment, useState, useEffect } from 'react'
import { Dialog, Transition } from '@headlessui/react'
import { apiClient } from '@/lib/api-client'

interface Trade {
  id: string
  name: string
  is_active: boolean
}

interface TradesFlyoutProps {
  isOpen: boolean
  onClose: () => void
}

export default function TradesFlyout({ isOpen, onClose }: TradesFlyoutProps) {
  const [trades, setTrades] = useState<Trade[]>([])
  const [loading, setLoading] = useState(true)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editingName, setEditingName] = useState('')
  const [newTradeName, setNewTradeName] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (isOpen) {
      fetchTrades()
    }
  }, [isOpen])

  const fetchTrades = async () => {
    try {
      setLoading(true)
      const data = await apiClient.getTrades() as Trade[]
      setTrades(data)
    } catch (error) {
      console.error('Error fetching trades:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleEdit = (trade: Trade) => {
    setEditingId(trade.id)
    setEditingName(trade.name)
  }

  const handleSaveEdit = async () => {
    if (!editingId || !editingName.trim()) return

    setSaving(true)
    try {
      await apiClient.updateTrade(editingId, { 
        name: editingName.trim()
      })
      await fetchTrades()
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
    if (!newTradeName.trim()) return

    setSaving(true)
    try {
      await apiClient.createTrade({ 
        name: newTradeName.trim()
      })
      await fetchTrades()
      setNewTradeName('')
    } catch (error) {
      console.error('Error creating trade:', error)
    } finally {
      setSaving(false)
    }
  }

  const handleDeleteTrade = async (tradeId: string) => {
    if (!confirm('Are you sure you want to delete this trade? This will remove it from all projects.')) {
      return
    }

    setSaving(true)
    try {
      await apiClient.deleteTrade(tradeId)
      await fetchTrades()
    } catch (error) {
      console.error('Error deleting trade:', error)
    } finally {
      setSaving(false)
    }
  }



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
                          Manage Trades
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
                    </div>

                    {/* Content */}
                    <div className="flex-1 px-6 py-4">
                      {loading ? (
                        <div className="text-center py-4">
                          <div className="text-gray-500">Loading trades...</div>
                        </div>
                      ) : (
                        <div className="space-y-2">
                          {trades.map((trade, index) => (
                            <div key={trade.id} className="flex items-center space-x-2 group">
                              {/* Trade name */}
                              {editingId === trade.id ? (
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
                                <div className="flex-1 py-1 text-sm text-black">{trade.name}</div>
                              )}

                              {/* Action buttons */}
                              {editingId === trade.id ? (
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
                                    onClick={() => handleEdit(trade)}
                                    className="p-1 text-gray-400 hover:text-gray-600"
                                    title="Edit"
                                  >
                                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                                    </svg>
                                  </button>
                                  <button
                                    onClick={() => handleDeleteTrade(trade.id)}
                                    disabled={saving}
                                    className="p-1 text-red-400 hover:text-red-600"
                                    title="Delete"
                                  >
                                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                    </svg>
                                  </button>
                                </div>
                              )}
                            </div>
                          ))}

                          {/* Add new trade */}
                          <div className="flex items-center space-x-2 pt-2 border-t">
                            <input
                              type="text"
                              value={newTradeName}
                              onChange={(e) => setNewTradeName(e.target.value)}
                              onKeyDown={(e) => {
                                if (e.key === 'Enter') handleAddTrade()
                              }}
                              placeholder="Add new trade..."
                              className="flex-1 px-2 py-1 border rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 text-black"
                            />
                            <button
                              onClick={handleAddTrade}
                              disabled={!newTradeName.trim() || saving}
                              className="px-3 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                              Add
                            </button>
                          </div>
                        </div>
                      )}
                    </div>

                    {/* Footer */}
                    <div className="px-6 py-4 bg-gray-50 border-t">
                      <p className="text-xs text-gray-500">
                        {trades.length} trades configured. Changes apply to all future projects.
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