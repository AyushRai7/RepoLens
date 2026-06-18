"use client";

import { GitBranch, Sparkles, AlertCircle, RefreshCw } from "lucide-react";

export function DiagramIdleState({ onGenerate }: { onGenerate: () => void }) {
  return (
    <div className="flex items-center justify-center h-full">
      <div className="text-center space-y-4 max-w-sm">
        <div className="w-14 h-14 rounded-2xl bg-violet-600/15 border border-violet-500/20 flex items-center justify-center mx-auto">
          <GitBranch className="w-7 h-7 text-violet-400" />
        </div>
        <div>
          <h3 className="text-base font-semibold text-white/80 mb-1">Architecture Diagram</h3>
          <p className="text-xs text-white/35 leading-relaxed">
            AI reads the file tree and generates an interactive flowchart showing how your codebase components connect.
          </p>
        </div>
        <button onClick={onGenerate} className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-violet-600 hover:bg-violet-500 text-white text-sm font-medium transition-colors mx-auto">
          <Sparkles className="w-4 h-4" /> Generate Diagram
        </button>
      </div>
    </div>
  );
}

export function DiagramLoadingState() {
  return (
    <div className="flex items-center justify-center h-full">
      <div className="text-center space-y-3">
        <div className="relative w-12 h-12 mx-auto">
          <div className="absolute inset-0 rounded-full border-2 border-violet-500/20" />
          <div className="absolute inset-0 rounded-full border-2 border-t-violet-500 animate-spin" />
          <GitBranch className="absolute inset-0 m-auto w-5 h-5 text-violet-400" />
        </div>
        <div>
          <p className="text-sm font-medium text-white/70">Generating architecture diagram…</p>
          <p className="text-xs text-white/30 mt-1">AI is analyzing the file structure via Groq</p>
        </div>
        <div className="flex items-center gap-1.5 justify-center">
          {["Reading file tree", "Identifying layers", "Building diagram"].map((step, i) => (
            <div key={step} className="flex items-center gap-1.5 text-[10px] text-white/25">
              {i > 0 && <span className="text-white/10">›</span>}
              <span>{step}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export function DiagramErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="flex items-center justify-center h-full">
      <div className="text-center space-y-4 max-w-sm">
        <AlertCircle className="w-10 h-10 text-red-400/50 mx-auto" />
        <div>
          <p className="text-sm font-medium text-white/60">Failed to generate diagram</p>
          <p className="text-xs text-white/30 mt-1 leading-relaxed">{message}</p>
        </div>
        <button onClick={onRetry} className="flex items-center gap-2 px-4 py-2 rounded-lg bg-white/8 hover:bg-white/12 border border-white/10 text-white/60 text-xs transition-all mx-auto">
          <RefreshCw className="w-3.5 h-3.5" /> Try again
        </button>
      </div>
    </div>
  );
}