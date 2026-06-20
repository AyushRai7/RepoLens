import { useEffect, useRef, useCallback } from 'react'
import { useChatStore } from '@/store/chatStore'

// ── Types ──────────────────────────────────────────────────────────────────────

interface PendingMessage {
  content: string
  selectedFiles: string[]
  assistantMsgId: string
}

interface WsEntry {
  ws: WebSocket
  owner: string
  name: string
  refCount: number
  reconnectTimer: ReturnType<typeof setTimeout> | null
  reconnectDelay: number
  dead: boolean
  pendingQueue: PendingMessage[]
  backendReady: boolean
  streamingId: string | null
}


const wsRegistry: Record<string, WsEntry> = {}

function repoKey(owner: string, name: string) {
  return `${owner}/${name}`
}

function getWsUrl(owner: string, name: string) {
  const base = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000')
    .replace(/^http/, 'ws')
  // Always include /api prefix — matches FastAPI router mount
  return `${base}/api/chat/ws/${owner}/${name}`
}

// ── Hook ───────────────────────────────────────────────────────────────────────

export function useChat(owner: string, name: string) {
  const key = repoKey(owner, name)
  const mountedRef = useRef(true)

  const {
    initSession,
    startAssistantMessage,
    appendToken,
    finalizeMessage,
    setConnected,
    setLoading,
    setStatusMessage,
    setActiveRepo,
    addUserMessage,
    clearMessages,
    getSession,
  } = useChatStore()

  const startMsgRef = useRef(startAssistantMessage)
  useEffect(() => { startMsgRef.current = startAssistantMessage }, [startAssistantMessage])

  useEffect(() => {
    initSession(key)
    setActiveRepo(key)
  }, [key]) 


  useEffect(() => {
    mountedRef.current = true

    const existing = wsRegistry[key]
    if (existing && !existing.dead && existing.ws.readyState <= WebSocket.OPEN) {
      existing.refCount++
      return () => {
        mountedRef.current = false
        if (wsRegistry[key]) wsRegistry[key].refCount--
      }
    }

    function connect(delay = 0) {
      const entry: WsEntry = wsRegistry[key] ?? {
        ws: null as unknown as WebSocket,
        owner,
        name,
        refCount: 1,
        reconnectTimer: null,
        reconnectDelay: 1000,
        dead: false,
        pendingQueue: [],
        backendReady: false,
        streamingId: null,
      }
      wsRegistry[key] = entry

      if (delay > 0) {
        entry.reconnectTimer = setTimeout(doConnect, delay)
      } else {
        doConnect()
      }
    }

    function doConnect() {
      const url = getWsUrl(owner, name);
      console.log("Opening WebSocket:", url);

      const entry = wsRegistry[key]
      if (!entry || entry.dead) return

      entry.backendReady = false
      const ws = new WebSocket(getWsUrl(owner, name))
      entry.ws = ws

      ws.onopen = () => {
        entry.reconnectDelay = 1000
        setStatusMessage('Connecting to AI agent…')
      }

      ws.onmessage = (event) => {
        let msg: { type: string; content: string; analysed_at?: string }
        try { msg = JSON.parse(event.data) } catch { return }

        switch (msg.type) {

          case 'ready': {
            entry.backendReady = true
            setConnected(true)
            setLoading(false)
            setStatusMessage(null)

            // Clear stale localStorage history if repo was re-analysed
            const session = getSession(key)
            const analysedAt = msg.analysed_at
            if (analysedAt && session.savedAt) {
              if (new Date(analysedAt) > new Date(session.savedAt)) {
                clearMessages(key)
              }
            } else if (!session.savedAt && session.messages.length > 0) {
              clearMessages(key)
            }

            const queued = entry.pendingQueue.splice(0)
            for (const { content, selectedFiles, assistantMsgId } of queued) {
              entry.streamingId = assistantMsgId
              entry.ws.send(JSON.stringify({
                type: 'message',
                content,
                selected_files: selectedFiles,
              }))
            }
            break
          }

          case 'status':
            setStatusMessage(msg.content)
            break

          case 'token': {
            const sid = wsRegistry[key]?.streamingId
            if (sid) appendToken(key, sid, msg.content)
            break
          }

          case 'done': {
            const sid = wsRegistry[key]?.streamingId
            if (sid) {
              finalizeMessage(key, sid)
              if (wsRegistry[key]) wsRegistry[key].streamingId = null
            }
            setLoading(false)
            break
          }

          case 'error': {
            console.error('[Chat WS] server error:', msg.content)
            const sid = wsRegistry[key]?.streamingId
            if (sid) {
              finalizeMessage(key, sid)
              if (wsRegistry[key]) wsRegistry[key].streamingId = null
            }
            setLoading(false)
            setConnected(false)
            setStatusMessage(msg.content)
            break
          }
        }
      }

      ws.onclose = (event) => {
  console.log(
    "WS CLOSE",
    event.code,
    event.reason,
    event.wasClean
  );

  entry.backendReady = false;
  setConnected(false);
  setLoading(false);

  // Finalize any in-flight streaming message
  const sid = entry.streamingId;
  if (sid) {
    finalizeMessage(key, sid);
    entry.streamingId = null;
  }

  const registryEntry = wsRegistry[key];
  if (!registryEntry || registryEntry.dead) return;

  const delay = Math.min(registryEntry.reconnectDelay * 2, 8000);
  registryEntry.reconnectDelay = delay;
  setStatusMessage(`Reconnecting in ${Math.round(delay / 1000)}s…`);
  registryEntry.reconnectTimer = setTimeout(doConnect, delay);
};

      ws.onerror = (e) => {
  console.error("WS ERROR", e);
};
    }

    connect(0)

    return () => {
      mountedRef.current = false
      const entry = wsRegistry[key]
      if (entry) entry.refCount = Math.max(0, entry.refCount - 1)
    }
  }, [key]) 


  const sendMessage = useCallback(
    (content: string) => {
      const store = useChatStore.getState()

      // Guard: already loading OR messages already queued
      const entry = wsRegistry[key]
      if (store.isLoading || (entry?.pendingQueue.length ?? 0) > 0) return
      if (!entry || entry.dead) return

      const session = getSession(key)
      const selectedFiles = [...session.selectedFiles]

      // Optimistic UI update
      addUserMessage(key, content, selectedFiles)
      setLoading(true)

      // Create the assistant placeholder now so we have the id
      const assistantMsgId = startMsgRef.current(key)

      // Store on registry entry so all hook instances share it
      entry.streamingId = assistantMsgId

      if (entry.ws.readyState !== WebSocket.OPEN || !entry.backendReady) {
        // Queue — will be flushed with streamingId restored on 'ready'
        entry.pendingQueue.push({ content, selectedFiles, assistantMsgId })
        return
      }

      entry.ws.send(JSON.stringify({
        type: 'message',
        content,
        selected_files: selectedFiles,
      }))
    },
    [key, getSession, addUserMessage, setLoading]
  )

  const isConnected = useChatStore((s) => s.isConnected)
  const isLoading = useChatStore((s) => s.isLoading)
  const statusMessage = useChatStore((s) => s.statusMessage)

  return { sendMessage, isConnected, isLoading, statusMessage }
}

// ── Utility: hard-close a socket (e.g. on repo delete) ────────────────────────

export function destroyChatSocket(owner: string, name: string) {
  const key = repoKey(owner, name)
  const entry = wsRegistry[key]
  if (!entry) return
  entry.dead = true
  if (entry.reconnectTimer) clearTimeout(entry.reconnectTimer)
  entry.ws?.close()
  delete wsRegistry[key]
}