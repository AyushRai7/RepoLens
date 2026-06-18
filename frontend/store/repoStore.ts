import { create } from 'zustand'
import type { PipelineStatus, RepoMeta, GraphData } from '@/lib/types'

interface RepoStore {
  // Current repo being viewed
  owner: string | null
  name: string | null
  setRepo: (owner: string, name: string) => void

  // Pipeline status (live while analysis runs)
  pipelineStatus: PipelineStatus | null
  setPipelineStatus: (s: PipelineStatus) => void

  // Full repo meta (once ready)
  repoMeta: RepoMeta | null
  setRepoMeta: (r: RepoMeta) => void

  // Graph data
  graphData: GraphData | null
  setGraphData: (g: GraphData) => void

  // Selected file node (for node-scoped chat)
  selectedFile: string | null
  setSelectedFile: (path: string | null) => void

  // Churn heatmap overlay toggle
  showChurn: boolean
  toggleChurn: () => void

  reset: () => void
}

export const useRepoStore = create<RepoStore>((set) => ({
  owner: null,
  name: null,
  setRepo: (owner, name) => set({ owner, name }),

  pipelineStatus: null,
  setPipelineStatus: (s) => set({ pipelineStatus: s }),

  repoMeta: null,
  setRepoMeta: (r) => set({ repoMeta: r }),

  graphData: null,
  setGraphData: (g) => set({ graphData: g }),

  selectedFile: null,
  setSelectedFile: (path) => set({ selectedFile: path }),

  showChurn: false,
  toggleChurn: () => set((s) => ({ showChurn: !s.showChurn })),

  reset: () => set({
    owner: null, name: null,
    pipelineStatus: null, repoMeta: null,
    graphData: null, selectedFile: null, showChurn: false,
  }),
}))