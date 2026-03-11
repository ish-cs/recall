import { useStore } from '../../store'
import { useSearch } from '../../hooks/useSearch'
import { SearchBar } from './SearchBar'
import { SearchResultItem } from './SearchResultItem'

export function SearchView() {
  const searchQuery = useStore((s) => s.searchQuery)
  const searchResults = useStore((s) => s.searchResults)
  const searchLoading = useStore((s) => s.searchLoading)
  const setActiveView = useStore((s) => s.setActiveView)
  const setSelected = useStore((s) => s.setSelectedConversation)

  // Trigger debounced search whenever query/mode/filters change
  useSearch()

  function handleResultClick(conversationId: string) {
    setActiveView('timeline')
    setSelected(conversationId, null)
  }

  return (
    <div className="flex flex-col h-full">
      <SearchBar />
      <div className="flex-1 overflow-y-auto">
        {searchLoading && (
          <div className="p-4 text-sm text-gray-400">Searching…</div>
        )}
        {!searchLoading && searchQuery && searchResults.length === 0 && (
          <div className="p-4 text-sm text-gray-500">No results for "{searchQuery}"</div>
        )}
        {!searchLoading && !searchQuery && (
          <div className="p-4 text-sm text-gray-400">
            Type to search across all conversations.
          </div>
        )}
        {searchResults.map((result) => (
          <SearchResultItem
            key={result.segmentId}
            result={result}
            query={searchQuery}
            onClick={() => handleResultClick(result.conversationId)}
          />
        ))}
      </div>
    </div>
  )
}
