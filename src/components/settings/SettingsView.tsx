import { useState } from 'react'
import { StoragePanel } from './StoragePanel'
import { ModelPanel } from './ModelPanel'
import { PerformancePanel } from './PerformancePanel'
import { PrivacyPanel } from './PrivacyPanel'

type Tab = 'general' | 'recording' | 'storage' | 'privacy'

const TABS: { id: Tab; label: string }[] = [
  { id: 'general', label: 'General' },
  { id: 'recording', label: 'Recording' },
  { id: 'storage', label: 'Storage' },
  { id: 'privacy', label: 'Privacy' },
]

export function SettingsView() {
  const [activeTab, setActiveTab] = useState<Tab>('general')

  return (
    <div className="flex h-full">
      <div className="w-40 border-r bg-gray-50 p-2 space-y-1">
        {TABS.map(({ id, label }) => (
          <button
            key={id}
            onClick={() => setActiveTab(id)}
            className={`w-full text-left px-3 py-2 rounded text-sm ${
              activeTab === id ? 'bg-white shadow-sm font-medium' : 'hover:bg-gray-100'
            }`}
          >
            {label}
          </button>
        ))}
      </div>
      <div className="flex-1 p-6 overflow-y-auto">
        {activeTab === 'general' && <PerformancePanel />}
        {activeTab === 'recording' && <ModelPanel />}
        {activeTab === 'storage' && <StoragePanel />}
        {activeTab === 'privacy' && <PrivacyPanel />}
      </div>
    </div>
  )
}
