"use client";

import { useEffect, useState } from "react";
import { Route, ChevronRight, ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";
import { getApiRoutes } from "@/lib/api";
import type { ApiRoute } from "@/lib/types";

const METHOD_COLORS: Record<string, string> = {
  GET: "bg-green-500/15 text-green-400 border-green-500/20",
  POST: "bg-blue-500/15 text-blue-400 border-blue-500/20",
  PUT: "bg-yellow-500/15 text-yellow-400 border-yellow-500/20",
  PATCH: "bg-orange-500/15 text-orange-400 border-orange-500/20",
  DELETE: "bg-red-500/15 text-red-400 border-red-500/20",
};

function Loader() {
  return (
    <div className="flex items-center justify-center py-16">
      <span className="w-5 h-5 rounded-full border-2 border-violet-500/30 border-t-violet-500 animate-spin" />
    </div>
  );
}

export default function RoutesTab({
  owner,
  name,
}: {
  owner: string;
  name: string;
}) {
  const [data, setData] = useState<ApiRoute[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [codeOpen, setCodeOpen] = useState<Set<string>>(new Set());
  const [callersOpen, setCallersOpen] = useState<Set<string>>(new Set());

  useEffect(() => {
    getApiRoutes(owner, name).then((r) => {
      setData(r.routes);
      setLoading(false);
    });
  }, []);

  if (loading) return <Loader />;

  if (data.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <Route className="w-8 h-8 text-white/15 mb-3" />
        <p className="text-white/30 text-sm">No API routes detected</p>
        <p className="text-white/20 text-xs mt-1">
          Supported: FastAPI, Express, Django, Flask
        </p>
      </div>
    );
  }

  const toggleRow = (key: string) =>
    setExpanded((prev) => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });

  const toggleCode = (e: React.MouseEvent, key: string) => {
    e.stopPropagation();
    setCodeOpen((prev) => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });
  };

  const toggleCallers = (e: React.MouseEvent, key: string) => {
    e.stopPropagation();
    setCallersOpen((prev) => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });
  };

  return (
    <div className="rounded-xl border border-white/8 overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-white/8 bg-white/3">
            <th className="text-left px-4 py-2.5 text-xs font-medium text-white/40 w-6" />
            <th className="text-left px-4 py-2.5 text-xs font-medium text-white/40">
              Method
            </th>
            <th className="text-left px-4 py-2.5 text-xs font-medium text-white/40">
              Path
            </th>
            <th className="text-left px-4 py-2.5 text-xs font-medium text-white/40">
              Handler
            </th>
            <th className="text-left px-4 py-2.5 text-xs font-medium text-white/40">
              Description
            </th>
          </tr>
        </thead>
        <tbody>
          {data.map((route, i) => {
            const rowKey = `${route.method}:${route.path}:${i}`;
            const isExpanded = expanded.has(rowKey);
            const isCodeOpen = codeOpen.has(rowKey);
            const isCallersOpen = callersOpen.has(rowKey);
            const callers: any[] = (route as any).frontend_callers ?? [];
            const handlerCode: string | null = (route as any).handler_code ?? null;

            return (
              <>
                <tr
                  key={rowKey}
                  onClick={() => toggleRow(rowKey)}
                  className={cn(
                    "border-b border-white/5 cursor-pointer transition-colors",
                    isExpanded ? "bg-white/4" : "hover:bg-white/3",
                  )}
                >
                  <td className="pl-4 py-2.5">
                    <ChevronRight
                      className={cn(
                        "w-3 h-3 text-white/25 transition-transform",
                        isExpanded && "rotate-90",
                      )}
                    />
                  </td>
                  <td className="px-4 py-2.5">
                    <span
                      className={cn(
                        "text-[10px] px-2 py-0.5 rounded border font-mono font-medium",
                        METHOD_COLORS[route.method] ??
                          "bg-white/8 text-white/40 border-white/10",
                      )}
                    >
                      {route.method}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 font-mono text-xs text-white/70">
                    {route.path}
                  </td>
                  <td className="px-4 py-2.5 font-mono text-[10px] text-white/30 truncate max-w-[140px]">
                    {route.handler_function ?? route.handler_file ?? "—"}
                  </td>
                  <td className="px-4 py-2.5 text-xs text-white/40">
                    {route.description ?? "—"}
                  </td>
                </tr>

                {isExpanded && (
                  <tr
                    key={`${rowKey}-detail`}
                    className="border-b border-white/5 bg-white/2"
                  >
                    <td colSpan={5} className="px-4 py-3">
                      <div className="flex flex-col gap-2">

                        {/* Handler source code */}
                        <div className="rounded-lg border border-white/8 overflow-hidden">
                          <button
                            onClick={(e) => toggleCode(e, rowKey)}
                            className="w-full flex items-center justify-between px-3 py-2.5 hover:bg-white/4 transition-colors text-left"
                          >
                            <div className="flex items-center gap-2">
                              <svg
                                className="w-3.5 h-3.5 text-violet-400"
                                viewBox="0 0 24 24"
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="2"
                              >
                                <polyline points="16 18 22 12 16 6" />
                                <polyline points="8 6 2 12 8 18" />
                              </svg>
                              <span className="text-xs font-medium text-white/60">
                                Handler Source Code
                              </span>
                              {route.handler_file && (
                                <span className="text-[10px] font-mono text-white/25 truncate max-w-[300px]">
                                  {route.handler_file}
                                  {route.handler_function
                                    ? ` → ${route.handler_function}`
                                    : ""}
                                </span>
                              )}
                            </div>
                            <ChevronDown
                              className={cn(
                                "w-3 h-3 text-white/30 transition-transform flex-shrink-0",
                                isCodeOpen && "rotate-180",
                              )}
                            />
                          </button>
                          {isCodeOpen && (
                            <div className="border-t border-white/8 bg-[#0d1117]">
                              {handlerCode ? (
                                <pre className="px-4 py-3 text-[11px] font-mono text-green-300/80 overflow-x-auto leading-relaxed whitespace-pre">
                                  {handlerCode}
                                </pre>
                              ) : (
                                <div className="px-4 py-3 text-xs text-white/25 italic">
                                  Source code not available — handler may be
                                  defined in a separate file or use an external
                                  reference.
                                </div>
                              )}
                            </div>
                          )}
                        </div>

                        {/* Frontend callers */}
                        <div className="rounded-lg border border-white/8 overflow-hidden">
                          <button
                            onClick={(e) => toggleCallers(e, rowKey)}
                            className="w-full flex items-center justify-between px-3 py-2.5 hover:bg-white/4 transition-colors text-left"
                          >
                            <div className="flex items-center gap-2">
                              <svg
                                className="w-3.5 h-3.5 text-blue-400"
                                viewBox="0 0 24 24"
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="2"
                              >
                                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                              </svg>
                              <span className="text-xs font-medium text-white/60">
                                Called From Frontend
                              </span>
                              <span
                                className={cn(
                                  "text-[10px] px-1.5 py-0.5 rounded-full font-medium",
                                  callers.length > 0
                                    ? "bg-blue-500/15 text-blue-400 border border-blue-500/20"
                                    : "bg-white/8 text-white/25",
                                )}
                              >
                                {callers.length}{" "}
                                {callers.length === 1 ? "caller" : "callers"}
                              </span>
                            </div>
                            <ChevronDown
                              className={cn(
                                "w-3 h-3 text-white/30 transition-transform flex-shrink-0",
                                isCallersOpen && "rotate-180",
                              )}
                            />
                          </button>
                          {isCallersOpen && (
                            <div className="border-t border-white/8">
                              {callers.length > 0 ? (
                                <div className="divide-y divide-white/5">
                                  {callers.map((caller: any, ci: number) => (
                                    <div
                                      key={ci}
                                      className="px-4 py-2.5 flex flex-col gap-1"
                                    >
                                      <div className="flex items-center gap-2">
                                        <svg
                                          className="w-3 h-3 text-white/25 flex-shrink-0"
                                          viewBox="0 0 24 24"
                                          fill="none"
                                          stroke="currentColor"
                                          strokeWidth="2"
                                        >
                                          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                                          <polyline points="14 2 14 8 20 8" />
                                        </svg>
                                        <span className="font-mono text-[11px] text-blue-300/70 truncate">
                                          {caller.file}
                                        </span>
                                        <span className="text-[10px] text-white/25 flex-shrink-0">
                                          line {caller.line}
                                        </span>
                                      </div>
                                      {caller.snippet && (
                                        <pre className="ml-5 text-[10px] font-mono text-white/35 bg-white/3 rounded px-2 py-1 overflow-x-auto whitespace-pre">
                                          {caller.snippet}
                                        </pre>
                                      )}
                                    </div>
                                  ))}
                                </div>
                              ) : (
                                <div className="px-4 py-3 text-xs text-white/25 italic">
                                  No frontend callers detected — this route may
                                  be called server-side, by external clients, or
                                  via a pattern not yet recognized.
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      </div>
                    </td>
                  </tr>
                )}
              </>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}