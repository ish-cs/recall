import { useCallback, useEffect, useRef } from 'react'
import { useStore } from '../store'
import { listConversations } from '../api/tauri'

// Check if Tauri API is available
function isTauriAvailable(): boolean {
  return typeof window !== 'undefined' && '__TAURI__' in window
}

export function useConversations() {
  const setConversations = useStore((s) => s.setConversations)
  const prependConversation = useStore((s) => s.prependConversation)
  const updateConversation = useStore((s) => s.updateConversation)
  const loadedRef = useRef(false)

  const load = useCallback(async (limit = 50, offset = 0) => {
    if (!isTauriAvailable()) return
    try {
      const convs = await listConversations(limit, offset)
      setConversations(convs)
    } catch (e) {
      console.error('Failed to load conversations', e)
    }
  }, [setConversations])

  useEffect(() => {
    if (loadedRef.current) return
    loadedRef.current = true
    // Delay slightly to ensure Tauri is ready
    const timer = setTimeout(load, 100)
    return () => clearTimeout(timer)
  }, [load])

  return { load, prependConversation, updateConversation }
}
