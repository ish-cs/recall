import { invoke } from '@tauri-apps/api/core'
import type {
  ConversationSummary,
  ConversationDetail,
  SpeakerProfile,
  SearchResult,
  SearchQuery,
  RecordingStatus,
  StorageUsage,
  DeletionSummary,
  DeleteScope,
} from './types'

// ── Recording ──────────────────────────────────────────────────

export const startRecording = () => invoke<void>('start_recording')
export const stopRecording = () => invoke<void>('stop_recording')
export const pauseRecording = () => invoke<void>('pause_recording')
export const resumeRecording = () => invoke<void>('resume_recording')
export const getRecordingStatus = () => invoke<RecordingStatus>('get_recording_status')

// ── Conversations ──────────────────────────────────────────────

export const listConversations = (
  limit: number,
  offset: number,
  dateFrom?: number,
  dateTo?: number,
) =>
  invoke<ConversationSummary[]>('list_conversations', {
    limit,
    offset,
    dateFrom: dateFrom ?? null,
    dateTo: dateTo ?? null,
  })

export const getConversation = (id: string) =>
  invoke<ConversationDetail>('get_conversation', { id })

export const deleteConversation = (id: string, deleteAudio: boolean) =>
  invoke<void>('delete_conversation', { id, deleteAudio })

export const splitConversation = (id: string, atSegmentId: string) =>
  invoke<string>('split_conversation', { id, atSegmentId })

// ── Search ────────────────────────────────────────────────────

export const search = (query: SearchQuery) =>
  invoke<SearchResult[]>('search', { query })

// ── Speakers ─────────────────────────────────────────────────

export const listSpeakerProfiles = () =>
  invoke<SpeakerProfile[]>('list_speaker_profiles')

export const renameSpeakerProfile = (id: string, displayName: string) =>
  invoke<void>('rename_speaker_profile', { id, displayName })

export const mergeSpeakerProfiles = (fromId: string, toId: string) =>
  invoke<void>('merge_speaker_profiles', { fromId, toId })

export const deleteSpeakerProfile = (id: string) =>
  invoke<void>('delete_speaker_profile', { id })

// ── Settings ─────────────────────────────────────────────────

export const getSetting = (key: string) =>
  invoke<string | null>('get_setting', { key })

export const setSetting = (key: string, value: string) =>
  invoke<void>('set_setting', { key, value })

// ── Storage ──────────────────────────────────────────────────

export const getStorageUsage = () =>
  invoke<StorageUsage>('get_storage_usage')

export const deleteDataByAge = (
  olderThanDays: number,
  scope: DeleteScope,
) =>
  invoke<DeletionSummary>('delete_data_by_age', { olderThanDays, scope })

export const exportTranscripts = (outputPath: string) =>
  invoke<void>('export_transcripts', { outputPath })

export const deleteAllData = () =>
  invoke<void>('delete_all_data')
