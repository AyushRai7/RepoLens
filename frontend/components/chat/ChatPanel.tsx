'use client'

import { useEffect, useRef, useState } from 'react'
import { useChatStore, MAX_CONTEXT_FILES } from '@/store/chatStore'
import { useChat } from '@/hooks/useChat'
import MessageBubble from './MessageBubble'
import {
  MessageSquare, Wifi, WifiOff, Loader2,
  Plus, X, FileCode2, Search,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { getGraph } from '@/lib/api'

interface ChatPanelProps {
  owner: string
  name: string
  scopedFile?: string | null
  suggestions?: string[]
  compact?: boolean
}

const DEFAULT_SUGGESTIONS = [
  'What does this project do?',
  'How does authentication work?',
  'Where are the API routes defined?',
  'What is the folder structure?',
]

export default function ChatPanel({
  owner,
  name,
  scopedFile = null,
  suggestions = DEFAULT_SUGGESTIONS,
  compact = false,
}: ChatPanelProps) {
  const repoKey = `${owner}/${name}`
  const { sendMessage, isConnected, isLoading, statusMessage } = useChat(owner, name)

  const { getSession, addContextFile, removeContextFile } = useChatStore()
  const session = getSession(repoKey)
  const messages = session.messages
  const selectedFiles = session.selectedFiles

  const bottomRef = useRef<HTMLDivElement>(null)

  // Auto-scroll on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  useEffect(() => {
    if (scopedFile) addContextFile(repoKey, scopedFile)
  }, [scopedFile, repoKey, addContextFile])

  // ── File picker state ──────────────────────────────────────────────────────
  const [allFilePaths, setAllFilePaths] = useState<string[]>([])
  const [showPicker, setShowPicker] = useState(false)
  const [pickerQuery, setPickerQuery] = useState('')
  const fetchedRef = useRef(false)   

  useEffect(() => {
    if (fetchedRef.current) return
    fetchedRef.current = true
    getGraph(owner, name)
      .then((data) => setAllFilePaths(data.nodes.map((n) => n.id)))
      .catch(() => {
        fetchedRef.current = false  
      })
  }, [owner, name])

  const filteredPaths = pickerQuery.trim()
    ? allFilePaths
        .filter((p) => p.toLowerCase().includes(pickerQuery.toLowerCase()))
        .slice(0, 10)
    : allFilePaths.slice(0, 10)

  const isEmpty = messages.length === 0

  return (
    <div className={cn('flex flex-col h-full bg-[#0a0a0f]', compact && 'text-xs')}>

      <div className={cn(
        'flex items-center gap-1.5 px-3 py-1.5 border-b text-xs transition-all flex-shrink-0',
        isConnected
          ? 'bg-green-500/5 border-green-500/10 text-green-400/60'
          : statusMessage?.toLowerCase().includes('fail') ||
            statusMessage?.toLowerCase().includes('error')
          ? 'bg-red-500/5 border-red-500/10 text-red-400/70'
          : 'bg-yellow-500/5 border-yellow-500/10 text-yellow-400/60'
      )}>
        {isConnected ? (
          <><Wifi className="w-3 h-3" />Connected</>
        ) : statusMessage ? (
          <><Loader2 className="w-3 h-3 animate-spin" />{statusMessage}</>
        ) : (
          <><WifiOff className="w-3 h-3" />Connecting…</>
        )}
      </div>

      {/* ── Messages ───────────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto px-3 py-4 space-y-4">
        {isEmpty ? (
          <EmptyState
            scopedFile={scopedFile}
            owner={owner}
            name={name}
            suggestions={suggestions}
            isLoading={isLoading}       // ← was isConnected (bug: disabled during reconnect)
            compact={compact}
            onSuggestion={(s) => sendMessage(s)}
          />
        ) : (
          <>
            {messages.map((msg) => (
              <div key={msg.id} className="flex flex-col">
                <MessageBubble message={msg} compact={compact} />
                {msg.role === 'user' && msg.contextFiles && msg.contextFiles.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-1 justify-end pr-1">
                    <span className="text-[9px] text-white/20 self-center">with:</span>
                    {msg.contextFiles.map((fp) => (
                      <span
                        key={fp}
                        title={fp}
                        className="inline-flex items-center gap-1 text-[9px] font-mono bg-violet-500/8 border border-violet-500/15 text-violet-400/50 rounded-full px-1.5 py-0.5"
                      >
                        <FileCode2 className="w-2 h-2 flex-shrink-0" />
                        <span className="max-w-[100px] truncate">{fp.split('/').pop()}</span>
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))}
            <div ref={bottomRef} />
          </>
        )}
      </div>

      {/* ── File context pills ─────────────────────────────────────── */}
      {selectedFiles.length > 0 && (
        <div className="flex flex-wrap gap-1.5 px-3 pt-2 pb-0 flex-shrink-0">
          {selectedFiles.map((fp) => (
            <span
              key={fp}
              className="flex items-center gap-1 text-[10px] font-mono bg-violet-500/10 border border-violet-500/20 text-violet-300 rounded-full px-2 py-0.5"
            >
              <FileCode2 className="w-2.5 h-2.5 flex-shrink-0" />
              <span className="max-w-[160px] truncate" title={fp}>
                {fp.split('/').pop()}
              </span>
              <button
                onClick={() => removeContextFile(repoKey, fp)}
                className="ml-0.5 text-violet-400/60 hover:text-violet-300 transition-colors"
                aria-label={`Remove ${fp}`}
              >
                <X className="w-2.5 h-2.5" />
              </button>
            </span>
          ))}
          <span className="text-[9px] text-white/20 self-center">
            {selectedFiles.length}/{MAX_CONTEXT_FILES} files
          </span>
        </div>
      )}

      {/* ── File picker dropdown ───────────────────────────────────── */}
      {showPicker && (
        <FilePicker
          repoKey={repoKey}
          query={pickerQuery}
          onQueryChange={setPickerQuery}
          paths={filteredPaths}
          selected={selectedFiles}
          onAdd={(p) => {
            addContextFile(repoKey, p)
            setPickerQuery('')
          }}
          onClose={() => {
            setShowPicker(false)
            setPickerQuery('')
          }}
        />
      )}

      {/* ── Chat input ─────────────────────────────────────────────── */}
      <ChatInput
        onSend={sendMessage}
        disabled={isLoading}            
        isLoading={isLoading}
        compact={compact}
        canAddFile={selectedFiles.length < MAX_CONTEXT_FILES}
        onOpenPicker={() => setShowPicker((v) => !v)}
        pickerOpen={showPicker}
      />
    </div>
  )
}

