"use client";

import { Star, GitFork, Eye, Globe, Lock, AlertCircle, ExternalLink, Clock } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

// ── Types ──────────────────────────────────────────────────────────────────────

export interface RepoMeta {
  owner: string;
  name: string;
  fullName: string;          // e.g. "vercel/next.js"
  description: string | null;
  url: string;
  homepage: string | null;
  language: string | null;
  languages: Record<string, number>;  // { TypeScript: 189234, CSS: 21023, ... }
  stars: number;
  forks: number;
  watchers: number;
  openIssues: number;
  isPrivate: boolean;
  isFork: boolean;
  license: string | null;
  topics: string[];
  defaultBranch: string;
  pushedAt: string;          // ISO date string
  createdAt: string;
  diskUsageKb: number;
  ownerAvatarUrl: string;
}

interface RepoCardProps {
  repo: RepoMeta;
  className?: string;
}

// ── Helpers ────────────────────────────────────────────────────────────────────

const LANGUAGE_COLORS: Record<string, string> = {
  TypeScript: "#3178c6",
  JavaScript: "#f1e05a",
  Python: "#3572A5",
  Rust: "#dea584",
  Go: "#00ADD8",
  Java: "#b07219",
  "C++": "#f34b7d",
  C: "#555555",
  "C#": "#178600",
  Ruby: "#701516",
  Swift: "#ffac45",
  Kotlin: "#A97BFF",
  PHP: "#4F5D95",
  Scala: "#c22d40",
  Shell: "#89e051",
  HTML: "#e34c26",
  CSS: "#563d7c",
  Vue: "#41b883",
  Svelte: "#ff3e00",
  Dart: "#00B4AB",
  Elixir: "#6e4a7e",
  Haskell: "#5e5086",
  Lua: "#000080",
  MATLAB: "#e16737",
  R: "#198CE7",
};

function formatCount(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return String(n);
}

function formatBytes(kb: number): string {
  if (kb >= 1_048_576) return `${(kb / 1_048_576).toFixed(1)} GB`;
  if (kb >= 1_024) return `${(kb / 1_024).toFixed(1)} MB`;
  return `${kb} KB`;
}

function timeAgo(isoDate: string): string {
  const diff = Date.now() - new Date(isoDate).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days < 30) return `${days}d ago`;
  const months = Math.floor(days / 30);
  if (months < 12) return `${months}mo ago`;
  return `${Math.floor(months / 12)}y ago`;
}

// ── Language Bar ───────────────────────────────────────────────────────────────

function LanguageBar({ languages }: { languages: Record<string, number> }) {
  const total = Object.values(languages).reduce((a, b) => a + b, 0);
  if (total === 0) return null;

  const sorted = Object.entries(languages)
    .sort(([, a], [, b]) => b - a)
    .slice(0, 6);

  return (
    <div className="space-y-2">
      {/* Bar */}
      <div className="flex h-2 w-full overflow-hidden rounded-full bg-muted gap-[2px]">
        {sorted.map(([lang, bytes]) => (
          <div
            key={lang}
            style={{
              width: `${(bytes / total) * 100}%`,
              background: LANGUAGE_COLORS[lang] ?? "#8b8b8b",
            }}
            className="h-full first:rounded-l-full last:rounded-r-full transition-all"
          />
        ))}
      </div>
      {/* Legend */}
      <div className="flex flex-wrap gap-x-4 gap-y-1">
        {sorted.map(([lang, bytes]) => (
          <span key={lang} className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <span
              className="inline-block h-2.5 w-2.5 rounded-full flex-shrink-0"
              style={{ background: LANGUAGE_COLORS[lang] ?? "#8b8b8b" }}
            />
            <span className="font-medium text-foreground">{lang}</span>
            <span>{((bytes / total) * 100).toFixed(1)}%</span>
          </span>
        ))}
      </div>
    </div>
  );
}

// ── Stat Pill ──────────────────────────────────────────────────────────────────

function StatPill({
  icon: Icon,
  value,
  label,
  className,
}: {
  icon: React.ComponentType<{ className?: string }>;
  value: string | number;
  label: string;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex items-center gap-1.5 rounded-lg border border-border/60 bg-muted/40 px-3 py-1.5 text-sm",
        className
      )}
      aria-label={`${label}: ${value}`}
    >
      <Icon className="h-3.5 w-3.5 text-muted-foreground" />
      <span className="font-semibold tabular-nums">{value}</span>
      <span className="text-xs text-muted-foreground">{label}</span>
    </div>
  );
}

// ── Main Component ─────────────────────────────────────────────────────────────

