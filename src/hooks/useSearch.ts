import { useCallback, useEffect, useRef } from 'react'
import { useStore } from '../store'
import { search } from '../api/tauri'

const DEBOUNCE_MS = 300

export function useSearch() {
  const searchQuery = useStore((s) => s.searchQuery)
  const searchMode = useStore((s) => s.searchMode)
  const searchFilters = useStore((s) => s.searchFilters)
  const setSearchResults = useStore((s) => s.setSearchResults)

  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const runSearch = useCallback(
    async (query: string) => {
      if (!query.trim()) {
        setSearchResults([], false)
        return
      }
      setSearchResults([], true)
      try {
        const results = await search({
          text: query,
          mode: searchMode,
          dateFrom: searchFilters.dateFrom,
          dateTo: searchFilters.dateTo,
          speakerProfileId: searchFilters.speakerProfileId,
          topicTag: searchFilters.topicTag,
          limit: 50,
        })
        setSearchResults(results, false)
      } catch (e) {
        console.error('Search failed', e)
        setSearchResults([], false)
      }
    },
    [searchMode, searchFilters, setSearchResults]
  )

  useEffect(() => {
    if (timerRef.current) clearTimeout(timerRef.current)
    timerRef.current = setTimeout(() => runSearch(searchQuery), DEBOUNCE_MS)
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current)
    }
  }, [searchQuery, runSearch])
}