// ── File Picker ───────────────────────────────────────────────────────────────

function FilePicker({
  repoKey,
  query,
  onQueryChange,
  paths,
  selected,
  onAdd,
  onClose,
}: {
  repoKey: string
  query: string
  onQueryChange: (q: string) => void
  paths: string[]
  selected: string[]
  onAdd: (p: string) => void
  onClose: () => void
}) {
  const inputRef = useRef<HTMLInputElement>(null)
  useEffect(() => { inputRef.current?.focus() }, [])

  return (
    <div className="border-t border-white/8 bg-[#0d0d15] flex-shrink-0">
      <div className="flex items-center gap-2 px-3 py-2 border-b border-white/5">
        <Search className="w-3 h-3 text-white/30 flex-shrink-0" />
        <input
          ref={inputRef}
          value={query}
          onChange={(e) => onQueryChange(e.target.value)}
          placeholder="Search file path…"
          className="flex-1 bg-transparent text-xs text-white placeholder:text-white/25 outline-none"
        />
        <button onClick={onClose} className="text-white/30 hover:text-white/60 transition-colors">
          <X className="w-3.5 h-3.5" />
        </button>
      </div>

      <div className="max-h-44 overflow-y-auto py-1">
        {paths.length === 0 ? (
          <p className="text-xs text-white/20 px-3 py-2">No files found</p>
        ) : (
          paths.map((p) => {
            const alreadyAdded = selected.includes(p)
            const atLimit = selected.length >= MAX_CONTEXT_FILES
            return (
              <button
                key={p}
                onClick={() => { if (!alreadyAdded && !atLimit) onAdd(p) }}
                disabled={alreadyAdded || atLimit}
                className={cn(
                  'w-full flex items-center gap-2 px-3 py-1.5 text-left text-xs transition-colors',
                  alreadyAdded
                    ? 'text-violet-400/50 cursor-default'
                    : atLimit
                    ? 'text-white/20 cursor-not-allowed'
                    : 'text-white/50 hover:bg-white/4 hover:text-white/80 cursor-pointer'
                )}
              >
                <FileCode2 className="w-3 h-3 flex-shrink-0 text-white/25" />
                <span className="font-mono truncate">{p}</span>
                {alreadyAdded && (
                  <span className="ml-auto text-[9px] text-violet-400/50">added</span>
                )}
              </button>
            )
          })
        )}
      </div>

      {selected.length >= MAX_CONTEXT_FILES && (
        <p className="text-[10px] text-yellow-400/50 px-3 pb-2">
          Max {MAX_CONTEXT_FILES} files reached. Remove one to add more.
        </p>
      )}
    </div>
  )
}

// ── Empty State ───────────────────────────────────────────────────────────────

