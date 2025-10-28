'use client'

import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { apiClient } from '@/lib/api-client'
import { useAuth } from '@/app/providers'
import ProjectTradesFlyout from '@/components/ProjectTradesFlyout'

interface Project {
  id: string
  name: string
  enabled: boolean
  drive_folder_id?: string
  is_drive_folder?: boolean
}

interface BidderStat {
  trade_id: string
  trade_name: string
  display_name: string
  bidder_count: number
  proposal_count: number
  last_bid_received: string | null
}

export default function ProjectDetail() {
  const params = useParams()
  const router = useRouter()
  const { user } = useAuth()
  const [project, setProject] = useState<Project | null>(null)
  const [bidderStats, setBidderStats] = useState<BidderStat[]>([])
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)
  const [showTradesFlyout, setShowTradesFlyout] = useState(false)

  const fetchBidderStats = async () => {
    try {
      const stats = await apiClient.getProjectStats(params.id as string) as BidderStat[]
      setBidderStats(stats)
    } catch (error) {
      console.error('Error fetching bidder stats:', error)
    }
  }

  const handleAutoSync = async () => {
    if (!project?.drive_folder_id) return
    
    setSyncing(true)
    try {
      // Sync Drive files
      const driveResult = await apiClient.syncProjectDrive(params.id as string) as {
        errors?: string[]
        summary?: { 
          total_new: number
          all_files?: string[]
          skipped_files?: string[]
        }
        skipped_existing?: number
      }
      console.log('Drive sync complete:', driveResult)
      
      // Log detailed sync results
      if (driveResult.errors && driveResult.errors.length > 0) {
        console.warn('Sync errors:', driveResult.errors)
      }
      if (driveResult.summary) {
        console.log(`Drive sync summary: ${driveResult.summary.total_new} new proposals, ${driveResult.skipped_existing} skipped`)
        console.log('All files:', driveResult.summary.all_files)
        console.log('Skipped files:', driveResult.summary.skipped_files)
      }
      
      // Sync BuildingConnected emails
      try {
        const bcResult = await apiClient.syncBuildingConnected(params.id as string) as {
          new_proposals?: number
          skipped_existing?: number
          errors?: string[]
        }
        console.log('BuildingConnected sync complete:', bcResult)
        
        if (bcResult.new_proposals && bcResult.new_proposals > 0) {
          console.log(`BuildingConnected: ${bcResult.new_proposals} new proposals added`)
        }
      } catch (bcError) {
        // Don't fail if BuildingConnected sync fails
        console.warn('BuildingConnected sync failed:', bcError)
      }
      
      // Refresh stats after sync
      await fetchBidderStats()
    } catch (error) {
      console.error('Error syncing:', error)
      // Don't show error to user for auto-sync
    } finally {
      setSyncing(false)
    }
  }

  useEffect(() => {
    if (user && params.id) {
      fetchProject()
      fetchBidderStats()
    }
  }, [user, params.id])

  // Auto-sync when project loads (for Drive folders)
  useEffect(() => {
    if (project?.drive_folder_id && project?.is_drive_folder && !syncing) {
      handleAutoSync()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project?.id]) // Only sync once when project ID changes

  const fetchProject = async () => {
    try {
      const projects = await apiClient.getProjects() as Project[]
      const foundProject = projects.find(p => p.id === params.id)
      
      if (foundProject) {
        setProject(foundProject)
      } else {
        // Project not found, redirect back
        router.push('/')
      }
    } catch (error) {
      console.error('Error fetching project:', error)
      router.push('/')
    } finally {
      setLoading(false)
    }
  }

  const handleBack = () => {
    router.push('/')
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-lg">Loading project...</div>
      </div>
    )
  }

  if (!project) {
    return null
  }

  // Calculate total bidders across all trades
  const totalBidders = bidderStats.reduce((sum, stat) => sum + stat.bidder_count, 0)

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center h-16">
            <button
              onClick={handleBack}
              className="mr-4 p-2 hover:bg-gray-100 rounded-lg transition-colors"
              aria-label="Go back"
            >
              <svg className="w-5 h-5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
            </button>
            <div className="flex items-center space-x-4">
              <div className="flex items-center space-x-2">
                {project.is_drive_folder && (
                  <svg className="w-5 h-5 text-blue-500" fill="currentColor" viewBox="0 0 20 20">
                    <path d="M2 6a2 2 0 012-2h5l2 2h5a2 2 0 012 2v6a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" />
                  </svg>
                )}
                <h1 className="text-xl font-semibold text-black">{project.name}</h1>
              </div>
              {syncing && (
                <div className="flex items-center space-x-2 text-blue-600">
                  <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  <span className="text-sm font-medium">Syncing...</span>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <div className="px-4 py-6 sm:px-0">
          <div className="bg-white rounded-lg shadow">
            <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
              <h2 className="text-lg font-medium text-black">Trade Bidders</h2>
              <button
                onClick={() => setShowTradesFlyout(true)}
                className="px-3 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors"
              >
                Manage Trades
              </button>
            </div>
            
            <div className="overflow-hidden">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 tracking-wider">
                      Trade
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 tracking-wider">
                      Number of Bidders ({totalBidders} Total)
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {bidderStats.length === 0 ? (
                    <tr>
                      <td colSpan={2} className="px-6 py-4 text-center text-sm text-gray-500">
                        No trades configured for this project
                      </td>
                    </tr>
                  ) : (
                    bidderStats.map((stat) => (
                      <tr 
                        key={stat.trade_id} 
                        className="hover:bg-gray-50 cursor-pointer"
                        onClick={() => setShowTradesFlyout(true)}
                      >
                        <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                          {stat.display_name}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          <div className="flex items-center">
                            <span className="text-lg font-semibold text-gray-700">{stat.bidder_count}</span>
                            <span className="ml-2 text-xs text-gray-500">bidders</span>
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

      {/* Project Trades Flyout */}
      <ProjectTradesFlyout
        isOpen={showTradesFlyout}
        onClose={() => {
          setShowTradesFlyout(false)
          fetchBidderStats() // Refresh stats when closing
        }}
        projectId={params.id as string}
      />
    </div>
  )
}