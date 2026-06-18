import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'
import type { ChatMessage } from '@/lib/types'

export const MAX_CONTEXT_FILES = 5

let _idCounter = 0
function genId() {
  return `msg-${++_idCounter}-${Date.now()}`
}

export interface ChatSession {
  repoKey: string
  messages: ChatMessage[]
  selectedFiles: string[]
  savedAt?: string
}

interface ChatState {
  sessions: Record<string, ChatSession>
  activeRepoKey: string | null
  isConnected: boolean
  isLoading: boolean
  statusMessage: string | null

  initSession: (repoKey: string) => void
  getSession: (repoKey: string) => ChatSession

  addContextFile: (repoKey: string, path: string) => void
  removeContextFile: (repoKey: string, path: string) => void
  clearContextFiles: (repoKey: string) => void

  addUserMessage: (repoKey: string, content: string, contextFiles?: string[]) => void
  startAssistantMessage: (repoKey: string) => string
  appendToken: (repoKey: string, id: string, token: string) => void
  finalizeMessage: (repoKey: string, id: string) => void
  clearMessages: (repoKey: string) => void

  setConnected: (v: boolean) => void
  setLoading: (v: boolean) => void
  setStatusMessage: (msg: string | null) => void
  setActiveRepo: (repoKey: string) => void
}

function defaultSession(repoKey: string): ChatSession {
  return { repoKey, messages: [], selectedFiles: [] }
}

export const useChatStore = create<ChatState>()(
  persist(
    (set, get) => ({
      sessions: {},
      activeRepoKey: null,
      isConnected: false,
      isLoading: false,
      statusMessage: null,

      initSession: (repoKey) =>
        set((s) => ({
          sessions: s.sessions[repoKey]
            ? s.sessions
            : { ...s.sessions, [repoKey]: defaultSession(repoKey) },
          activeRepoKey: repoKey,
        })),

      getSession: (repoKey) =>
        get().sessions[repoKey] ?? defaultSession(repoKey),

      addContextFile: (repoKey, path) =>
        set((s) => {
          const session = s.sessions[repoKey] ?? defaultSession(repoKey)
          if (session.selectedFiles.includes(path) || session.selectedFiles.length >= MAX_CONTEXT_FILES)
            return {}
          return {
            sessions: {
              ...s.sessions,
              [repoKey]: { ...session, selectedFiles: [...session.selectedFiles, path] },
            },
          }
        }),

      removeContextFile: (repoKey, path) =>
        set((s) => {
          const session = s.sessions[repoKey] ?? defaultSession(repoKey)
          return {
            sessions: {
              ...s.sessions,
              [repoKey]: {
                ...session,
                selectedFiles: session.selectedFiles.filter((f) => f !== path),
              },
            },
          }
        }),

      clearContextFiles: (repoKey) =>
        set((s) => {
          const session = s.sessions[repoKey] ?? defaultSession(repoKey)
          return {
            sessions: { ...s.sessions, [repoKey]: { ...session, selectedFiles: [] } },
          }
        }),

      addUserMessage: (repoKey, content, contextFiles = []) =>
        set((s) => {
          const session = s.sessions[repoKey] ?? defaultSession(repoKey)
          const now = new Date().toISOString()
          return {
            sessions: {
              ...s.sessions,
              [repoKey]: {
                ...session,
                savedAt: now,
                selectedFiles: [],   // clear staged files after send
                messages: [
                  ...session.messages,
                  {
                    id: genId(),
                    role: 'user' as const,
                    content,
                    timestamp: now,
                    isStreaming: false,
                    contextFiles: contextFiles.length > 0 ? contextFiles : undefined,
                  },
                ],
              },
            },
          }
        }),

      startAssistantMessage: (repoKey) => {
        const id = genId()
        set((s) => {
          const session = s.sessions[repoKey] ?? defaultSession(repoKey)
          return {
            sessions: {
              ...s.sessions,
              [repoKey]: {
                ...session,
                savedAt: new Date().toISOString(),
                messages: [
                  ...session.messages,
                  {
                    id,
                    role: 'assistant' as const,
                    content: '',
                    timestamp: new Date().toISOString(),
                    isStreaming: true,
                  },
                ],
              },
            },
          }
        })
        return id
      },

      appendToken: (repoKey, id, token) =>
        set((s) => {
          const session = s.sessions[repoKey] ?? defaultSession(repoKey)
          return {
            sessions: {
              ...s.sessions,
              [repoKey]: {
                ...session,
                messages: session.messages.map((m) =>
                  m.id === id ? { ...m, content: m.content + token } : m
                ),
              },
            },
          }
        }),

      finalizeMessage: (repoKey, id) =>
        set((s) => {
          const session = s.sessions[repoKey] ?? defaultSession(repoKey)
          return {
            isLoading: false,
            sessions: {
              ...s.sessions,
              [repoKey]: {
                ...session,
                savedAt: new Date().toISOString(),
                messages: session.messages.map((m) =>
                  m.id === id ? { ...m, isStreaming: false } : m
                ),
              },
            },
          }
        }),

      clearMessages: (repoKey) =>
        set((s) => ({
          sessions: {
            ...s.sessions,
            [repoKey]: { repoKey, messages: [], selectedFiles: [], savedAt: undefined },
          },
        })),

      setConnected: (v) => set({ isConnected: v }),
      setLoading: (v) => set({ isLoading: v }),
      setStatusMessage: (msg) => set({ statusMessage: msg }),
      setActiveRepo: (repoKey) => set({ activeRepoKey: repoKey }),
    }),
    {
      name: 'repolens-chat-v3',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({ sessions: state.sessions }),
    }
  )
)