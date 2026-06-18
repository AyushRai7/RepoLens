"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { getCommits } from "@/lib/api";
import type { Commit } from "@/lib/types";
import { cn, timeAgo } from "@/lib/utils";
import {
  GitCommitHorizontal,
  Plus,
  Minus,
  ChevronDown,
  ChevronRight,
  Search,
  User,
} from "lucide-react";

function CommitRow({ commit }: { commit: Commit }) {
  const [open, setOpen] = useState(false);
  const lines = commit.message.split("\n");
  const title = lines[0];
  const body = lines.slice(1).join("\n").trim();

  return (
    <div className="border border-white/8 rounded-xl overflow-hidden hover:border-white/12 transition-colors">
      {/* Main row */}
      <div
        className="flex items-start gap-3 p-4 cursor-pointer"
        onClick={() => setOpen((o) => !o)}
      >
        <GitCommitHorizontal className="w-4 h-4 text-violet-400 mt-0.5 flex-shrink-0" />

        <div className="flex-1 min-w-0">
          <a
            href={commit.github_url}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            className="text-sm text-white/80 font-medium leading-snug mb-1 line-clamp-2 hover:text-violet-400 transition-colors block"
          >
            {title}
          </a>

          {/* AI summary badge */}
          {commit.ai_summary && (
            <p className="text-xs text-violet-300/70 mb-2 italic">
              {commit.ai_summary}
            </p>
          )}

          <div className="flex flex-wrap items-center gap-3 text-[10px] text-white/30">
            <span className="flex items-center gap-1">
              <User className="w-2.5 h-2.5" />
              {commit.author_name}
            </span>
            <span>{timeAgo(commit.committed_at)}</span>
            <span className="font-mono text-white/20">{commit.sha_short}</span>
            <span className="flex items-center gap-1 text-green-400/60">
              <Plus className="w-2.5 h-2.5" />
              {commit.additions}
            </span>
            <span className="flex items-center gap-1 text-red-400/60">
              <Minus className="w-2.5 h-2.5" />
              {commit.deletions}
            </span>
            <span>{commit.files_changed.length} files</span>
          </div>
        </div>

        {/* Expand toggle */}
        <button className="text-white/20 flex-shrink-0 mt-0.5">
          {open ? (
            <ChevronDown className="w-3.5 h-3.5" />
          ) : (
            <ChevronRight className="w-3.5 h-3.5" />
          )}
        </button>
      </div>

      {/* Expanded detail */}
      {open && (
        <div className="border-t border-white/8 bg-white/2 px-4 py-3 space-y-3">
          {body && (
            <pre className="text-xs text-white/40 whitespace-pre-wrap font-mono leading-relaxed">
              {body}
            </pre>
          )}

          {commit.files_changed.length > 0 && (
            <div>
              <p className="text-[10px] font-medium text-white/30 mb-1.5">
                Files changed
              </p>
              <div className="flex flex-wrap gap-1">
                {commit.files_changed.slice(0, 20).map((f, i) => (
                  <span
                    key={i}
                    className="text-[10px] font-mono px-2 py-0.5 rounded bg-white/5 border border-white/8 text-white/40 truncate max-w-[200px]"
                  >
                    {f}
                  </span>
                ))}
                {commit.files_changed.length > 20 && (
                  <span className="text-[10px] text-white/25">
                    +{commit.files_changed.length - 20} more
                  </span>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ContributorBar({ commits }: { commits: Commit[] }) {
  const counts: Record<string, number> = {};
  commits.forEach((c) => {
    counts[c.author_name] = (counts[c.author_name] ?? 0) + 1;
  });
  const sorted = Object.entries(counts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6);
  const max = sorted[0]?.[1] ?? 1;

  return (
    <div className="p-4 rounded-xl border border-white/8 bg-white/3 mb-6">
      <h3 className="text-xs font-medium text-white/40 mb-3">
        Top contributors
      </h3>
      <div className="space-y-2">
        {sorted.map(([author, count]) => (
          <div key={author} className="flex items-center gap-3">
            <span className="text-xs text-white/50 w-28 truncate">
              {author}
            </span>
            <div className="flex-1 h-1.5 bg-white/5 rounded-full overflow-hidden">
              <div
                className="h-full bg-violet-500/60 rounded-full"
                style={{ width: `${(count / max) * 100}%` }}
              />
            </div>
            <span className="text-[10px] text-white/25 w-8 text-right">
              {count}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function CommitsPage() {
  const params = useParams<{ owner: string; name: string }>();
  const { owner, name } = params;

  const [commits, setCommits] = useState<Commit[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [authorFilter, setAuthorFilter] = useState<string | null>(null);

  useEffect(() => {
    getCommits(owner, name, 50).then((r) => {
      setCommits(r.commits);
      setLoading(false);
    });
  }, []);

  const authors = [...new Set(commits.map((c) => c.author_name))].slice(0, 8);

  const filtered = commits.filter((c) => {
    if (authorFilter && c.author_name !== authorFilter) return false;
    if (
      search &&
      !c.message.toLowerCase().includes(search.toLowerCase()) &&
      !c.sha.includes(search)
    )
      return false;
    return true;
  });

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <span className="w-5 h-5 rounded-full border-2 border-violet-500/30 border-t-violet-500 animate-spin" />
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto px-5 py-6">
      <div className="flex items-center justify-between mb-5">
        <h2 className="text-lg font-semibold text-white/80">Commit History</h2>
        <span className="text-xs text-white/30">{commits.length} commits</span>
      </div>

      {/* Contributor bar */}
      {commits.length > 0 && <ContributorBar commits={commits} />}

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-2 mb-5">
        {/* Search */}
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-white/8 bg-white/3 flex-1 min-w-[180px]">
          <Search className="w-3 h-3 text-white/25 flex-shrink-0" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search commits..."
            className="bg-transparent text-xs text-white placeholder:text-white/25 outline-none flex-1"
          />
        </div>

        {/* Author filter */}
        <div className="flex flex-wrap gap-1">
          <button
            onClick={() => setAuthorFilter(null)}
            className={cn(
              "text-xs px-2.5 py-1 rounded-lg border transition-all",
              !authorFilter
                ? "bg-violet-600 border-violet-500 text-white"
                : "border-white/8 text-white/40 hover:text-white/60",
            )}
          >
            All
          </button>
          {authors.map((a) => (
            <button
              key={a}
              onClick={() => setAuthorFilter(a === authorFilter ? null : a)}
              className={cn(
                "text-xs px-2.5 py-1 rounded-lg border transition-all truncate max-w-[120px]",
                authorFilter === a
                  ? "bg-violet-600 border-violet-500 text-white"
                  : "border-white/8 text-white/40 hover:text-white/60",
              )}
            >
              {a}
            </button>
          ))}
        </div>
      </div>

      {/* Commit list */}
      <div className="space-y-2">
        {filtered.map((commit) => (
          <CommitRow key={commit.sha} commit={commit} />
        ))}
        {filtered.length === 0 && (
          <div className="py-12 text-center text-white/25 text-sm">
            No commits match your filters
          </div>
        )}
      </div>
    </div>
  );
}
