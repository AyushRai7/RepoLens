"use client";

import { GitBranch, Download, RefreshCw } from "lucide-react";

interface DiagramToolbarProps {
  totalFiles: number;
  cached: boolean;
  ready: boolean;
  onDownload: () => void;
  onRegenerate: () => void;
}

export default function DiagramToolbar({ totalFiles, cached, ready, onDownload, onRegenerate }: DiagramToolbarProps) {
  return (
    <div className="flex items-center justify-between px-5 py-2.5 border-b border-white/6 bg-[#0d0d14]/90 backdrop-blur flex-shrink-0">
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-1.5 text-xs text-white/50">
          <GitBranch className="w-3.5 h-3.5 text-violet-400" />
          <span className="font-medium text-white/70">Architecture Diagram</span>
        </div>
        {ready && (
          <div className="flex items-center gap-2 text-[10px] text-white/30">
            <span>·</span>
            <span>{totalFiles} files · AI-generated</span>
            {cached && (
              <span className="px-1.5 py-0.5 rounded bg-white/5 border border-white/8 text-white/25">cached</span>
            )}
          </div>
        )}
      </div>

      <div className="flex items-center gap-2">
        {ready && (
          <>
            <button onClick={onDownload} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-white/8 bg-white/3 text-xs text-white/40 hover:text-white/70 hover:bg-white/6 transition-all">
              <Download className="w-3 h-3" /> .mmd
            </button>
            <button onClick={onRegenerate} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-white/8 bg-white/3 text-xs text-white/40 hover:text-white/70 hover:bg-white/6 transition-all" title="Regenerate diagram (clears cache)">
              <RefreshCw className="w-3 h-3" /> Regenerate
            </button>
          </>
        )}
      </div>
    </div>
  );
}