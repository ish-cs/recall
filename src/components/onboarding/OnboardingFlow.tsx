import { useState } from 'react'
import { setSetting } from '../../api/tauri'
import { ConsentStep } from './ConsentStep'
import { ModelDownloadStep } from './ModelDownloadStep'

interface OnboardingFlowProps {
  onComplete: () => void
}

type Step = 'consent' | 'models'

export function OnboardingFlow({ onComplete }: OnboardingFlowProps) {
  const [step, setStep] = useState<Step>('consent')

  async function handleConsent() {
    await setSetting('consent_given', 'true').catch(() => {})
    setStep('models')
  }

  return (
    <div className="flex flex-col h-screen bg-gray-50">
      <div className="flex-1 overflow-y-auto">
        {step === 'consent' && <ConsentStep onAccept={handleConsent} />}
        {step === 'models' && <ModelDownloadStep onComplete={onComplete} />}
      </div>
      <div className="h-1 bg-gray-200">
        <div
          className="h-1 bg-blue-500 transition-all"
          style={{ width: step === 'consent' ? '50%' : '100%' }}
        />
      </div>
    </div>
  )
}
