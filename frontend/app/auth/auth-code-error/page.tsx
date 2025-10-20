'use client'

import { useRouter, useSearchParams } from 'next/navigation'
import { Suspense } from 'react'

function AuthErrorContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const error = searchParams.get('error')
  const description = searchParams.get('description')

  const getErrorMessage = () => {
    switch (error) {
      case 'server_error':
        return 'Database error occurred while creating your account.'
      case 'auth_failed':
        return 'Authentication failed during the sign-in process.'
      case 'missing_code':
        return 'No authorization code was provided.'
      default:
        return 'An unexpected error occurred during sign-in.'
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="max-w-md w-full bg-white rounded-lg shadow-md p-6">
        <div className="text-center">
          <div className="mx-auto flex items-center justify-center h-12 w-12 rounded-full bg-red-100">
            <svg className="h-6 w-6 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.96-.833-2.732 0L3.732 16c-.77.833.192 2.5 1.732 2.5z" />
            </svg>
          </div>
          <h1 className="mt-4 text-lg font-semibold text-gray-900">Authentication Error</h1>
          <p className="mt-2 text-sm text-gray-600">
            {getErrorMessage()}
          </p>
          {description && (
            <div className="mt-3 p-3 bg-gray-50 rounded-md">
              <p className="text-xs text-gray-500 font-mono">
                {decodeURIComponent(description)}
              </p>
            </div>
          )}
          <div className="mt-6 space-y-3">
            <button
              onClick={() => router.push('/')}
              className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded-lg transition-colors"
            >
              Try Again
            </button>
            <button
              onClick={() => router.push('/')}
              className="w-full bg-gray-100 hover:bg-gray-200 text-gray-700 font-medium py-2 px-4 rounded-lg transition-colors"
            >
              Go Home
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default function AuthCodeError() {
  return (
    <Suspense fallback={<div>Loading...</div>}>
      <AuthErrorContent />
    </Suspense>
  )
}