import { useEffect } from 'react'
import { listen, UnlistenFn } from '@tauri-apps/api/event'

// Check if Tauri API is available
function isTauriAvailable(): boolean {
  return typeof window !== 'undefined' && '__TAURI__' in window
}

/**
 * Generic Tauri event listener. Returns unsubscribe function automatically on unmount.
 */
export function useTauriEvent<T>(
  eventName: string,
  handler: (payload: T) => void,
  deps: unknown[] = []
) {
  useEffect(() => {
    if (!isTauriAvailable()) return

    let unlisten: UnlistenFn | undefined

    listen<T>(eventName, (event) => {
      handler(event.payload)
    }).then((fn) => {
      unlisten = fn
    })

    return () => {
      unlisten?.()
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)
}
