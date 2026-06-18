"use client";

import { useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { getDependencies } from "@/lib/api";
import type { Dependency } from "@/lib/types";

function Loader() {
  return (
    <div className="flex items-center justify-center py-16">
      <span className="w-5 h-5 rounded-full border-2 border-violet-500/30 border-t-violet-500 animate-spin" />
    </div>
  );
}

export default function DepsTab({
  owner,
  name,
}: {
  owner: string;
  name: string;
}) {
  const [data, setData] = useState<{
    dependencies: Dependency[];
    vulnerable_count: number;
  }>({ dependencies: [], vulnerable_count: 0 });
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<"all" | "vuln" | "dev">("all");

  useEffect(() => {
    getDependencies(owner, name).then((r) => {
      setData(r as any);
      setLoading(false);
    });
  }, []);

  if (loading) return <Loader />;

  const filtered = data.dependencies.filter((d) => {
    if (filter === "vuln") return d.has_vulnerability;
    if (filter === "dev") return d.is_dev;
    return true;
  });

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <span className="text-xs text-white/30">
            {data.dependencies.length} packages
          </span>
          {data.vulnerable_count > 0 && (
            <span className="flex items-center gap-1 text-xs text-red-400 bg-red-500/10 border border-red-500/20 px-2 py-0.5 rounded-full">
              <AlertTriangle className="w-3 h-3" />
              {data.vulnerable_count} vulnerable
            </span>
          )}
        </div>
        <div className="flex gap-1">
          {(["all", "vuln", "dev"] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={cn(
                "text-xs px-2.5 py-1 rounded-lg border transition-all capitalize",
                filter === f
                  ? "bg-violet-600 border-violet-500 text-white"
                  : "border-white/8 text-white/40 hover:text-white/70",
              )}
            >
              {f === "vuln" ? "⚠ Vulnerable" : f}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        {filtered.map((dep, i) => (
          <div
            key={i}
            className={cn(
              "p-3 rounded-xl border transition-all",
              dep.has_vulnerability
                ? "border-red-500/30 bg-red-500/5"
                : "border-white/8 bg-white/3",
            )}
          >
            <div className="flex items-start justify-between gap-2 mb-1">
              <div className="flex items-center gap-2 min-w-0">
                <span className="text-sm font-medium text-white/80 truncate">
                  {dep.name}
                </span>
                {dep.version && (
                  <span className="text-[10px] text-white/30 font-mono flex-shrink-0">
                    {dep.version}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-1 flex-shrink-0">
                {dep.is_dev && (
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/8 text-white/30">
                    dev
                  </span>
                )}
                {dep.has_vulnerability ? (
                  <AlertTriangle className="w-3.5 h-3.5 text-red-400" />
                ) : (
                  <CheckCircle2 className="w-3.5 h-3.5 text-green-500/50" />
                )}
              </div>
            </div>
            {dep.ecosystem && (
              <span className="text-[10px] text-white/25">{dep.ecosystem}</span>
            )}
            {dep.ai_purpose && (
              <p className="text-xs text-white/40 mt-1 leading-relaxed">
                {dep.ai_purpose}
              </p>
            )}
            {dep.vuln_details && dep.vuln_details.length > 0 && (
              <div className="mt-2 flex flex-col gap-1">
                {dep.vuln_details.map((cve: any) => (
                  <div
                    key={cve.cve_id}
                    className={cn(
                      "text-[10px] rounded px-2 py-1 flex items-center gap-1 flex-wrap",
                      cve.severity === "critical"
                        ? "text-red-400 bg-red-500/10"
                        : cve.severity === "high"
                          ? "text-orange-400 bg-orange-500/10"
                          : cve.severity === "medium"
                            ? "text-yellow-400 bg-yellow-500/10"
                            : "text-blue-400 bg-blue-500/10",
                    )}
                  >
                    <span className="font-mono">{cve.cve_id}</span>
                    <span className="text-white/20">·</span>
                    <span className="uppercase font-medium">{cve.severity}</span>
                    {cve.cvss_score > 0 && (
                      <span className="text-white/30">({cve.cvss_score})</span>
                    )}
                    {cve.fixed_in && (
                      <span className="text-white/25">fix: {cve.fixed_in}</span>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}