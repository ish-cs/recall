import { useState, useEffect } from 'react'
import { getSetting, setSetting } from '../../api/tauri'

function isTauriAvailable(): boolean {
  return typeof window !== 'undefined' && '__TAURI__' in window
}

const POWER_MODES = [
  { value: 'low_power', label: 'Low Power', desc: 'Disable embeddings and summarization' },
  { value: 'balanced', label: 'Balanced', desc: 'Throttled background processing' },
  { value: 'performance', label: 'Performance', desc: 'Full speed, higher resource usage' },
]

export function PerformancePanel() {
  const [mode, setMode] = useState('balanced')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!isTauriAvailable()) return
    getSetting('power_mode').then((v) => v && setMode(v)).catch(() => {})
  }, [])

  async function saveMode(value: string) {
    if (!isTauriAvailable()) return
    setSaving(true)
    try {
      await setSetting('power_mode', value)
      setMode(value)
    } finally { setSaving(false) }
  }

  return (
    <div className="space-y-4">
      <h3 className="font-medium">Power Mode</h3>
      <div className="space-y-2">
        {POWER_MODES.map((m) => (
          <label
            key={m.value}
            className={`flex items-center gap-3 p-3 border rounded cursor-pointer ${
              mode === m.value ? 'border-blue-500 bg-blue-50' : 'hover:bg-gray-50'
            }`}
          >
            <input
              type="radio"
              name="power_mode"
              value={m.value}
              checked={mode === m.value}
              onChange={() => saveMode(m.value)}
              disabled={saving}
              className="text-blue-600"
            />
            <div>
              <div className="font-medium text-sm">{m.label}</div>
              <div className="text-xs text-gray-500">{m.desc}</div>
            </div>
          </label>
        ))}
      </div>
    </div>
  )
}
