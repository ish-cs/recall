export interface ConversationSummary {
  id: string
  startedAt: number       // Unix ms
  endedAt: number | null
  title: string | null
  summary: string | null
  topicTags: string[]
  segmentCount: number
  speakerCount: number
}

export interface TranscriptSegment {
  id: string
  conversationId: string
  speakerInstanceId: string | null
  startedAt: number
  endedAt: number
  text: string
  confidence: number | null
}

export interface SpeakerInstance {
  id: string
  conversationId: string
  diarizationLabel: string
  speakerProfileId: string | null
  speakerDisplayName: string | null
  confidence: number | null
  segmentCount: number
}

export interface ConversationDetail extends ConversationSummary {
  segments: TranscriptSegment[]
  speakers: SpeakerInstance[]
}

export interface SpeakerProfile {
  id: string
  displayName: string | null
  isUser: boolean
  segmentCount: number
  conversationCount: number
  createdAt: number
  updatedAt: number
}

export interface SearchResult {
  segmentId: string
  conversationId: string
  conversationStartedAt: number
  text: string
  startedAt: number
  speakerDisplayName: string | null
  matchType: 'keyword' | 'semantic' | 'hybrid'
  score: number
}

export interface StorageUsage {
  audioBytes: number
  transcriptDbBytes: number
  modelsBytes: number
}

export interface RecordingStatus {
  recording: boolean
  paused: boolean
  currentConversationId: string | null
}

export type SearchMode = 'keyword' | 'semantic' | 'hybrid'

export interface SearchQuery {
  text: string
  mode: SearchMode
  speakerProfileId?: string
  dateFrom?: number
  dateTo?: number
  topicTag?: string
  limit?: number
}

export interface DeletionSummary {
  conversationsDeleted: number
  segmentsDeleted: number
  audioFilesDeleted: number
  bytesFreed: number
}

export type DeleteScope = 'Audio' | 'Transcripts' | 'Both'

export interface SpeakerMatchSuggestion {
  speakerInstanceId: string
  speakerProfileId: string
  confidence: number
  displayName: string | null
}
