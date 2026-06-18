"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getFileDetail } from "@/lib/api";
import type { FileDetail } from "@/lib/types";
import {
  X, FileCode2, ArrowUpRight, ArrowDownRight,
  MessageSquare, ChevronRight, Loader2, Sparkles,
} from "lucide-react";

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface FileDetailPanelProps {
  owner: string;
  name: string;
  path: string;
  onClose: () => void;
}

export default function FileDetailPanel({ owner, name, path, onClose }: FileDetailPanelProps) {
  const router = useRouter();
  const [detail, setDetail] = useState<FileDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [summary, setSummary] = useState<string | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    setSummary(null);
    getFileDetail(owner, name, path)
      .then((d) => { setDetail(d); if (d.ai_summary) setSummary(d.ai_summary); })
      .finally(() => setLoading(false));
  }, [path]);

  async function generateSummary() {
    setSummaryLoading(true);
    try {
      const res = await fetch(`${BASE}/api/graph/${owner}/${name}/summarize`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path }),
      });
      const data = await res.json();
      setSummary(data.summary ?? data.detail ?? "No summary returned.");
    } catch { setSummary("Failed to reach the backend."); }
    finally { setSummaryLoading(false); }
  }

  return (
    <div className="absolute right-0 top-0 h-full w-80 bg-[#0d0d14]/96 backdrop-blur border-l border-white/8 z-20 flex flex-col shadow-2xl">
      <div className="flex items-center justify-between p-4 border-b border-white/8">
        <div className="flex items-center gap-2 min-w-0">
          <FileCode2 className="w-4 h-4 text-violet-400 flex-shrink-0" />
          <span className="text-sm font-medium text-white truncate">{path.split("/").pop()}</span>
        </div>
        <button onClick={onClose} className="text-white/30 hover:text-white/70 ml-2 flex-shrink-0">
          <X className="w-4 h-4" />
        </button>
      </div>

      {loading ? (
        <div className="flex-1 flex items-center justify-center">
          <Loader2 className="w-5 h-5 text-violet-400 animate-spin" />
        </div>
      ) : detail ? (
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          <p className="text-[10px] text-white/20 font-mono break-all leading-relaxed">{path}</p>

          <div className="grid grid-cols-2 gap-2">
            {[
              ["Language", detail.language],
              ["Lines", detail.lines],
              ["Functions", detail.functions.length],
              ["Classes", detail.classes.length],
            ].map(([k, v]) => (
              <div key={k as string} className="p-2.5 rounded-lg bg-white/4 border border-white/6">
                <div className="text-[10px] text-white/30 mb-0.5">{k}</div>
                <div className="text-sm font-medium text-white">{v}</div>
              </div>
            ))}
          </div>

          <div className="p-3 rounded-lg bg-violet-500/8 border border-violet-500/15">
            <div className="flex items-center justify-between mb-1.5">
              <div className="text-[10px] text-violet-400 flex items-center gap-1">
                <Sparkles className="w-2.5 h-2.5" /> AI Summary
              </div>
              {!summary && !summaryLoading && (
                <button onClick={generateSummary} className="text-[10px] text-violet-300 hover:text-violet-200 px-2 py-0.5 rounded bg-violet-500/15 border border-violet-500/20">
                  Generate
                </button>
              )}
            </div>
            {summaryLoading ? (
              <div className="flex items-center gap-2">
                <Loader2 className="w-3 h-3 text-violet-400 animate-spin" />
                <span className="text-xs text-white/40">Analyzing with Groq…</span>
              </div>
            ) : summary ? (
              <p className="text-xs text-white/65 leading-relaxed">{summary}</p>
            ) : (
              <p className="text-xs text-white/25 italic">Click Generate for an AI explanation</p>
            )}
          </div>

          {detail.functions.length > 0 && (
            <div>
              <div className="text-xs font-medium text-white/40 mb-2">Functions ({detail.functions.length})</div>
              <div className="space-y-1 max-h-40 overflow-y-auto">
                {detail.functions.slice(0, 15).map((fn) => (
                  <div key={fn.name} className="flex items-center gap-2 py-1.5 px-2 rounded bg-white/3">
                    <span className="text-[10px] text-violet-400 font-mono flex-shrink-0">fn</span>
                    <span className="text-xs text-white/70 font-mono truncate">{fn.name}</span>
                    <span className="text-[10px] text-white/20 ml-auto flex-shrink-0">:{fn.line}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {detail.imports_from.length > 0 && (
            <div>
              <div className="text-xs font-medium text-white/40 mb-2 flex items-center gap-1">
                <ArrowUpRight className="w-3 h-3" /> Imports from ({detail.imports_from.length})
              </div>
              <div className="space-y-1">
                {detail.imports_from.slice(0, 8).map((p) => (
                  <div key={p} className="text-[10px] text-white/40 font-mono truncate pl-2">{p}</div>
                ))}
              </div>
            </div>
          )}

          {detail.imported_by.length > 0 && (
            <div>
              <div className="text-xs font-medium text-white/40 mb-2 flex items-center gap-1">
                <ArrowDownRight className="w-3 h-3" /> Imported by ({detail.imported_by.length})
              </div>
              <div className="space-y-1">
                {detail.imported_by.slice(0, 8).map((p) => (
                  <div key={p} className="text-[10px] text-white/40 font-mono truncate pl-2">{p}</div>
                ))}
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="flex-1 flex items-center justify-center text-white/30 text-sm">File not found</div>
      )}

      <div className="p-4 border-t border-white/8">
        <button
          onClick={() => router.push(`/repo/${owner}/${name}/chat?file=${encodeURIComponent(path)}`)}
          className="w-full flex items-center justify-center gap-2 py-2 rounded-lg bg-violet-600 hover:bg-violet-500 text-white text-xs font-medium transition-colors"
        >
          <MessageSquare className="w-3.5 h-3.5" /> Chat about this file <ChevronRight className="w-3 h-3" />
        </button>
      </div>
    </div>
  );
}