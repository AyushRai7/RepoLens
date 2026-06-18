"use client";

import { useParams } from "next/navigation";
import { useRepoStore } from "@/store/repoStore";
import { useRouter } from "next/navigation";
import type { LucideIcon } from "lucide-react";
import {
  Star,
  GitFork,
  Scale,
  FileCode2,
  Hash,
  AlertTriangle,
  CheckCircle2,
  ArrowRight,
  Globe,
  Calendar,
} from "lucide-react";
import { cn, formatNumber, getLangColor, timeAgo } from "@/lib/utils";

function HealthBar({ score }: { score: number }) {
  const color =
    score >= 80 ? "bg-green-500" : score >= 60 ? "bg-yellow-500" : "bg-red-500";
  const label = score >= 80 ? "Excellent" : score >= 60 ? "Good" : "Needs work";
  return (
    <div>
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-xs text-white/40">Health score</span>
        <span
          className={cn(
            "text-sm font-semibold",
            score >= 80
              ? "text-green-400"
              : score >= 60
                ? "text-yellow-400"
                : "text-red-400",
          )}
        >
          {score}/100 · {label}
        </span>
      </div>
      <div className="h-1.5 w-full bg-white/8 rounded-full overflow-hidden">
        <div
          className={cn(
            "h-full rounded-full transition-all duration-700",
            color,
          )}
          style={{ width: `${score}%` }}
        />
      </div>
    </div>
  );
}

function StatCard({
  icon: Icon,
  label,
  value,
  sub,
}: {
  icon: LucideIcon;
  label: string;
  value: string | number;
  sub?: string;
}) {
  return (
    <div className="p-4 rounded-xl border border-white/8 bg-white/3">
      <div className="flex items-center gap-2 mb-2">
        <Icon className="w-3.5 h-3.5 text-white/30" />
        <span className="text-xs text-white/30">{label}</span>
      </div>

      <div className="text-xl font-semibold text-white">{value}</div>

      {sub && <div className="text-xs text-white/30 mt-0.5">{sub}</div>}
    </div>
  );
}

