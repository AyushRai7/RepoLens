'use client'

import { useState, useEffect, useRef } from 'react'
import { useParams } from 'next/navigation'
import { generateDocs, downloadDocsUrl, getGraph } from '@/lib/api'
import { useRepoStore } from '@/store/repoStore'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'
import { cn } from '@/lib/utils'
import {
  FileText, Download, Sparkles,
  BookOpen, File, Loader2, AlertCircle,
  Search, FileCode2, X,
} from 'lucide-react'

type DocScope = 'repo' | 'file'

export default function DocsPage() {
  const params = useParams<{ owner: string; name: string }>()
  const { owner, name } = params
  const { selectedFile, repoMeta } = useRepoStore()

  const [scope, setScope] = useState<DocScope>('repo')
  const [filePath, setFilePath] = useState(selectedFile ?? '')
  const [docs, setDocs] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const [allFilePaths, setAllFilePaths] = useState<string[]>([])
  const [showSuggestions, setShowSuggestions] = useState(false)
  const [inputFocused, setInputFocused] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const suggestionsRef = useRef<HTMLDivElement>(null)

  // Load file paths from graph data
  useEffect(() => {
    if (allFilePaths.length > 0) return
    getGraph(owner, name)
      .then((data) => setAllFilePaths(data.nodes.map((n) => n.id)))
      .catch(() => {})
  }, [owner, name])

  // Filter suggestions based on input
  const filteredPaths = filePath.trim()
    ? allFilePaths
        .filter((p) => p.toLowerCase().includes(filePath.toLowerCase()))
        .slice(0, 10)
    : allFilePaths.slice(0, 8)

  // Close suggestions on outside click
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (
        suggestionsRef.current &&
        !suggestionsRef.current.contains(e.target as Node) &&
        !inputRef.current?.contains(e.target as Node)
      ) {
        setShowSuggestions(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  async function generate() {
    setLoading(true)
    setError('')
    setDocs(null)
    try {
      const result = await generateDocs(owner, name, scope === 'file' ? filePath : undefined)
      setDocs(result.documentation)
    } catch (e: any) {
      setError(e.message || 'Failed to generate documentation')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-5xl mx-auto px-5 py-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-lg font-semibold text-white/80 mb-0.5">Documentation</h2>
          <p className="text-xs text-white/30">AI-generated docs for any file or the entire repository</p>
        </div>
      </div>

      {/* Controls */}
      <div className="p-5 rounded-xl border border-white/8 bg-white/3 mb-6">
        {/* Scope selector */}
        <div className="flex gap-2 mb-4">
          {([
            { id: 'repo', label: 'Full repository', icon: BookOpen, desc: 'Overview, architecture, all key files' },
            { id: 'file', label: 'Specific file', icon: File, desc: 'Detailed docs for one file' },
          ] as const).map(opt => (
            <button
              key={opt.id}
              onClick={() => setScope(opt.id)}
              className={cn(
                'flex-1 flex items-start gap-3 p-3 rounded-xl border text-left transition-all',
                scope === opt.id
                  ? 'border-violet-500/40 bg-violet-500/10'
                  : 'border-white/8 hover:border-white/15'
              )}
            >
              <div className={cn('w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5',
                scope === opt.id ? 'bg-violet-600/30' : 'bg-white/8'
              )}>
                <opt.icon className={cn('w-3.5 h-3.5', scope === opt.id ? 'text-violet-400' : 'text-white/40')} />
              </div>
              <div>
                <div className={cn('text-sm font-medium', scope === opt.id ? 'text-violet-300' : 'text-white/60')}>{opt.label}</div>
                <div className="text-xs text-white/25 mt-0.5">{opt.desc}</div>
              </div>
            </button>
          ))}
        </div>

        {/* File input with autocomplete */}
        {scope === 'file' && (
          <div className="mb-4 relative">
            <label className="text-xs text-white/40 mb-1.5 block">File path</label>

            {/* Input */}
            <div className={cn(
              'flex items-center gap-2 px-3 py-2 rounded-lg border transition-all bg-[#0a0a0f]',
              inputFocused
                ? 'border-violet-500/40 ring-1 ring-violet-500/10'
                : 'border-white/10'
            )}>
              <Search className="w-3.5 h-3.5 text-white/25 flex-shrink-0" />
              <input
                ref={inputRef}
                value={filePath}
                onChange={e => {
                  setFilePath(e.target.value)
                  setShowSuggestions(true)
                }}
                onFocus={() => {
                  setInputFocused(true)
                  setShowSuggestions(true)
                }}
                onBlur={() => setInputFocused(false)}
                onKeyDown={e => {
                  if (e.key === 'Escape') setShowSuggestions(false)
                }}
                placeholder="Search or type a file path…"
                className="flex-1 bg-transparent text-sm text-white placeholder:text-white/25 outline-none font-mono"
              />
              {filePath && (
                <button
                  onClick={() => {
                    setFilePath('')
                    setShowSuggestions(true)
                    inputRef.current?.focus()
                  }}
                  className="text-white/25 hover:text-white/50 transition-colors flex-shrink-0"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              )}
            </div>

            {/* Selected file pill */}
            {filePath && !showSuggestions && (
              <div className="flex items-center gap-1.5 mt-2">
                <span className="inline-flex items-center gap-1.5 text-[11px] font-mono bg-violet-500/10 border border-violet-500/20 text-violet-300 rounded-full px-2.5 py-0.5">
                  <FileCode2 className="w-3 h-3 flex-shrink-0" />
                  <span className="truncate max-w-[400px]">{filePath}</span>
                </span>
              </div>
            )}

            {/* Suggestions dropdown */}
            {showSuggestions && filteredPaths.length > 0 && (
              <div
                ref={suggestionsRef}
                className="absolute z-20 top-full mt-1 left-0 right-0 rounded-xl border border-white/8 bg-[#0d0d15] shadow-xl shadow-black/40 overflow-hidden"
              >
                {/* Header */}
                <div className="px-3 py-2 border-b border-white/5 flex items-center justify-between">
                  <span className="text-[10px] text-white/25">
                    {filePath.trim()
                      ? `${filteredPaths.length} match${filteredPaths.length !== 1 ? 'es' : ''}`
                      : 'All files'}
                  </span>
                  <button
                    onClick={() => setShowSuggestions(false)}
                    className="text-white/20 hover:text-white/50 transition-colors"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </div>

                {/* Results list */}
                <div className="max-h-52 overflow-y-auto py-1">
                  {filteredPaths.map((p) => {
                    const isSelected = filePath === p
                    const fileName = p.split('/').pop() ?? p
                    const dir = p.includes('/') ? p.substring(0, p.lastIndexOf('/')) : ''

                    const query = filePath.trim().toLowerCase()
                    const matchIdx = query ? p.toLowerCase().indexOf(query) : -1

                    return (
                      <button
                        key={p}
                        onMouseDown={(e) => {
                          e.preventDefault() 
                          setFilePath(p)
                          setShowSuggestions(false)
                        }}
                        className={cn(
                          'w-full flex items-center gap-2.5 px-3 py-2 text-left transition-colors',
                          isSelected
                            ? 'bg-violet-500/15 text-violet-300'
                            : 'text-white/55 hover:bg-white/4 hover:text-white/85'
                        )}
                      >
                        <FileCode2 className="w-3.5 h-3.5 flex-shrink-0 text-white/25" />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-baseline gap-1.5">
                            <span className="text-xs font-mono font-medium truncate">
                              {matchIdx >= 0 ? (
                                <>
                                  <span>{p.slice(0, matchIdx)}</span>
                                  <span className="text-violet-400 bg-violet-500/15 rounded px-0.5">
                                    {p.slice(matchIdx, matchIdx + query.length)}
                                  </span>
                                  <span>{p.slice(matchIdx + query.length)}</span>
                                </>
                              ) : (
                                p
                              )}
                            </span>
                          </div>
                        </div>
                        {isSelected && (
                          <span className="text-[9px] text-violet-400/60 flex-shrink-0">selected</span>
                        )}
                      </button>
                    )
                  })}
                </div>

                {filteredPaths.length === 0 && (
                  <p className="text-xs text-white/20 px-3 py-3">No files found</p>
                )}
              </div>
            )}
          </div>
        )}

        {/* Generate button */}
        <button
          onClick={generate}
          disabled={loading || (scope === 'file' && !filePath.trim())}
          className={cn(
            'flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-medium transition-all',
            loading || (scope === 'file' && !filePath.trim())
              ? 'bg-violet-600/30 text-white/30 cursor-not-allowed'
              : 'bg-violet-600 hover:bg-violet-500 text-white'
          )}
        >
          {loading
            ? <><Loader2 className="w-4 h-4 animate-spin" /> Generating...</>
            : <><Sparkles className="w-4 h-4" /> Generate Documentation</>
          }
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 p-4 rounded-xl border border-red-500/20 bg-red-500/8 text-red-400 text-sm mb-6">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          {error}
        </div>
      )}

      {/* Loading skeleton */}
      {loading && (
        <div className="p-6 rounded-xl border border-white/8 bg-white/3 space-y-3">
          <div className="h-6 w-48 bg-white/5 rounded animate-pulse" />
          <div className="h-3 w-full bg-white/5 rounded animate-pulse" />
          <div className="h-3 w-5/6 bg-white/5 rounded animate-pulse" />
          <div className="h-3 w-4/6 bg-white/5 rounded animate-pulse" />
          <div className="h-3 w-full bg-white/5 rounded animate-pulse mt-4" />
          <div className="h-3 w-3/4 bg-white/5 rounded animate-pulse" />
        </div>
      )}

      {/* Generated docs */}
      {docs && !loading && (
        <div>
          {/* Download buttons */}
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <FileText className="w-4 h-4 text-violet-400" />
              <span className="text-sm font-medium text-white/70">Generated documentation</span>
              {scope === 'file' && filePath && (
                <span className="text-xs font-mono text-white/30 bg-white/5 px-2 py-0.5 rounded-full">
                  {filePath.split('/').pop()}
                </span>
              )}
            </div>
            <div className="flex gap-2">
              {(['md', 'html'] as const).map(fmt => (
                <a
                  key={fmt}
                  href={downloadDocsUrl(owner, name, fmt)}
                  download
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-white/10 bg-white/5 hover:bg-white/8 transition-all text-xs text-white/50 hover:text-white/70"
                >
                  <Download className="w-3 h-3" />
                  .{fmt}
                </a>
              ))}
            </div>
          </div>

          {/* Rendered markdown */}
          <div className="prose prose-invert prose-sm max-w-none p-6 rounded-xl border border-white/8 bg-[#0d0d14]">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{

                code({ node, className, children, ...props }: any) {
                  const match = /language-(\w+)/.exec(className || '')
                  return !props.inline ? (
                    <SyntaxHighlighter
                      style={oneDark as any}
                      language={match?.[1] || 'text'}
                      PreTag="div"
                      className="!rounded-lg !text-xs !my-3"
                    >
                      {String(children).replace(/\n$/, '')}
                    </SyntaxHighlighter>
                  ) : (
                    <code className="bg-white/10 rounded px-1.5 py-0.5 text-xs font-mono text-violet-300" {...props}>
                      {children}
                    </code>
                  )
                },
                h1: ({ children }) => <h1 className="text-xl font-bold text-white mb-3 mt-6 first:mt-0">{children}</h1>,
                h2: ({ children }) => <h2 className="text-lg font-semibold text-white/90 mb-2 mt-5">{children}</h2>,
                h3: ({ children }) => <h3 className="text-base font-medium text-white/80 mb-2 mt-4">{children}</h3>,
                p: ({ children }) => <p className="text-white/60 leading-relaxed mb-3">{children}</p>,
                ul: ({ children }) => <ul className="list-disc list-inside space-y-1 my-2 text-white/60">{children}</ul>,
                ol: ({ children }) => <ol className="list-decimal list-inside space-y-1 my-2 text-white/60">{children}</ol>,
                table: ({ children }) => (
                  <div className="overflow-x-auto my-4">
                    <table className="w-full border border-white/10 rounded-lg overflow-hidden text-xs">{children}</table>
                  </div>
                ),
                th: ({ children }) => <th className="px-3 py-2 text-left bg-white/5 text-white/60 font-medium border-b border-white/10">{children}</th>,
                td: ({ children }) => <td className="px-3 py-2 text-white/50 border-b border-white/5">{children}</td>,
                blockquote: ({ children }) => (
                  <blockquote className="border-l-2 border-violet-500/40 pl-4 my-3 text-white/40 italic">{children}</blockquote>
                ),
              }}
            >
              {docs}
            </ReactMarkdown>
          </div>
        </div>
      )}

      {/* Empty state */}
      {!docs && !loading && !error && (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <div className="w-12 h-12 rounded-xl bg-violet-600/10 border border-violet-500/20 flex items-center justify-center mb-3">
            <BookOpen className="w-5 h-5 text-violet-400/60" />
          </div>
          <p className="text-white/30 text-sm">Choose a scope and click Generate</p>
          <p className="text-white/20 text-xs mt-1">Docs are generated by Groq LLaMA 3.1 and downloadable as Markdown or HTML</p>
        </div>
      )}
    </div>
  )
}