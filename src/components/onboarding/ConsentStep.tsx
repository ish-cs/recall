interface ConsentStepProps {
  onAccept: () => void
}

export function ConsentStep({ onAccept }: ConsentStepProps) {
  return (
    <div className="flex flex-col items-center justify-center h-full p-8 max-w-md mx-auto text-center">
      <h2 className="text-2xl font-bold mb-4">Welcome to Recall</h2>
      <p className="text-gray-600 mb-6 text-sm leading-relaxed">
        Recall captures and transcribes audio from your microphone to help you
        recall conversations. All processing happens locally on your device —
        no audio or transcripts are sent to any server.
      </p>
      <ul className="text-left text-sm text-gray-600 mb-8 space-y-2">
        <li>✓ Audio is processed entirely on-device</li>
        <li>✓ Transcripts are stored in an encrypted local database</li>
        <li>✓ You can delete all data at any time from Settings</li>
        <li>✓ No account required</li>
      </ul>
      <button
        onClick={onAccept}
        className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium"
      >
        I understand — Get Started
      </button>
    </div>
  )
}
