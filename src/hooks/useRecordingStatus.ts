import { useEffect, useRef } from 'react'
import { useStore } from '../store'
import { useTauriEvent } from './useTauriEvents'
import { getRecordingStatus } from '../api/tauri'

interface PipelineStatusEvent {
  type: string
  recording: boolean
  paused: boolean
  hot_queue_depth: number
  cold_queue_depth: number
}

// Check if Tauri API is available
function isTauriAvailable(): boolean {
  return typeof window !== 'undefined' && '__TAURI__' in window
}

/**
 * Subscribes to pipeline status events and syncs recording state to the store.
 * Also polls status on mount.
 */
export function useRecordingStatus() {
  const setRecordingState = useStore((s) => s.setRecordingState)
  const loadedRef = useRef(false)

  // Poll status on mount
  useEffect(() => {
    if (loadedRef.current) return
    loadedRef.current = true

    if (!isTauriAvailable()) return

    // Delay slightly to ensure Tauri is ready
    const timer = setTimeout(() => {
      getRecordingStatus()
        .then((status) => {
          setRecordingState(status.recording, status.paused, status.currentConversationId)
        })
        .catch(() => {
          // Worker may not be ready yet
        })
    }, 100)

    return () => clearTimeout(timer)
  }, [setRecordingState])

  // Listen for heartbeat events
  useTauriEvent<PipelineStatusEvent>('pipeline:status', (event) => {
    setRecordingState(event.recording, event.paused, null)
  })
}
