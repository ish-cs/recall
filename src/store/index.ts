import { create } from 'zustand'
import type {
  ConversationSummary,
  ConversationDetail,
  SearchResult,
  SpeakerMatchSuggestion,
  SearchMode,
} from '../api/types'

interface SearchFilters {
  dateFrom?: number
  dateTo?: number
  speakerProfileId?: string
  topicTag?: string
}

export type ActiveView = 'timeline' | 'search' | 'speakers' | 'settings'

interface AppStore {
  // Recording state
  recording: boolean
  paused: boolean
  currentConversationId: string | null

  // Conversations
  conversations: ConversationSummary[]
  selectedConversationId: string | null
  selectedConversationDetail: ConversationDetail | null

  // Search
  searchQuery: string
  searchMode: SearchMode
  searchFilters: SearchFilters
  searchResults: SearchResult[]
  searchLoading: boolean

  // Active view
  activeView: ActiveView

  // Speaker match suggestions
  pendingSpeakerSuggestions: SpeakerMatchSuggestion[]

  // Actions
  setRecordingState: (recording: boolean, paused: boolean, conversationId: string | null) => void
  setConversations: (convs: ConversationSummary[]) => void
  prependConversation: (conv: ConversationSummary) => void
  updateConversation: (id: string, updates: Partial<ConversationSummary>) => void
  removeConversation: (id: string) => void
  setSelectedConversation: (id: string | null, detail: ConversationDetail | null) => void
  updateSelectedSegmentSpeaker: (segmentId: string, speakerInstanceId: string, speakerDisplayName: string | null) => void
  appendSegmentToDetail: (segment: import('../api/types').TranscriptSegment) => void
  setSearchQuery: (q: string) => void
  setSearchMode: (m: SearchMode) => void
  setSearchFilters: (f: SearchFilters) => void
  setSearchResults: (r: SearchResult[], loading: boolean) => void
  setActiveView: (v: ActiveView) => void
  addSpeakerSuggestion: (s: SpeakerMatchSuggestion) => void
  removeSpeakerSuggestion: (speakerInstanceId: string) => void
}

export const useStore = create<AppStore>((set) => ({
  recording: false,
  paused: false,
  currentConversationId: null,

  conversations: [],
  selectedConversationId: null,
  selectedConversationDetail: null,

  searchQuery: '',
  searchMode: 'keyword',
  searchFilters: {},
  searchResults: [],
  searchLoading: false,

  activeView: 'timeline',

  pendingSpeakerSuggestions: [],

  setRecordingState: (recording, paused, conversationId) =>
    set({ recording, paused, currentConversationId: conversationId }),

  setConversations: (conversations) => set({ conversations }),

  prependConversation: (conv) =>
    set((state) => ({ conversations: [conv, ...state.conversations] })),

  updateConversation: (id, updates) =>
    set((state) => ({
      conversations: state.conversations.map((c) =>
        c.id === id ? { ...c, ...updates } : c
      ),
    })),

  removeConversation: (id) =>
    set((state) => ({
      conversations: state.conversations.filter((c) => c.id !== id),
    })),

  setSelectedConversation: (id, detail) =>
    set({ selectedConversationId: id, selectedConversationDetail: detail }),

  updateSelectedSegmentSpeaker: (segmentId, speakerInstanceId, speakerDisplayName) =>
    set((state) => {
      if (!state.selectedConversationDetail) return {}
      return {
        selectedConversationDetail: {
          ...state.selectedConversationDetail,
          segments: state.selectedConversationDetail.segments.map((s) =>
            s.id === segmentId ? { ...s, speakerInstanceId } : s
          ),
          speakers: state.selectedConversationDetail.speakers.map((sp) =>
            sp.id === speakerInstanceId
              ? { ...sp, speakerDisplayName }
              : sp
          ),
        },
      }
    }),

  appendSegmentToDetail: (segment) =>
    set((state) => {
      if (!state.selectedConversationDetail) return {}
      return {
        selectedConversationDetail: {
          ...state.selectedConversationDetail,
          segments: [...state.selectedConversationDetail.segments, segment],
          segmentCount: state.selectedConversationDetail.segmentCount + 1,
        },
      }
    }),

  setSearchQuery: (searchQuery) => set({ searchQuery }),
  setSearchMode: (searchMode) => set({ searchMode }),
  setSearchFilters: (searchFilters) => set({ searchFilters }),
  setSearchResults: (searchResults, searchLoading) => set({ searchResults, searchLoading }),
  setActiveView: (activeView) => set({ activeView }),

  addSpeakerSuggestion: (s) =>
    set((state) => ({
      pendingSpeakerSuggestions: [...state.pendingSpeakerSuggestions, s],
    })),

  removeSpeakerSuggestion: (speakerInstanceId) =>
    set((state) => ({
      pendingSpeakerSuggestions: state.pendingSpeakerSuggestions.filter(
        (s) => s.speakerInstanceId !== speakerInstanceId
      ),
    })),
}))
