import { useEffect, useState } from 'react'
import type { ConversationDetail as ConversationDetailType } from '../../api/types'
import { getConversation, deleteConversation } from '../../api/tauri'
import { useStore } from '../../store'
import { TranscriptView } from '../transcript/TranscriptView'

function isTauriAvailable(): boolean {
  return typeof window !== 'undefined' && '__TAURI__' in window
}

interface ConversationDetailProps {
  conversationId: string
  onClose: () => void
}

export function ConversationDetail({ conversationId, onClose }: ConversationDetailProps) {
  const [detail, setDetail] = useState<ConversationDetailType | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const removeConversation = useStore((s) => s.removeConversation)

  useEffect(() => {
    if (!isTauriAvailable()) {
      setLoading(false)
      return
    }
    setLoading(true)
    setError(null)
    getConversation(conversationId)
      .then(setDetail)
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false))
  }, [conversationId])

  async function handleDelete() {
    if (!isTauriAvailable()) return
    if (!confirm('Delete this conversation and its transcript?')) return
    try {
      await deleteConversation(conversationId, false)
      removeConversation(conversationId)
      onClose()
    } catch (e) {
      console.error('Delete failed', e)
    }
  }

  if (loading) {
    return <div className="p-6 text-sm text-gray-500">Loading…</div>
  }
  if (error || !detail) {
    return <div className="p-6 text-sm text-red-500">Failed to load: {error}</div>
  }

  const startDate = new Date(detail.startedAt).toLocaleString()
  const endDate = detail.endedAt ? new Date(detail.endedAt).toLocaleString() : 'ongoing'

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="p-4 border-b flex items-start justify-between gap-4">
        <div>
          <h2 className="font-semibold text-base">
            {detail.title ?? startDate}
          </h2>
          <p className="text-xs text-gray-500 mt-0.5">{startDate} – {endDate}</p>
          {detail.summary && (
            <p className="text-sm text-gray-700 mt-2">{detail.summary}</p>
          )}
        </div>
        <div className="flex gap-2 shrink-0">
          <button
            onClick={handleDelete}
            className="text-xs px-2 py-1 text-red-600 hover:bg-red-50 rounded"
          >
            Delete
          </button>
          <button
            onClick={onClose}
            className="text-xs px-2 py-1 text-gray-600 hover:bg-gray-100 rounded"
          >
            ✕
          </button>
        </div>
      </div>

      {/* Transcript */}
      <div className="flex-1 overflow-y-auto px-4">
        <TranscriptView conversation={detail} />
      </div>
    </div>
  )
}
