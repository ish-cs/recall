import { useEffect, useState } from 'react'
import { useStore } from './store'
import { useRecordingStatus } from './hooks/useRecordingStatus'
import { useConversations } from './hooks/useConversations'
import { useTauriEvent } from './hooks/useTauriEvents'
import { getSetting } from './api/tauri'
import { AppShell } from './components/layout/AppShell'
import { OnboardingFlow } from './components/onboarding/OnboardingFlow'
import { TimelineView } from './components/timeline/TimelineView'
import { SearchView } from './components/search/SearchView'
import { SpeakersView } from './components/speakers/SpeakersView'
import { SettingsView } from './components/settings/SettingsView'

function MainContent() {
  const activeView = useStore((s) => s.activeView)
  return (
    <>
      {activeView === 'timeline' && <TimelineView />}
      {activeView === 'search' && <SearchView />}
      {activeView === 'speakers' && <SpeakersView />}
      {activeView === 'settings' && <SettingsView />}
    </>
  )
}

function App() {
  const [onboardingDone, setOnboardingDone] = useState<boolean | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [tauriReady, setTauriReady] = useState(false)

  const prependConversation = useStore((s) => s.prependConversation)
  const updateConversation = useStore((s) => s.updateConversation)

  useRecordingStatus()
  useConversations()

  // Check if Tauri is available
  useEffect(() => {
    import('@tauri-apps/api/core').then(() => {
      console.log('Tauri API loaded')
      setTauriReady(true)
    }).catch((e) => {
      console.error('Tauri API not available:', e)
      setLoadError('Tauri API not available - running in browser mode')
      // Fallback: assume onboarding not done
      setOnboardingDone(false)
    })
  }, [])

  // Check onboarding status on mount
  useEffect(() => {
    if (!tauriReady) return

    // Check if Tauri is actually available in window
    if (!('__TAURI__' in window)) {
      setOnboardingDone(false)
      return
    }

    getSetting('onboarding_complete')
      .then((val) => {
        console.log('Onboarding setting:', val)
        // val is null if not set yet, treat as not done
        setOnboardingDone(val === 'true')
      })
      .catch((e) => {
        console.error('Failed to get onboarding setting:', e)
        setLoadError(e?.toString() || 'Unknown error')
        setOnboardingDone(false)
      })
  }, [tauriReady])

  useTauriEvent<{ type: string; conversation_id: string; started_at: number }>(
    'conversation:started',
    (event) => {
      prependConversation({
        id: event.conversation_id,
        startedAt: event.started_at,
        endedAt: null,
        title: null,
        summary: null,
        topicTags: [],
        segmentCount: 0,
        speakerCount: 0,
      })
    }
  )

  useTauriEvent<{ type: string; conversation_id: string; ended_at: number }>(
    'conversation:ended',
    (event) => {
      updateConversation(event.conversation_id, { endedAt: event.ended_at })
    }
  )

  useTauriEvent<{ type: string; conversation_id: string; summary: string; tags: string[] }>(
    'enrichment:complete',
    (event) => {
      updateConversation(event.conversation_id, {
        summary: event.summary,
        topicTags: event.tags,
      })
    }
  )

  const addSpeakerSuggestion = useStore((s) => s.addSpeakerSuggestion)
  useTauriEvent<{ type: string; segment_id: string; conversation_id: string; speaker_profile_id: string; display_name: string | null; confidence: number }>(
    'speaker:match_suggestion',
    (event) => {
      addSpeakerSuggestion({
        speakerInstanceId: event.segment_id,
        speakerProfileId: event.speaker_profile_id,
        confidence: event.confidence,
        displayName: event.display_name,
      })
    }
  )

  if (onboardingDone === null) return (
    <div className="flex flex-col items-center justify-center h-screen gap-4">
      <div className="text-gray-500">Loading...</div>
      {loadError && <div className="text-red-500 text-sm px-4">{loadError}</div>}
    </div>
  )

  if (!onboardingDone) {
    return (
      <div className="h-screen">
        {loadError && (
          <div className="bg-yellow-100 border-l-4 border-yellow-500 text-yellow-700 p-2 text-sm">
            Note: {loadError}
          </div>
        )}
        <OnboardingFlow onComplete={() => setOnboardingDone(true)} />
      </div>
    )
  }

  return (
    <AppShell>
      <MainContent />
    </AppShell>
  )
}

export default App