export function RepoCard({ repo, className }: RepoCardProps) {
  const primaryLang = repo.language;
  const primaryColor = primaryLang ? (LANGUAGE_COLORS[primaryLang] ?? "#8b8b8b") : null;

  return (
    <article
      className={cn(
        "group relative overflow-hidden rounded-2xl border border-border bg-card shadow-sm transition-shadow hover:shadow-md",
        className
      )}
    >
      {/* Top accent strip colored by primary language */}
      {primaryColor && (
        <div
          className="h-[3px] w-full"
          style={{ background: `linear-gradient(90deg, ${primaryColor}cc, ${primaryColor}44)` }}
          aria-hidden
        />
      )}

      <div className="p-6 space-y-5">
        {/* Header row */}
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-start gap-3 min-w-0">
            {/* Owner avatar */}
            <img
              src={repo.ownerAvatarUrl}
              alt={`${repo.owner} avatar`}
              className="h-10 w-10 rounded-full border border-border object-cover flex-shrink-0"
            />
            <div className="min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <h2 className="text-lg font-bold leading-tight text-foreground truncate max-w-[280px]">
                  {repo.fullName}
                </h2>
                {repo.isPrivate ? (
                  <Badge variant="outline" className="gap-1 text-xs">
                    <Lock className="h-3 w-3" />
                    Private
                  </Badge>
                ) : (
                  <Badge variant="outline" className="gap-1 text-xs text-muted-foreground">
                    <Globe className="h-3 w-3" />
                    Public
                  </Badge>
                )}
                {repo.isFork && (
                  <Badge variant="secondary" className="gap-1 text-xs">
                    <GitFork className="h-3 w-3" />
                    Fork
                  </Badge>
                )}
              </div>
              <div className="flex items-center gap-2 mt-1 text-xs text-muted-foreground">
                <span>Branch: <span className="font-mono font-medium text-foreground">{repo.defaultBranch}</span></span>
                {repo.license && (
                  <>
                    <span>·</span>
                    <span>{repo.license}</span>
                  </>
                )}
                <span>·</span>
                <span>{formatBytes(repo.diskUsageKb)}</span>
              </div>
            </div>
          </div>

          {/* External links */}
          <div className="flex items-center gap-1.5 flex-shrink-0">
            {repo.homepage && (
              <a
                href={repo.homepage}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-border bg-muted/50 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                aria-label="Homepage"
              >
                <Globe className="h-3.5 w-3.5" />
              </a>
            )}
            <a
              href={repo.url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-border bg-muted/50 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              aria-label="Open on GitHub"
            >
              <ExternalLink className="h-3.5 w-3.5" />
            </a>
          </div>
        </div>

        {/* Description */}
        {repo.description && (
          <p className="text-sm text-muted-foreground leading-relaxed line-clamp-2">
            {repo.description}
          </p>
        )}

        {/* Stats row */}
        <div className="flex flex-wrap gap-2">
          <StatPill icon={Star} value={formatCount(repo.stars)} label="stars" />
          <StatPill icon={GitFork} value={formatCount(repo.forks)} label="forks" />
          <StatPill icon={Eye} value={formatCount(repo.watchers)} label="watchers" />
          {repo.openIssues > 0 && (
            <StatPill
              icon={AlertCircle}
              value={formatCount(repo.openIssues)}
              label="issues"
              className="text-amber-600 border-amber-200 bg-amber-50/50 dark:border-amber-900/40 dark:bg-amber-950/20 dark:text-amber-400"
            />
          )}
        </div>

        {/* Language breakdown */}
        {Object.keys(repo.languages).length > 0 && (
          <LanguageBar languages={repo.languages} />
        )}

        {/* Topics */}
        {repo.topics.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {repo.topics.slice(0, 10).map((topic) => (
              <span
                key={topic}
                className="rounded-full bg-primary/8 px-2.5 py-0.5 text-xs font-medium text-primary border border-primary/20"
              >
                {topic}
              </span>
            ))}
            {repo.topics.length > 10 && (
              <span className="rounded-full bg-muted px-2.5 py-0.5 text-xs text-muted-foreground">
                +{repo.topics.length - 10} more
              </span>
            )}
          </div>
        )}

        {/* Footer: last pushed */}
        <div className="flex items-center gap-1.5 text-xs text-muted-foreground border-t border-border/60 pt-4">
          <Clock className="h-3.5 w-3.5" />
          <span>Last pushed <time dateTime={repo.pushedAt}>{timeAgo(repo.pushedAt)}</time></span>
          <span className="ml-auto">
            Created <time dateTime={repo.createdAt}>{timeAgo(repo.createdAt)}</time>
          </span>
        </div>
      </div>
    </article>
  );
}

export default RepoCard;