import { useStore } from '../../store'
import type { SearchMode } from '../../api/types'

const MODES: { value: SearchMode; label: string }[] = [
  { value: 'keyword', label: 'Keyword' },
  { value: 'semantic', label: 'Semantic' },
  { value: 'hybrid', label: 'Hybrid' },
]

export function SearchBar() {
  const searchQuery = useStore((s) => s.searchQuery)
  const searchMode = useStore((s) => s.searchMode)
  const setSearchQuery = useStore((s) => s.setSearchQuery)
  const setSearchMode = useStore((s) => s.setSearchMode)

  return (
    <div className="flex items-center gap-2 p-3 border-b bg-white">
      <input
        type="search"
        value={searchQuery}
        onChange={(e) => setSearchQuery(e.target.value)}
        placeholder="Search conversations…"
        className="flex-1 px-3 py-1.5 border rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
      />
      <div className="flex rounded border overflow-hidden text-xs">
        {MODES.map(({ value, label }) => (
          <button
            key={value}
            onClick={() => setSearchMode(value)}
            className={`px-2.5 py-1.5 ${
              searchMode === value
                ? 'bg-blue-600 text-white'
                : 'bg-white text-gray-600 hover:bg-gray-50'
            }`}
          >
            {label}
          </button>
        ))}
      </div>
    </div>
  )
}
