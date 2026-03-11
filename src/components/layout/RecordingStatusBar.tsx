import { useStore } from '../../store'
import { startRecording, stopRecording, pauseRecording, resumeRecording } from '../../api/tauri'

// Check if Tauri API is available
function isTauriAvailable(): boolean {
  return typeof window !== 'undefined' && '__TAURI__' in window
}

export function RecordingStatusBar() {
  const recording = useStore((s) => s.recording)
  const paused = useStore((s) => s.paused)

  const indicator = recording
    ? paused
      ? '🟡 Paused'
      : '🔴 Recording'
    : '⚫ Off'

  async function handleStart() {
    if (!isTauriAvailable()) return
    try { await startRecording() } catch (e) { console.error(e) }
  }
  async function handleStop() {
    if (!isTauriAvailable()) return
    try { await stopRecording() } catch (e) { console.error(e) }
  }
  async function handlePauseResume() {
    if (!isTauriAvailable()) return
    try {
      if (paused) await resumeRecording()
      else await pauseRecording()
    } catch (e) { console.error(e) }
  }

  return (
    <footer className="h-9 bg-white border-t flex items-center px-4 gap-3 text-xs text-gray-600 shrink-0">
      <span className="min-w-20">{indicator}</span>
      <div className="flex gap-2 ml-auto">
        {!recording && (
          <button
            onClick={handleStart}
            className="px-2 py-1 rounded bg-red-500 text-white hover:bg-red-600"
          >
            Start
          </button>
        )}
        {recording && (
          <>
            <button
              onClick={handlePauseResume}
              className="px-2 py-1 rounded bg-yellow-500 text-white hover:bg-yellow-600"
            >
              {paused ? 'Resume' : 'Pause'}
            </button>
            <button
              onClick={handleStop}
              className="px-2 py-1 rounded bg-gray-500 text-white hover:bg-gray-600"
            >
              Stop
            </button>
          </>
        )}
      </div>
    </footer>
  )
}
