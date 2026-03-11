import type { ConversationDetail } from '../../api/types'
import { SpeakerTurn } from './SpeakerTurn'

interface TranscriptViewProps {
  conversation: ConversationDetail
}

export function TranscriptView({ conversation }: TranscriptViewProps) {
  // Build stable speaker → color index map
  const speakerColorMap = new Map<string, number>()
  conversation.speakers.forEach((sp, i) => {
    speakerColorMap.set(sp.id, i)
  })

  if (conversation.segments.length === 0) {
    return (
      <div className="p-6 text-sm text-gray-500">No transcript segments yet.</div>
    )
  }

  return (
    <div className="divide-y divide-gray-100">
      {conversation.segments.map((seg) => {
        const colorIndex = seg.speakerInstanceId != null
          ? (speakerColorMap.get(seg.speakerInstanceId) ?? 0)
          : 0
        return (
          <SpeakerTurn
            key={seg.id}
            segment={seg}
            speakers={conversation.speakers}
            colorIndex={colorIndex}
          />
        )
      })}
    </div>
  )
}
