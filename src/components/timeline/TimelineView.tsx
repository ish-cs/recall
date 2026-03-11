import { useRef, useState } from 'react'
import { useVirtualizer } from '@tanstack/react-virtual'
import { useStore } from '../../store'
import { ConversationCard } from './ConversationCard'
import { ConversationDetail } from './ConversationDetail'

export function TimelineView() {
  const conversations = useStore((s) => s.conversations)
  const selectedId = useStore((s) => s.selectedConversationId)
  const setSelected = useStore((s) => s.setSelectedConversation)

  const [detailId, setDetailId] = useState<string | null>(null)

  const parentRef = useRef<HTMLDivElement>(null)

  const rowVirtualizer = useVirtualizer({
    count: conversations.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 100,
    overscan: 5,
  })

  function openDetail(id: string) {
    setDetailId(id)
    setSelected(id, null)
  }

  function closeDetail() {
    setDetailId(null)
    setSelected(null, null)
  }

  if (conversations.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-sm text-gray-500">
        No conversations yet. Start recording to begin.
      </div>
    )
  }

  return (
    <div className="flex h-full">
      {/* Conversation list */}
      <div
        ref={parentRef}
        className="w-72 border-r overflow-y-auto shrink-0"
        style={{ contain: 'strict', height: '100%' }}
      >
        <div
          style={{
            height: `${rowVirtualizer.getTotalSize()}px`,
            width: '100%',
            position: 'relative',
          }}
        >
          {rowVirtualizer.getVirtualItems().map((virtualRow) => {
            const conv = conversations[virtualRow.index]
            return (
              <div
                key={conv.id}
                style={{
                  position: 'absolute',
                  top: 0,
                  left: 0,
                  width: '100%',
                  height: `${virtualRow.size}px`,
                  transform: `translateY(${virtualRow.start}px)`,
                }}
              >
                <ConversationCard
                  conversation={conv}
                  selected={conv.id === selectedId}
                  onClick={() => openDetail(conv.id)}
                />
              </div>
            )
          })}
        </div>
      </div>

      {/* Detail panel */}
      <div className="flex-1 overflow-hidden">
        {detailId ? (
          <ConversationDetail conversationId={detailId} onClose={closeDetail} />
        ) : (
          <div className="flex items-center justify-center h-full text-sm text-gray-400">
            Select a conversation
          </div>
        )}
      </div>
    </div>
  )
}
