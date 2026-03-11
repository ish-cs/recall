import type { SearchResult } from '../../api/types'

interface SearchResultItemProps {
  result: SearchResult
  query: string
  onClick: () => void
}

function highlight(text: string, query: string): string {
  if (!query.trim()) return text
  // Basic word-boundary highlight — wrap match in <mark>
  const escaped = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  return text.replace(new RegExp(`(${escaped})`, 'gi'), '<mark class="bg-yellow-200">$1</mark>')
}

function formatDate(ms: number): string {
  return new Date(ms).toLocaleString([], {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function SearchResultItem({ result, query, onClick }: SearchResultItemProps) {
  const highlighted = highlight(result.text, query)
  const modeLabel =
    result.matchType === 'semantic' ? 'semantic' : result.matchType === 'hybrid' ? 'hybrid' : ''

  return (
    <button
      onClick={onClick}
      className="w-full text-left p-4 border-b hover:bg-gray-50 transition-colors"
    >
      <div className="flex justify-between items-start gap-2 mb-1">
        <div className="text-xs text-gray-500">
          {formatDate(result.conversationStartedAt)}
          {result.speakerDisplayName && (
            <span className="ml-2 text-blue-600">{result.speakerDisplayName}</span>
          )}
        </div>
        {modeLabel && (
          <span className="text-xs text-gray-400 shrink-0">{modeLabel}</span>
        )}
      </div>
      <p
        className="text-sm text-gray-800 leading-relaxed"
        // eslint-disable-next-line react/no-danger
        dangerouslySetInnerHTML={{ __html: highlighted }}
      />
    </button>
  )
}
