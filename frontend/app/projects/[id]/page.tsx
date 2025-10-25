'use client'

import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { apiClient } from '@/lib/api-client'
import { useAuth } from '@/app/providers'

interface Project {
  id: string
  name: string
  enabled: boolean
  drive_folder_id?: string
  is_drive_folder?: boolean
}

interface Trade {
  name: string
  bidderCount: number
}

// Demo data for construction trades
const DEMO_TRADES: Trade[] = [
  { name: 'Concrete', bidderCount: 4 },
  { name: 'Framing', bidderCount: 3 },
  { name: 'Electrical', bidderCount: 6 },
  { name: 'Plumbing', bidderCount: 5 },
  { name: 'HVAC', bidderCount: 4 },
  { name: 'Roofing', bidderCount: 2 },
  { name: 'Drywall', bidderCount: 3 },
  { name: 'Flooring', bidderCount: 7 },
  { name: 'Painting', bidderCount: 5 },
  { name: 'Landscaping', bidderCount: 3 },
  { name: 'Masonry', bidderCount: 2 },
  { name: 'Steel/Structural', bidderCount: 1 },
  { name: 'Windows & Doors', bidderCount: 4 },
  { name: 'Insulation', bidderCount: 2 },
  { name: 'Site Work', bidderCount: 3 },
]

export default function ProjectDetail() {
  const params = useParams()
  const router = useRouter()
  const { user } = useAuth()
  const [project, setProject] = useState<Project | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (user && params.id) {
      fetchProject()
    }
  }, [user, params.id])

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
            <div className="flex items-center space-x-2">
              {project.is_drive_folder && (
                <svg className="w-5 h-5 text-blue-500" fill="currentColor" viewBox="0 0 20 20">
                  <path d="M2 6a2 2 0 012-2h5l2 2h5a2 2 0 012 2v6a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" />
                </svg>
              )}
              <h1 className="text-xl font-semibold text-black">{project.name}</h1>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <div className="px-4 py-6 sm:px-0">
          <div className="bg-white rounded-lg shadow">
            <div className="px-6 py-4 border-b border-gray-200">
              <h2 className="text-lg font-medium text-black">Trade Bidders</h2>
            </div>
            
            <div className="overflow-hidden">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 tracking-wider">
                      Trade
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 tracking-wider">
                      Number of Bidders
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {DEMO_TRADES.map((trade, index) => (
                    <tr key={index} className="hover:bg-gray-50">
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                        {trade.name}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        <div className="flex items-center">
                          <span className="text-lg font-semibold text-gray-700">{trade.bidderCount}</span>
                          <span className="ml-2 text-xs text-gray-500">bidders</span>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}