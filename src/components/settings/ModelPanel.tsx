import { useState, useEffect } from 'react'
import { getSetting, setSetting } from '../../api/tauri'

function isTauriAvailable(): boolean {
  return typeof window !== 'undefined' && '__TAURI__' in window
}

export function ModelPanel() {
  const [vadThreshold, setVadThreshold] = useState('0.5')
  const [gapSeconds, setGapSeconds] = useState('60')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!isTauriAvailable()) return
    getSetting('vad_threshold').then((v) => v && setVadThreshold(v)).catch(() => {})
    getSetting('conversation_gap_seconds').then((v) => v && setGapSeconds(v)).catch(() => {})
  }, [])

  async function saveVAD(value: string) {
    if (!isTauriAvailable()) return
    setSaving(true)
    try {
      await setSetting('vad_threshold', value)
      setVadThreshold(value)
    } finally { setSaving(false) }
  }

  async function saveGap(value: string) {
    if (!isTauriAvailable()) return
    setSaving(true)
    try {
      await setSetting('conversation_gap_seconds', value)
      setGapSeconds(value)
    } finally { setSaving(false) }
  }

  return (
    <div className="space-y-6">
      <div>
        <h3 className="font-medium mb-3">Speech Detection (VAD)</h3>
        <label className="block text-sm text-gray-600 mb-1">
          Silence threshold: {vadThreshold}
        </label>
        <input
          type="range"
          min="0.1"
          max="0.9"
          step="0.1"
          value={vadThreshold}
          onChange={(e) => saveVAD(e.target.value)}
          disabled={saving}
          className="w-full"
        />
        <p className="text-xs text-gray-500 mt-1">Lower = more sensitive to quiet speech</p>
      </div>

      <div>
        <h3 className="font-medium mb-3">Conversation Split</h3>
        <label className="block text-sm text-gray-600 mb-1">
          Silence gap: {gapSeconds} seconds
        </label>
        <input
          type="range"
          min="30"
          max="300"
          step="30"
          value={gapSeconds}
          onChange={(e) => saveGap(e.target.value)}
          disabled={saving}
          className="w-full"
        />
        <p className="text-xs text-gray-500 mt-1">Split conversation after this much silence</p>
      </div>
    </div>
  )
}
