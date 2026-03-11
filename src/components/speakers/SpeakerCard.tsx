import type { SpeakerProfile } from '../../api/types'

interface SpeakerCardProps {
  speaker: SpeakerProfile
  onRename: () => void
  onMerge: () => void
  onDelete: () => void
}

function getInitials(name: string | null): string {
  if (!name) return '?'
  const parts = name.split(' ')
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase()
  return name.slice(0, 2).toUpperCase()
}

const AVATAR_COLORS = [
  'bg-blue-500',
  'bg-green-500',
  'bg-purple-500',
  'bg-orange-500',
  'bg-pink-500',
  'bg-teal-500',
]

export function SpeakerCard({ speaker, onRename, onMerge, onDelete }: SpeakerCardProps) {
  const colorIndex = speaker.id.charCodeAt(0) % AVATAR_COLORS.length
  const initials = getInitials(speaker.displayName)

  return (
    <div className="bg-white rounded-lg border p-4 flex items-start gap-4">
      <div className={`w-12 h-12 rounded-full flex items-center justify-center text-white font-medium ${AVATAR_COLORS[colorIndex]}`}>
        {initials}
      </div>
      <div className="flex-1 min-w-0">
        <h3 className="font-medium text-sm truncate">
          {speaker.displayName ?? 'Unnamed Speaker'}
        </h3>
        <p className="text-xs text-gray-500 mt-0.5">
          {speaker.segmentCount} segments • {speaker.conversationCount} conversations
        </p>
        {speaker.isUser && (
          <span className="inline-block mt-1 text-xs px-1.5 py-0.5 bg-gray-100 text-gray-600 rounded">
            You
          </span>
        )}
      </div>
      <div className="flex gap-1">
        <button
          onClick={onRename}
          className="p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded"
          title="Rename"
        >
          ✎
        </button>
        <button
          onClick={onMerge}
          className="p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded"
          title="Merge"
        >
          ⊕
        </button>
        <button
          onClick={onDelete}
          className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded"
          title="Delete"
        >
          ✕
        </button>
      </div>
    </div>
  )
}