export default function OverviewPage() {
  const params = useParams<{ owner: string; name: string }>();
  const { owner, name } = params;
  const router = useRouter();
  const { pipelineStatus, repoMeta } = useRepoStore();

  const isReady = pipelineStatus?.status === "ready";
  const data = repoMeta ?? pipelineStatus;

  return (
    <div className="max-w-5xl mx-auto px-5 py-8">
      {/* Repo header */}
      <div className="mb-8">
        <div className="flex items-start justify-between gap-4 mb-3">
          <div>
            <h1 className="text-2xl font-bold text-white mb-1">
              {owner}/<span className="text-violet-300">{name}</span>
            </h1>
            <p className="text-white/50 text-sm leading-relaxed max-w-2xl">
              {data?.description ?? "No description available."}
            </p>
          </div>
          <a
            href={`https://github.com/${owner}/${name}`}
            target="_blank"
            rel="noopener noreferrer"
            className="flex-shrink-0 flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border border-white/10 text-white/40 hover:text-white/70 hover:border-white/20 transition-all"
          >
            <Globe className="w-3 h-3" />
            GitHub
          </a>
        </div>

        {/* Tags */}
        <div className="flex flex-wrap gap-2">
          {data?.language && (
            <span className="flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full border border-white/10 bg-white/5 text-white/50">
              <span
                className="w-2 h-2 rounded-full"
                style={{ background: getLangColor(data.language) }}
              />
              {data.language}
            </span>
          )}
          {repoMeta?.license && (
            <span className="flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full border border-white/10 bg-white/5 text-white/50">
              <Scale className="w-3 h-3" />
              {repoMeta.license}
            </span>
          )}
          {repoMeta?.topics?.slice(0, 5).map((t) => (
            <span
              key={t}
              className="text-xs px-2.5 py-1 rounded-full border border-violet-500/20 bg-violet-500/8 text-violet-300/70"
            >
              {t}
            </span>
          ))}
        </div>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
        <StatCard
          icon={Star}
          label="Stars"
          value={formatNumber(data?.stars ?? 0)}
        />
        <StatCard
          icon={GitFork}
          label="Forks"
          value={formatNumber(repoMeta?.forks ?? 0)}
        />
        <StatCard
          icon={FileCode2}
          label="Files"
          value={formatNumber(data?.total_files ?? 0)}
          sub="parsed"
        />
        <StatCard
          icon={Hash}
          label="Lines"
          value={formatNumber(data?.total_lines ?? 0)}
          sub="of code"
        />
      </div>

      {isReady && repoMeta?.health_score != null && (
        <div className="p-5 rounded-xl border border-white/8 bg-white/3 mb-6">
          <HealthBar score={repoMeta.health_score} />
          {repoMeta.health_breakdown &&
            Array.isArray(repoMeta.health_breakdown) && (
              <div className="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-3">
                {repoMeta.health_breakdown.map((cat) => (
                  <div key={cat.key} className="text-center">
                    <div
                      className={cn(
                        "text-lg font-semibold",
                        cat.score >= 80
                          ? "text-green-400"
                          : cat.score >= 60
                            ? "text-yellow-400"
                            : "text-red-400",
                      )}
                    >
                      {cat.score}
                    </div>
                    <div className="text-xs text-white/30 capitalize">
                      {cat.label}
                    </div>
                    <div className="text-xs text-white/20 mt-1">
                      {cat.description}
                    </div>
                  </div>
                ))}
              </div>
            )}
        </div>
      )}

      {/* AI summary — streams in early */}
      {data?.ai_summary && (
        <div className="p-5 rounded-xl border border-violet-500/20 bg-violet-500/5 mb-6">
          <div className="flex items-center gap-2 mb-2">
            <div className="w-5 h-5 rounded bg-violet-600/30 flex items-center justify-center">
              <CheckCircle2 className="w-3 h-3 text-violet-400" />
            </div>
            <span className="text-xs font-medium text-violet-300">
              AI summary
            </span>
          </div>
          <p className="text-sm text-white/60 leading-relaxed">
            {data.ai_summary}
          </p>
        </div>
      )}

      {/* Language breakdown */}
      {data?.language_breakdown &&
        Object.keys(data.language_breakdown).length > 0 && (
          <div className="p-5 rounded-xl border border-white/8 bg-white/3 mb-6">
            <h3 className="text-sm font-medium text-white/70 mb-4">
              Language breakdown
            </h3>
            <div className="flex h-2 rounded-full overflow-hidden mb-3 gap-px">
              {Object.entries(data.language_breakdown)
                .sort((a, b) => b[1] - a[1])
                .slice(0, 8)
                .map(([lang, pct]) => (
                  <div
                    key={lang}
                    style={{ width: `${pct}%`, background: getLangColor(lang) }}
                    title={`${lang}: ${pct}%`}
                  />
                ))}
            </div>
            <div className="flex flex-wrap gap-3">
              {Object.entries(data.language_breakdown)
                .sort((a, b) => b[1] - a[1])
                .slice(0, 8)
                .map(([lang, pct]) => (
                  <div key={lang} className="flex items-center gap-1.5">
                    <span
                      className="w-2 h-2 rounded-full"
                      style={{ background: getLangColor(lang) }}
                    />
                    <span className="text-xs text-white/50">{lang}</span>
                    <span className="text-xs text-white/25">{pct}%</span>
                  </div>
                ))}
            </div>
          </div>
        )}

      {/* Last commit */}
      {repoMeta?.analysed_at && (
        <div className="flex items-center gap-2 text-xs text-white/25 mb-8">
          <Calendar className="w-3 h-3" />
          Analysed {timeAgo(repoMeta.analysed_at)}
        </div>
      )}

      {/* Quick actions — only when ready */}
      {isReady && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {[
            {
              label: "Explore code graph",
              desc: "Visual file relationships",
              path: "/graph",
              color: "violet",
            },
            {
              label: "Chat with codebase",
              desc: "Ask anything about the code",
              path: "/chat",
              color: "blue",
            },
            {
              label: "Generate docs",
              desc: "Download full documentation",
              path: "/docs",
              color: "green",
            },
          ].map((action) => (
            <button
              key={action.path}
              onClick={() =>
                router.push(`/repo/${owner}/${name}${action.path}`)
              }
              className="flex items-center justify-between p-4 rounded-xl border border-white/8 bg-white/3 hover:bg-white/5 hover:border-white/15 transition-all group text-left"
            >
              <div>
                <div className="text-sm font-medium text-white/80 mb-0.5">
                  {action.label}
                </div>
                <div className="text-xs text-white/30">{action.desc}</div>
              </div>
              <ArrowRight className="w-4 h-4 text-white/20 group-hover:text-white/50 group-hover:translate-x-0.5 transition-all" />
            </button>
          ))}
        </div>
      )}

      {/* Not ready placeholder */}
      {!isReady && (
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <div className="w-10 h-10 rounded-xl border border-violet-500/30 bg-violet-500/10 flex items-center justify-center mb-3">
            <span className="w-3 h-3 rounded-full bg-violet-400 animate-pulse" />
          </div>
          <p className="text-sm text-white/40">
            Analysis in progress — graph and chat will unlock shortly
          </p>
        </div>
      )}
    </div>
  );
}
