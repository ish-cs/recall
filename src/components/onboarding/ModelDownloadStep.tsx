import { useState } from 'react'
import { setSetting } from '../../api/tauri'

interface ModelDownloadStepProps {
  onComplete: () => void
}

export function ModelDownloadStep({ onComplete }: ModelDownloadStepProps) {
  const [skipped, setSkipped] = useState(false)

  async function handleSkip() {
    setSkipped(true)
    // Models will be downloaded on first use
    await setSetting('onboarding_complete', 'true').catch(() => {})
    onComplete()
  }

  return (
    <div className="flex flex-col items-center justify-center h-full p-8 max-w-md mx-auto text-center">
      <h2 className="text-2xl font-bold mb-4">Speech Models</h2>
      <p className="text-gray-600 mb-4 text-sm leading-relaxed">
        Recall uses a local speech recognition model (~1.5 GB) to transcribe audio.
        The model will be downloaded the first time you start recording.
      </p>
      <p className="text-gray-500 text-xs mb-8">
        You need an internet connection for the first download. After that, everything works offline.
      </p>
      <button
        onClick={handleSkip}
        disabled={skipped}
        className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium disabled:opacity-50"
      >
        {skipped ? 'Setting up…' : 'Continue'}
      </button>
    </div>
  )
}
