"use client";

import { useEffect, useState } from "react";
import {
  Search,
  ChevronRight,
  Sparkles,
  Loader2,
  Copy,
  Check,
} from "lucide-react";
import { cn, getLangColor } from "@/lib/utils";
import { getFunctions } from "@/lib/api";
import type { FunctionEntry } from "@/lib/types";

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function Loader() {
  return (
    <div className="flex items-center justify-center py-16">
      <span className="w-5 h-5 rounded-full border-2 border-violet-500/30 border-t-violet-500 animate-spin" />
    </div>
  );
}

function FunctionDetail({
  fn,
  owner,
  repoName,
}: {
  fn: FunctionEntry & { source_code?: string };
  owner: string;
  repoName: string;
}) {
  const [explanation, setExplanation] = useState<string | null>(null);
  const [explaining, setExplaining] = useState(false);
  const [explainError, setExplainError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const sourceCode = fn.source_code ?? fn.signature ?? "";

  async function handleExplain() {
    if (explanation || explaining) return;
    setExplaining(true);
    setExplainError(null);
    try {
      const res = await fetch(
        `${BASE}/api/structure/${owner}/${repoName}/explain-function`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            function_name: fn.name,
            file: fn.file,
            signature: fn.signature,
            source_code: sourceCode,
            language: fn.language,
          }),
        }
      );
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
        throw new Error(err.detail ?? `HTTP ${res.status}`);
      }
      const data = await res.json();
      setExplanation(data.explanation ?? "No explanation returned.");
    } catch (err: any) {
      setExplainError(err?.message ?? "Failed to get explanation.");
    } finally {
      setExplaining(false);
    }
  }

  function handleCopy() {
    navigator.clipboard.writeText(sourceCode);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <div className="bg-[#0d0d16] border-t border-white/6 px-5 py-4 flex flex-col gap-4">
      {/* Source code */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <span className="text-[10px] uppercase tracking-wider text-white/25 font-semibold">
            Source Code
          </span>
          {sourceCode && (
            <button
              onClick={handleCopy}
              className="flex items-center gap-1 text-[10px] text-white/30 hover:text-white/60 transition-colors"
            >
              {copied ? (
                <>
                  <Check className="w-3 h-3 text-green-400" />
                  <span className="text-green-400">Copied</span>
                </>
              ) : (
                <>
                  <Copy className="w-3 h-3" />
                  Copy
                </>
              )}
            </button>
          )}
        </div>
        {sourceCode ? (
          <pre className="rounded-xl bg-[#111118] border border-white/6 px-4 py-3 text-[11px] font-mono text-green-300/80 overflow-x-auto whitespace-pre leading-relaxed max-h-80">
            {sourceCode}
          </pre>
        ) : (
          <div className="rounded-xl bg-[#111118] border border-white/6 px-4 py-3 text-xs text-white/20 italic">
            Source not available for this function.
          </div>
        )}
      </div>

      {/* AI Explanation */}
      <div>
        {!explanation && !explaining && !explainError && (
          <button
            onClick={handleExplain}
            className="flex items-center gap-2 px-3 py-2 rounded-lg border border-violet-500/20 bg-violet-500/8 text-violet-300 text-xs font-medium hover:bg-violet-500/15 hover:border-violet-500/35 transition-all"
          >
            <Sparkles className="w-3.5 h-3.5" />
            Explain with AI
          </button>
        )}

        {explaining && (
          <div className="flex items-center gap-2 text-xs text-violet-300/60">
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
            Generating explanation…
          </div>
        )}

        {explainError && (
          <div className="flex items-center gap-3">
            <p className="text-xs text-red-400/70">{explainError}</p>
            <button
              onClick={() => { setExplainError(null); handleExplain(); }}
              className="text-xs text-white/40 underline hover:text-white/70 transition-colors"
            >
              Retry
            </button>
          </div>
        )}

        {explanation && (
          <div className="rounded-xl bg-violet-500/5 border border-violet-500/15 px-4 py-3">
            <div className="flex items-center gap-1.5 mb-2">
              <Sparkles className="w-3 h-3 text-violet-400" />
              <span className="text-[10px] uppercase tracking-wider text-violet-400/60 font-semibold">
                AI Explanation
              </span>
            </div>
            <p className="text-xs text-white/60 leading-relaxed whitespace-pre-wrap">
              {explanation}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

export default function FunctionsTab({
  owner,
  name,
}: {
  owner: string;
  name: string;
}) {
  const [data, setData] = useState<(FunctionEntry & { source_code?: string })[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [expandedRow, setExpandedRow] = useState<string | null>(null);

  useEffect(() => {
    getFunctions(owner, name).then((r) => {
      setData(r.functions as any);
      setLoading(false);
    });
  }, []);

  const filtered = data.filter(
    (f) =>
      !search ||
      f.name.toLowerCase().includes(search.toLowerCase()) ||
      f.file.toLowerCase().includes(search.toLowerCase())
  );

  function rowId(f: FunctionEntry) {
    return `${f.file}::${f.name}::${f.line}`;
  }

  function toggleRow(id: string) {
    setExpandedRow((prev) => (prev === id ? null : id));
  }

  if (loading) return <Loader />;

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <span className="text-xs text-white/30">
          {data.length} function{data.length !== 1 ? "s" : ""} found
        </span>
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-white/8 bg-white/3 w-56">
          <Search className="w-3 h-3 text-white/25" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search functions..."
            className="bg-transparent text-xs text-white placeholder:text-white/25 outline-none flex-1"
          />
        </div>
      </div>

      <div className="rounded-xl border border-white/8 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-white/8 bg-white/3">
              <th className="w-8 px-3 py-2.5" />
              <th className="text-left px-4 py-2.5 text-xs font-medium text-white/40">Function</th>
              <th className="text-left px-4 py-2.5 text-xs font-medium text-white/40">File</th>
              <th className="text-left px-4 py-2.5 text-xs font-medium text-white/40">Lang</th>
              <th className="text-left px-4 py-2.5 text-xs font-medium text-white/40">Line</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 && (
              <tr>
                <td colSpan={5} className="py-10 text-center text-white/25 text-sm">
                  No functions match your search
                </td>
              </tr>
            )}
            {filtered.slice(0, 200).map((fn) => {
              const id = rowId(fn);
              const isOpen = expandedRow === id;
              return (
                <>
                  <tr
                    key={id}
                    onClick={() => toggleRow(id)}
                    className={cn(
                      "border-b border-white/5 cursor-pointer transition-colors",
                      isOpen ? "bg-white/[0.04]" : "hover:bg-white/3"
                    )}
                  >
                    <td className="pl-3 py-2.5">
                      <ChevronRight
                        className={cn(
                          "w-3.5 h-3.5 text-white/20 transition-transform duration-150",
                          isOpen && "rotate-90 text-violet-400"
                        )}
                      />
                    </td>
                    <td className="px-4 py-2.5">
                      <span className="font-mono text-xs text-violet-300">{fn.name}</span>
                      {fn.ai_description && (
                        <p className="text-[10px] text-white/30 mt-0.5">{fn.ai_description}</p>
                      )}
                    </td>
                    <td className="px-4 py-2.5 font-mono text-[10px] text-white/30 max-w-[200px] truncate">
                      {fn.file}
                    </td>
                    <td className="px-4 py-2.5">
                      <span className="flex items-center gap-1">
                        <span
                          className="w-1.5 h-1.5 rounded-full flex-shrink-0"
                          style={{ background: getLangColor(fn.language) }}
                        />
                        <span className="text-[10px] text-white/40">{fn.language}</span>
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-[10px] text-white/30">{fn.line}</td>
                  </tr>
                  {isOpen && (
                    <tr key={`${id}-detail`} className="border-b border-white/5">
                      <td colSpan={5} className="p-0">
                        <FunctionDetail fn={fn} owner={owner} repoName={name} />
                      </td>
                    </tr>
                  )}
                </>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}