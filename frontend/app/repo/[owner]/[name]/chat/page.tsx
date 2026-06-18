'use client'


import { Suspense } from 'react'
import { useParams, useSearchParams } from 'next/navigation'
import { useRepoStore } from '@/store/repoStore'
import ChatPanel from '@/components/chat/ChatPanel'

function ChatPageInner() {
  const params = useParams<{ owner: string; name: string }>()
  const searchParams = useSearchParams()
  const { owner, name } = params

  const scopedFile = searchParams.get('file')
  const { selectedFile } = useRepoStore()
  const activeFile = scopedFile ?? selectedFile ?? null

  return (
    <div className="h-[calc(100vh-130px)]">
      <ChatPanel
        owner={owner}
        name={name}
        scopedFile={activeFile}
      />
    </div>
  )
}

export default function ChatPage() {
  return (
    <Suspense fallback={
      <div className="h-[calc(100vh-130px)] flex items-center justify-center text-white/20 text-sm">
        Loading chat…
      </div>
    }>
      <ChatPageInner />
    </Suspense>
  )
}