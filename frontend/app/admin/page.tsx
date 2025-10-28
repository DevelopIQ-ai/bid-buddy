'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'

interface AttachmentAnalyzed {
  filename: string
  company_name?: string
  trade?: string
  project_name?: string
  status?: string
  drive_upload?: {
    success: boolean
    error?: string
  }
}

interface EmailTrace {
  trace_id: string
  timestamp: string
  email_from: string | null
  email_subject: string | null
  email_has_attachments: boolean

  classification_bid_proposal: boolean | null
  classification_should_forward: boolean | null

  routed_to: string | null
  forward_status: string | null
  forward_message_id: string | null

  attachment_count: number | null
  attachments_analyzed: AttachmentAnalyzed[] | null

  status: string
  error: string | null
}

export default function AdminPage() {
  const [traces, setTraces] = useState<EmailTrace[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedTrace, setSelectedTrace] = useState<string | null>(null)
  const [userFilter, setUserFilter] = useState<string>('jessica@vanbruntco.com') // Default to Jessica

  useEffect(() => {
    fetchTraces()
  }, [])

  const fetchTraces = async () => {
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
      const url = userFilter
        ? `${apiUrl}/admin/traces?limit=50&user_email=${encodeURIComponent(userFilter)}`
        : `${apiUrl}/admin/traces?limit=50`
      const response = await fetch(url)
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }
      const data = await response.json()
      setTraces(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch traces')
    } finally {
      setLoading(false)
    }
  }

  const getRouteBadge = (route: string | null) => {
    if (!route) return null

    const colors = {
      'analyze_attachment': 'bg-blue-100 text-blue-800',
      'forward_email': 'bg-purple-100 text-purple-800',
      'skipped': 'bg-gray-100 text-gray-800'
    }

    return (
      <span className={`px-2 py-1 rounded text-xs font-medium ${colors[route as keyof typeof colors] || 'bg-gray-100 text-gray-800'}`}>
        {route}
      </span>
    )
  }

  const getStatusBadge = (status: string) => {
    const colors = {
      'completed': 'bg-green-100 text-green-800',
      'error': 'bg-red-100 text-red-800',
      'pending': 'bg-yellow-100 text-yellow-800'
    }

    return (
      <span className={`px-2 py-1 rounded text-xs font-medium ${colors[status as keyof typeof colors] || 'bg-gray-100 text-gray-800'}`}>
        {status}
      </span>
    )
  }

  const formatTimestamp = (timestamp: string) => {
    try {
      return new Date(timestamp).toLocaleString()
    } catch {
      return timestamp
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 p-8">
        <div className="max-w-7xl mx-auto">
          <h1 className="text-3xl font-bold mb-8">Email Agent Traces</h1>
          <div className="bg-white rounded-lg shadow p-8 text-center">
            <p className="text-gray-600">Loading traces...</p>
          </div>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 p-8">
        <div className="max-w-7xl mx-auto">
          <h1 className="text-3xl font-bold mb-8">Email Agent Traces</h1>
          <div className="bg-red-50 border border-red-200 rounded-lg p-4">
            <p className="text-red-800">Error: {error}</p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-7xl mx-auto">
        <div className="mb-8">
          <div className="flex justify-between items-center mb-4">
            <h1 className="text-3xl font-bold">Email Agent Traces</h1>
            <div className="flex gap-4">
              <Link
                href="/"
                className="px-4 py-2 bg-gray-200 text-gray-700 rounded hover:bg-gray-300"
              >
                ← Back to Dashboard
              </Link>
              <button
                onClick={fetchTraces}
                className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
              >
                Refresh
              </button>
            </div>
          </div>

          {/* User Filter */}
          <div className="bg-white rounded-lg shadow p-4">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Filter by User
            </label>
            <div className="flex gap-2">
              <select
                value={userFilter}
                onChange={(e) => {
                  setUserFilter(e.target.value)
                  setLoading(true)
                }}
                className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">All Users</option>
                <option value="jessica@vanbruntco.com">Jessica (jessica@vanbruntco.com)</option>
                <option value="evan@developiq.ai">Evan (evan@developiq.ai)</option>
                <option value="kush@developiq.ai">Kush (kush@developiq.ai)</option>
              </select>
              <button
                onClick={fetchTraces}
                className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
              >
                Apply Filter
              </button>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow overflow-hidden">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Timestamp
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    From
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Subject
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Classification
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Routed To
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Result
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Status
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {traces.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="px-6 py-4 text-center text-gray-500">
                      No traces found. Process some emails to see them here!
                    </td>
                  </tr>
                ) : (
                  traces.map((trace) => (
                    <tr
                      key={trace.trace_id}
                      className="hover:bg-gray-50 cursor-pointer"
                      onClick={() => setSelectedTrace(selectedTrace === trace.trace_id ? null : trace.trace_id)}
                    >
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {formatTimestamp(trace.timestamp)}
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-900">
                        <div className="max-w-xs truncate">{trace.email_from || 'N/A'}</div>
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-900">
                        <div className="max-w-xs truncate">{trace.email_subject || 'N/A'}</div>
                        {trace.email_has_attachments && (
                          <span className="ml-2 text-xs text-gray-500">📎</span>
                        )}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm">
                        <div className="flex flex-col gap-1">
                          {trace.classification_bid_proposal && (
                            <span className="text-xs text-blue-600">✓ Bid Proposal</span>
                          )}
                          {trace.classification_should_forward && (
                            <span className="text-xs text-purple-600">✓ Should Forward</span>
                          )}
                          {!trace.classification_bid_proposal && !trace.classification_should_forward && (
                            <span className="text-xs text-gray-400">No action</span>
                          )}
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        {getRouteBadge(trace.routed_to)}
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-900">
                        {trace.routed_to === 'analyze_attachment' && (
                          <div className="space-y-2">
                            <div className="text-xs font-medium">
                              {trace.attachment_count || 0} attachment(s) analyzed
                            </div>
                            {trace.attachments_analyzed && trace.attachments_analyzed.length > 0 && (
                              <div className="space-y-3">
                                {trace.attachments_analyzed.map((att, idx) => (
                                  <div key={idx} className="border-l-2 border-blue-300 pl-2 space-y-1">
                                    <div className="text-xs font-medium text-gray-700 truncate max-w-xs" title={att.filename}>
                                      📄 {att.filename}
                                    </div>
                                    <div className="text-xs text-gray-600">
                                      <span className="font-medium">Company:</span> {att.company_name || 'N/A'}
                                    </div>
                                    <div className="text-xs text-gray-600">
                                      <span className="font-medium">Trade:</span> {att.trade || 'N/A'}
                                    </div>
                                    <div className="text-xs text-gray-600">
                                      <span className="font-medium">Project:</span> {att.project_name || 'N/A'}
                                    </div>
                                    <div className="text-xs">
                                      <span className="font-medium">Status:</span>{' '}
                                      <span className={att.status === 'analyzed' ? 'text-green-600' : 'text-red-600'}>
                                        {att.status || 'unknown'}
                                      </span>
                                    </div>
                                    {att.drive_upload && (
                                      <div className="text-xs">
                                        <span className="font-medium">Drive Upload:</span>{' '}
                                        {att.drive_upload.success ? (
                                          <span className="text-green-600">✓ Success</span>
                                        ) : (
                                          <span className="text-red-600" title={att.drive_upload.error}>
                                            ✗ Failed
                                          </span>
                                        )}
                                      </div>
                                    )}
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        )}
                        {trace.routed_to === 'forward_email' && (
                          <div className="text-xs">
                            {trace.forward_status === 'forwarded' ? '✓ Forwarded' : '✗ Failed'}
                          </div>
                        )}
                        {trace.routed_to === 'skipped' && (
                          <div className="text-xs text-gray-500">—</div>
                        )}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        {getStatusBadge(trace.status)}
                        {trace.error && (
                          <div className="text-xs text-red-600 mt-1">{trace.error}</div>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Legend */}
        <div className="mt-6 bg-white rounded-lg shadow p-6">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Legend</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
            <div>
              <h4 className="font-medium text-gray-900 mb-2">Routes</h4>
              <ul className="space-y-1 text-gray-600">
                <li><span className="bg-blue-100 text-blue-800 px-2 py-0.5 rounded text-xs">analyze_attachment</span> - Email has bid proposal</li>
                <li><span className="bg-purple-100 text-purple-800 px-2 py-0.5 rounded text-xs">forward_email</span> - Question/important email</li>
                <li><span className="bg-gray-100 text-gray-800 px-2 py-0.5 rounded text-xs">skipped</span> - No action needed</li>
              </ul>
            </div>
            <div>
              <h4 className="font-medium text-gray-900 mb-2">Classification</h4>
              <ul className="space-y-1 text-gray-600">
                <li><span className="text-blue-600">✓ Bid Proposal</span> - Has PDF/DOCX attachment</li>
                <li><span className="text-purple-600">✓ Should Forward</span> - Needs admin attention</li>
              </ul>
            </div>
            <div>
              <h4 className="font-medium text-gray-900 mb-2">Status</h4>
              <ul className="space-y-1 text-gray-600">
                <li><span className="bg-green-100 text-green-800 px-2 py-0.5 rounded text-xs">completed</span> - Successfully processed</li>
                <li><span className="bg-red-100 text-red-800 px-2 py-0.5 rounded text-xs">error</span> - Processing failed</li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
