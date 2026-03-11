import type { TranscriptSegment, SpeakerInstance } from '../../api/types'
import { TimestampLabel } from './TimestampLabel'

// Stable color palette for speaker labels
const SPEAKER_COLORS = [
  'bg-blue-100 text-blue-700',
  'bg-green-100 text-green-700',
  'bg-purple-100 text-purple-700',
  'bg-orange-100 text-orange-700',
  'bg-pink-100 text-pink-700',
  'bg-teal-100 text-teal-700',
]

interface SpeakerTurnProps {
  segment: TranscriptSegment
  speakers: SpeakerInstance[]
  colorIndex: number
}

export function SpeakerTurn({ segment, speakers, colorIndex }: SpeakerTurnProps) {
  const speaker = speakers.find((s) => s.id === segment.speakerInstanceId)
  const label = speaker?.speakerDisplayName ?? speaker?.diarizationLabel ?? 'Unknown'
  const colorClass = SPEAKER_COLORS[colorIndex % SPEAKER_COLORS.length]

  return (
    <div className="flex gap-3 py-2">
      <div className="flex flex-col items-end gap-1 w-28 shrink-0">
        <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${colorClass}`}>
          {label}
        </span>
        <TimestampLabel ms={segment.startedAt} />
      </div>
      <p className="flex-1 text-sm text-gray-800 leading-relaxed pt-0.5">{segment.text}</p>
    </div>
  )
}