function EmptyState({
  scopedFile, owner, name, suggestions,
  isLoading, compact, onSuggestion,
}: {
  scopedFile: string | null
  owner: string
  name: string
  suggestions: string[]
  isLoading: boolean           // ← changed from isConnected
  compact: boolean
  onSuggestion: (s: string) => void
}) {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-4 text-center px-2">
      <div>
        <div className={cn(
          'rounded-xl bg-violet-600/15 border border-violet-500/20 flex items-center justify-center mx-auto mb-2',
          compact ? 'w-8 h-8' : 'w-11 h-11'
        )}>
          <MessageSquare className={cn('text-violet-400', compact ? 'w-4 h-4' : 'w-5 h-5')} />
        </div>
        <p className={cn('text-white/40 font-medium', compact ? 'text-xs' : 'text-sm')}>
          {scopedFile
            ? `Ask about ${scopedFile.split('/').pop()}`
            : `Chat with ${owner}/${name}`}
        </p>
        <p className={cn('text-white/20 mt-0.5', compact ? 'text-[10px]' : 'text-xs')}>
          The AI has read the entire codebase
        </p>
      </div>

      <div className={cn('grid gap-1.5 w-full', compact ? 'grid-cols-1' : 'grid-cols-1 sm:grid-cols-2')}>
        {suggestions.map((s) => (
          <button
            key={s}
            onClick={() => onSuggestion(s)}
            disabled={isLoading}   
            className={cn(
              'text-left p-2.5 rounded-xl border border-white/8 bg-white/3',
              'hover:bg-white/6 hover:border-white/15 transition-all',
              'text-white/45 disabled:opacity-30 disabled:cursor-not-allowed',
              compact ? 'text-[10px]' : 'text-xs'
            )}
          >
            {s}
          </button>
        ))}
      </div>
    </div>
  )
}

// ── Chat Input ────────────────────────────────────────────────────────────────

function ChatInput({
  onSend, disabled, isLoading, compact,
  canAddFile, onOpenPicker, pickerOpen,
}: {
  onSend: (msg: string) => void
  disabled: boolean
  isLoading: boolean
  compact: boolean
  canAddFile: boolean
  onOpenPicker: () => void
  pickerOpen: boolean
}) {
  const inputRef = useRef<HTMLTextAreaElement>(null)

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  function submit() {
    const val = inputRef.current?.value.trim()
    if (!val || disabled) return
    onSend(val)
    if (inputRef.current) inputRef.current.value = ''
  }

  return (
    <div className="border-t border-white/8 p-3 flex-shrink-0">
      <div className={cn(
        'flex items-end gap-2 p-2.5 rounded-xl border transition-all',
        disabled ? 'border-white/5 bg-white/2' : 'border-white/10 focus-within:border-violet-500/40 bg-[#111118]'
      )}>
        {/* Add file button */}
        <button
          onClick={onOpenPicker}
          title="Add file context"
          className={cn(
            'rounded-lg flex items-center justify-center flex-shrink-0 transition-all mb-0.5',
            compact ? 'w-5 h-5' : 'w-6 h-6',
            pickerOpen
              ? 'bg-violet-500/20 text-violet-300'
              : canAddFile
              ? 'bg-white/5 text-white/30 hover:bg-white/10 hover:text-white/60'
              : 'bg-white/3 text-white/15 cursor-not-allowed'
          )}
          disabled={!canAddFile && !pickerOpen}
        >
          <Plus className={cn(compact ? 'w-2.5 h-2.5' : 'w-3 h-3')} />
        </button>

        <textarea
          ref={inputRef}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          rows={1}
          placeholder={disabled ? 'Sending…' : 'Ask about the code…'}
          className={cn(
            'flex-1 bg-transparent text-white placeholder:text-white/20',
            'outline-none resize-none leading-relaxed disabled:opacity-40',
            'max-h-28 overflow-y-auto',
            compact ? 'text-xs' : 'text-sm'
          )}
        />

        <button
          onClick={submit}
          disabled={disabled}
          className={cn(
            'rounded-lg flex items-center justify-center flex-shrink-0 transition-all',
            compact ? 'w-6 h-6' : 'w-7 h-7',
            disabled
              ? 'bg-white/5 text-white/15 cursor-not-allowed'
              : 'bg-violet-600 hover:bg-violet-500 text-white'
          )}
        >
          {isLoading ? (
            <span className={cn(
              'rounded-full border-2 border-white/30 border-t-white animate-spin',
              compact ? 'w-2.5 h-2.5' : 'w-3 h-3'
            )} />
          ) : (
            <svg className={cn(compact ? 'w-2.5 h-2.5' : 'w-3 h-3')} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
              <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" />
            </svg>
          )}
        </button>
      </div>

      {!compact && (
        <p className="text-[10px] text-white/15 mt-1.5 text-center">
          Enter to send · Shift+Enter for new line · <span className="text-white/20">+ to add file context</span>
        </p>
      )}
    </div>
  )
}