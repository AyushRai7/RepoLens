'use client'

import { useEffect } from 'react'
import { useParams, usePathname, useRouter } from 'next/navigation'
import Link from 'next/link'
import { useRepoStore } from '@/store/repoStore'
import { useRepoAnalysis } from '@/hooks/useRepoAnalysis'
import { useChat } from '@/hooks/useChat'
import {
  Network, MessageSquare, GitBranch,
  FileCode2, BookOpen, LayoutDashboard,
  AlertCircle, Star, GitFork, CheckCircle2
} from 'lucide-react'
import { cn, formatNumber } from '@/lib/utils'

const TABS = [
  { id: 'overview',   label: 'Overview',   icon: LayoutDashboard, path: '' },
  { id: 'graph',      label: 'Graph',      icon: Network,         path: '/graph',     needsReady: true },
  { id: 'chat',       label: 'Chat',       icon: MessageSquare,   path: '/chat',      needsReady: true },
  { id: 'structure',  label: 'Structure',  icon: FileCode2,       path: '/structure', needsReady: true },
  { id: 'commits',    label: 'Commits',    icon: GitBranch,       path: '/commits',   needsReady: true },
  { id: 'docs',       label: 'Docs',       icon: BookOpen,        path: '/docs',      needsReady: true },
]

const STAGE_LABELS: Record<string, string> = {
  pending:   'Queued',
  fetching:  'Fetching repo',
  parsing:   'Parsing code',
  graphing:  'Building graph',
  analyzing: 'AI analysis',
  ready:     'Ready',
  failed:    'Failed',
}

const STAGE_ORDER = ['pending', 'fetching', 'parsing', 'graphing', 'analyzing', 'ready']

// Inner component so useChat can use params
function RepoLayoutInner({ 
  children, 
  owner, 
  name 
}: { 
  children: React.ReactNode
  owner: string
  name: string 
}) {
  const pathname = usePathname()
  const router = useRouter()

  const { setRepo, pipelineStatus, repoMeta } = useRepoStore()
  const { status, progress, message, isReady, isFailed } = useRepoAnalysis(owner, name)

  // Initialize WS connection at layout level — stays alive across all tab switches
  useChat(owner, name)

  useEffect(() => {
    setRepo(owner, name)
  }, [owner, name])

  const baseUrl = `/repo/${owner}/${name}`
  const currentTab = TABS.find(t => pathname === baseUrl + t.path) ?? TABS[0]
  const stageIndex = STAGE_ORDER.indexOf(status)

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-white flex flex-col">

      {/* Top bar */}
      <header className="border-b border-white/8 bg-[#0d0d14]/80 backdrop-blur-md sticky top-0 z-50">

        {/* Repo identity row */}
        <div className="flex items-center justify-between px-5 py-3">
          <div className="flex items-center gap-3 min-w-0">
            <Link href="/" className="w-6 h-6 rounded bg-violet-600 flex items-center justify-center flex-shrink-0">
              <Network className="w-3.5 h-3.5 text-white" />
            </Link>
            <span className="text-white/20">/</span>
            <div className="flex items-center gap-2 min-w-0">
              <span className="text-sm text-white/50 truncate">{owner}</span>
              <span className="text-white/20">/</span>
              <span className="text-sm font-medium text-white truncate">{name}</span>
            </div>
            {pipelineStatus?.language && (
              <span className="hidden sm:inline-flex text-xs px-2 py-0.5 rounded-full bg-white/8 text-white/40 border border-white/10">
                {pipelineStatus.language}
              </span>
            )}
          </div>

          <div className="flex items-center gap-3 flex-shrink-0">
            {repoMeta && (
              <>
                <span className="hidden sm:flex items-center gap-1 text-xs text-white/40">
                  <Star className="w-3 h-3" />
                  {formatNumber(repoMeta.stars)}
                </span>
                <span className="hidden sm:flex items-center gap-1 text-xs text-white/40">
                  <GitFork className="w-3 h-3" />
                  {formatNumber(repoMeta.forks)}
                </span>
              </>
            )}
            <div className={cn(
              'flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full border',
              isReady
                ? 'bg-green-500/10 border-green-500/20 text-green-400'
                : isFailed
                ? 'bg-red-500/10 border-red-500/20 text-red-400'
                : 'bg-violet-500/10 border-violet-500/20 text-violet-300'
            )}>
              {isReady ? (
                <CheckCircle2 className="w-3 h-3" />
              ) : isFailed ? (
                <AlertCircle className="w-3 h-3" />
              ) : (
                <span className="w-1.5 h-1.5 rounded-full bg-violet-400 animate-pulse" />
              )}
              {STAGE_LABELS[status] ?? status}
            </div>
          </div>
        </div>

        {/* Pipeline progress bar */}
        {!isReady && !isFailed && (
          <div className="px-5 pb-3">
            <div className="flex items-center gap-1.5 mb-2">
              {STAGE_ORDER.slice(1).map((stage, i) => (
                <div key={stage} className="flex items-center gap-1.5">
                  <div className={cn(
                    'flex items-center gap-1 text-xs px-2 py-0.5 rounded-full transition-all',
                    stageIndex > i
                      ? 'bg-green-500/15 text-green-400'
                      : stageIndex === i
                      ? 'bg-violet-500/20 text-violet-300 ring-1 ring-violet-500/30'
                      : 'bg-white/5 text-white/20'
                  )}>
                    {stageIndex > i && <CheckCircle2 className="w-2.5 h-2.5" />}
                    {stageIndex === i && <span className="w-1.5 h-1.5 rounded-full bg-violet-400 animate-pulse" />}
                    <span className="capitalize">{STAGE_LABELS[stage]}</span>
                  </div>
                  {i < STAGE_ORDER.length - 2 && (
                    <span className="text-white/10 text-xs">›</span>
                  )}
                </div>
              ))}
            </div>
            <div className="h-0.5 w-full bg-white/5 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-violet-600 to-blue-500 rounded-full transition-all duration-500"
                style={{ width: `${progress * 100}%` }}
              />
            </div>
            <p className="text-xs text-white/30 mt-1.5">{message}</p>
          </div>
        )}

        {/* Tabs */}
        <div className="flex items-center px-5 gap-0.5 overflow-x-auto scrollbar-none">
          {TABS.map((tab) => {
            const locked = tab.needsReady && !isReady
            const isActive = currentTab.id === tab.id
            return (
              <button
                key={tab.id}
                onClick={() => !locked && router.push(baseUrl + tab.path)}
                disabled={locked}
                className={cn(
                  'flex items-center gap-1.5 px-3 py-2.5 text-xs font-medium border-b-2 transition-all whitespace-nowrap',
                  isActive
                    ? 'border-violet-500 text-violet-300'
                    : locked
                    ? 'border-transparent text-white/20 cursor-not-allowed'
                    : 'border-transparent text-white/40 hover:text-white/70 hover:border-white/20 cursor-pointer'
                )}
              >
                <tab.icon className="w-3.5 h-3.5" />
                {tab.label}
                {locked && (
                  <span className="text-[10px] bg-white/8 px-1.5 py-0.5 rounded text-white/20">
                    Soon
                  </span>
                )}
              </button>
            )
          })}
        </div>
      </header>

      <main className="flex-1 overflow-auto">
        {children}
      </main>

    </div>
  )
}

export default function RepoLayout({ children }: { children: React.ReactNode }) {
  const params = useParams<{ owner: string; name: string }>()
  const { owner, name } = params

  return <RepoLayoutInner owner={owner} name={name}>{children}</RepoLayoutInner>
}