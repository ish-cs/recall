import { useEffect, useState } from 'react'
import { listSpeakerProfiles, renameSpeakerProfile, mergeSpeakerProfiles, deleteSpeakerProfile } from '../../api/tauri'
import type { SpeakerProfile } from '../../api/types'
import { SpeakerCard } from './SpeakerCard'
import { RenameDialog } from './RenameDialog'

function isTauriAvailable(): boolean {
  return typeof window !== 'undefined' && '__TAURI__' in window
}

export function SpeakersView() {
  const [speakers, setSpeakers] = useState<SpeakerProfile[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [renameTarget, setRenameTarget] = useState<SpeakerProfile | null>(null)

  function load() {
    if (!isTauriAvailable()) {
      setLoading(false)
      return
    }
    setLoading(true)
    listSpeakerProfiles()
      .then(setSpeakers)
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  async function handleRename(id: string, name: string) {
    if (!isTauriAvailable()) return
    await renameSpeakerProfile(id, name)
    setRenameTarget(null)
    load()
  }

  async function handleMerge(fromId: string, toId: string) {
    if (!isTauriAvailable()) return
    await mergeSpeakerProfiles(fromId, toId)
    load()
  }

  async function handleDelete(id: string) {
    if (!isTauriAvailable()) return
    if (!confirm('Delete this speaker profile?')) return
    await deleteSpeakerProfile(id)
    load()
  }

  if (loading) return <div className="p-6 text-sm text-gray-500">Loading…</div>
  if (error) return <div className="p-6 text-sm text-red-500">{error}</div>

  if (speakers.length === 0) {
    return (
      <div className="p-6 text-sm text-gray-500">
        No speakers yet. Speakers will appear after recording conversations with diarization enabled.
      </div>
    )
  }

  return (
    <div className="p-4">
      <h2 className="text-lg font-semibold mb-4">Speakers</h2>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {speakers.map((sp) => (
          <SpeakerCard
            key={sp.id}
            speaker={sp}
            onRename={() => setRenameTarget(sp)}
            onMerge={() => {
              const other = speakers.find((o) => o.id !== sp.id)
              if (other && confirm(`Merge "${sp.displayName || 'this speaker'}" into "${other.displayName || 'other speaker'}"?`)) {
                handleMerge(sp.id, other.id)
              }
            }}
            onDelete={() => handleDelete(sp.id)}
          />
        ))}
      </div>
      {renameTarget && (
        <RenameDialog
          currentName={renameTarget.displayName}
          onConfirm={(name) => handleRename(renameTarget.id, name)}
          onCancel={() => setRenameTarget(null)}
        />
      )}
    </div>
  )
}
