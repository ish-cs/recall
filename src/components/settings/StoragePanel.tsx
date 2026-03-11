import { useEffect, useState } from 'react'
import { getStorageUsage, deleteDataByAge, deleteAllData } from '../../api/tauri'
import type { StorageUsage, DeleteScope } from '../../api/types'

function isTauriAvailable(): boolean {
  return typeof window !== 'undefined' && '__TAURI__' in window
}

export function StoragePanel() {
  const [usage, setUsage] = useState<StorageUsage | null>(null)
  const [loading, setLoading] = useState(true)
  const [deleting, setDeleting] = useState(false)

  function load() {
    if (!isTauriAvailable()) {
      setLoading(false)
      return
    }
    getStorageUsage()
      .then(setUsage)
      .catch(console.error)
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  async function handleDeleteOlder(days: number, scope: DeleteScope) {
    if (!isTauriAvailable()) return
    if (!confirm(`Delete data older than ${days} days? This cannot be undone.`)) return
    setDeleting(true)
    try {
      await deleteDataByAge(days, scope)
      load()
    } catch (e) {
      console.error(e)
    } finally {
      setDeleting(false)
    }
  }

  async function handleDeleteAll() {
    if (!isTauriAvailable()) return
    const confirmText = 'DELETE'
    const input = prompt(`Type "${confirmText}" to delete ALL data:`)
    if (input !== confirmText) return
    setDeleting(true)
    try {
      await deleteAllData()
      alert('All data deleted. The app will restart.')
      window.location.reload()
    } catch (e) {
      console.error(e)
    } finally {
      setDeleting(false)
    }
  }

  if (loading) return <div className="text-sm text-gray-500">Loading…</div>

  const formatBytes = (b: number) => {
    if (b < 1024) return `${b} B`
    if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`
    if (b < 1024 * 1024 * 1024) return `${(b / (1024 * 1024)).toFixed(1)} MB`
    return `${(b / (1024 * 1024 * 1024)).toFixed(2)} GB`
  }

  const total = (usage?.audioBytes ?? 0) + (usage?.transcriptDbBytes ?? 0) + (usage?.modelsBytes ?? 0)

  return (
    <div className="space-y-6">
      <div>
        <h3 className="font-medium mb-3">Storage Usage</h3>
        <div className="space-y-2">
          <div className="flex justify-between text-sm">
            <span>Audio recordings</span>
            <span className="text-gray-600">{formatBytes(usage?.audioBytes ?? 0)}</span>
          </div>
          <div className="flex justify-between text-sm">
            <span>Transcripts & embeddings</span>
            <span className="text-gray-600">{formatBytes(usage?.transcriptDbBytes ?? 0)}</span>
          </div>
          <div className="flex justify-between text-sm">
            <span>ML models</span>
            <span className="text-gray-600">{formatBytes(usage?.modelsBytes ?? 0)}</span>
          </div>
          <div className="border-t pt-2 flex justify-between font-medium text-sm">
            <span>Total</span>
            <span>{formatBytes(total)}</span>
          </div>
        </div>
      </div>

      <div>
        <h3 className="font-medium mb-3">Delete Old Data</h3>
        <div className="flex gap-2">
          <button
            onClick={() => handleDeleteOlder(7, 'Both')}
            disabled={deleting}
            className="px-3 py-1.5 text-sm bg-gray-100 rounded hover:bg-gray-200 disabled:opacity-50"
          >
            7 days
          </button>
          <button
            onClick={() => handleDeleteOlder(30, 'Both')}
            disabled={deleting}
            className="px-3 py-1.5 text-sm bg-gray-100 rounded hover:bg-gray-200 disabled:opacity-50"
          >
            30 days
          </button>
          <button
            onClick={() => handleDeleteOlder(90, 'Both')}
            disabled={deleting}
            className="px-3 py-1.5 text-sm bg-gray-100 rounded hover:bg-gray-200 disabled:opacity-50"
          >
            90 days
          </button>
        </div>
      </div>

      <div>
        <h3 className="font-medium mb-3 text-red-600">Danger Zone</h3>
        <button
          onClick={handleDeleteAll}
          disabled={deleting}
          className="px-3 py-1.5 text-sm bg-red-50 text-red-600 rounded hover:bg-red-100 disabled:opacity-50"
        >
          Delete All Data
        </button>
      </div>
    </div>
  )
}
