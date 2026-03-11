import type { ConversationSummary } from '../../api/types'

interface ConversationCardProps {
  conversation: ConversationSummary
  selected: boolean
  onClick: () => void
}

function formatDuration(startMs: number, endMs: number | null): string {
  const durationMs = (endMs ?? Date.now()) - startMs
  const minutes = Math.floor(durationMs / 60000)
  const seconds = Math.floor((durationMs % 60000) / 1000)
  if (minutes === 0) return `${seconds}s`
  return `${minutes}m ${seconds}s`
}

function formatDate(ms: number): string {
  return new Date(ms).toLocaleString([], {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function ConversationCard({ conversation: c, selected, onClick }: ConversationCardProps) {
  return (
    <button
      onClick={onClick}
      className={`w-full text-left p-4 border-b hover:bg-gray-50 transition-colors ${
        selected ? 'bg-blue-50 border-l-2 border-l-blue-500' : ''
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="font-medium text-sm text-gray-900 truncate">
          {c.title ?? formatDate(c.startedAt)}
        </div>
        <div className="text-xs text-gray-400 shrink-0">
          {formatDuration(c.startedAt, c.endedAt)}
        </div>
      </div>
      <div className="flex gap-3 mt-1 text-xs text-gray-500">
        <span>{c.segmentCount} segments</span>
        {c.speakerCount > 0 && <span>{c.speakerCount} speakers</span>}
        {c.endedAt == null && <span className="text-red-500 font-medium">● Live</span>}
      </div>
      {c.summary && (
        <p className="mt-1 text-xs text-gray-600 line-clamp-2">{c.summary}</p>
      )}
      {c.topicTags.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-2">
          {c.topicTags.slice(0, 4).map((tag) => (
            <span key={tag} className="px-1.5 py-0.5 bg-gray-100 text-gray-600 rounded text-xs">
              {tag}
            </span>
          ))}
        </div>
      )}
    </button>
  )
}
