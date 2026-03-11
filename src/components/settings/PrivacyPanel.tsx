import { useState } from 'react'
import { exportTranscripts } from '../../api/tauri'

function isTauriAvailable(): boolean {
  return typeof window !== 'undefined' && '__TAURI__' in window
}

export function PrivacyPanel() {
  const [exporting, setExporting] = useState(false)

  async function handleExport() {
    if (!isTauriAvailable()) return
    // Use path as-is; Rust will expand ~ internally
    const path = prompt('Enter path to export JSON:')
    if (!path) return
    setExporting(true)
    try {
      await exportTranscripts(path)
      alert('Export complete!')
    } catch (e) {
      alert('Export failed: ' + e)
    } finally {
      setExporting(false)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h3 className="font-medium mb-3">Data Export</h3>
        <p className="text-sm text-gray-600 mb-3">
          Export all transcripts as JSON for backup or transfer.
        </p>
        <button
          onClick={handleExport}
          disabled={exporting}
          className="px-3 py-1.5 text-sm bg-gray-100 rounded hover:bg-gray-200 disabled:opacity-50"
        >
          {exporting ? 'Exporting...' : 'Export All Transcripts'}
        </button>
      </div>

      <div>
        <h3 className="font-medium mb-3">Privacy Information</h3>
        <ul className="text-sm text-gray-600 space-y-2">
          <li>• All audio processing happens locally on your device</li>
          <li>• No audio or transcripts are sent to external servers</li>
          <li>• Transcripts are stored in an encrypted local database</li>
          <li>• You can delete all data at any time from Storage settings</li>
        </ul>
      </div>
    </div>
  )
}
