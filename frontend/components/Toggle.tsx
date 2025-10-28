'use client'

import { Switch } from '@headlessui/react'

interface ToggleProps {
  enabled: boolean
  onChange: () => void
  disabled?: boolean
  locked?: boolean
}

export default function Toggle({ enabled, onChange, disabled, locked }: ToggleProps) {
  return (
    <div className="flex items-center space-x-2">
      {locked && (
        <svg className="w-4 h-4 text-gray-400" fill="currentColor" viewBox="0 0 20 20">
          <path fillRule="evenodd" d="M5 9V7a5 5 0 0110 0v2a2 2 0 012 2v5a2 2 0 01-2 2H5a2 2 0 01-2-2v-5a2 2 0 012-2zm8-2v2H7V7a3 3 0 016 0z" clipRule="evenodd" />
        </svg>
      )}
      <Switch
        checked={enabled}
        onChange={onChange}
        disabled={disabled || locked}
        className={`${
          enabled ? 'bg-blue-600' : 'bg-gray-200'
        } ${
          disabled || locked ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'
        } relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2`}
      >
        <span className="sr-only">Toggle project</span>
        <span
          className={`${
            enabled ? 'translate-x-6' : 'translate-x-1'
          } inline-block h-4 w-4 transform rounded-full bg-white transition-transform`}
        />
      </Switch>
    </div>
  )
}