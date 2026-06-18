import { useEffect, useRef } from 'react'
import { useRepoStore } from '@/store/repoStore'
import { getRepoStatus, getRepo, getGraph } from '@/lib/api'
import type { RepoStatus } from '@/lib/types'

const TERMINAL_STATES: RepoStatus[] = ['ready', 'failed']
const POLL_INTERVAL = 2000 // ms

export function useRepoAnalysis(owner: string, name: string) {
  const { setPipelineStatus, setRepoMeta, setGraphData, pipelineStatus } = useRepoStore()
  const timerRef = useRef<NodeJS.Timeout | null>(null)
  const mountedRef = useRef(true)

  useEffect(() => {
    mountedRef.current = true

    async function poll() {
      if (!mountedRef.current) return
      try {
        const status = await getRepoStatus(owner, name)
        if (!mountedRef.current) return
        setPipelineStatus(status)

        if (status.status === 'ready') {
          const [meta, graph] = await Promise.all([
            getRepo(owner, name),
            getGraph(owner, name),
          ])
          if (!mountedRef.current) return
          setRepoMeta(meta)
          setGraphData(graph)
          return 
        }

        if (status.status === 'failed') return 

        timerRef.current = setTimeout(poll, POLL_INTERVAL)
      } catch (err) {
        if (mountedRef.current) {
          timerRef.current = setTimeout(poll, POLL_INTERVAL * 2)
        }
      }
    }

    poll()

    return () => {
      mountedRef.current = false
      if (timerRef.current) clearTimeout(timerRef.current)
    }
  }, [owner, name])

  return {
    status: pipelineStatus?.status ?? 'pending',
    progress: pipelineStatus?.progress ?? 0,
    message: pipelineStatus?.message ?? 'Loading...',
    isReady: pipelineStatus?.status === 'ready',
    isFailed: pipelineStatus?.status === 'failed',
  }
}