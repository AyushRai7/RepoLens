"use client";

import { useEffect, useRef } from "react";
import {
  Download,
  Braces,
  Share2,
  Sparkles,
  FileText,
  CheckCircle2,
  XCircle,
  Loader2,
  Clock,
} from "lucide-react";
import { cn } from "@/lib/utils";

// ── Types ──────────────────────────────────────────────────────────────────────

export type StageStatus = "pending" | "running" | "done" | "error";

export interface PipelineStage {
  key: string;
  label: string;
  /** Short description shown in tooltip / detail */
  description?: string;
  status: StageStatus;
  /** 0–100, meaningful only when status is "running" */
  progress?: number;
  /** Elapsed or estimated seconds */
  durationMs?: number;
  errorMessage?: string;
}

export interface PipelineState {
  stages: PipelineStage[];
  /** Overall status: running while any stage is running, done when all done */
  overall: "idle" | "running" | "done" | "error";
  startedAt?: string;
  completedAt?: string;
}

interface PipelineBarProps {
  pipeline: PipelineState;
  /** Compact single-row variant vs expanded multi-row */
  variant?: "compact" | "expanded";
  className?: string;
}

// ── Helpers ────────────────────────────────────────────────────────────────────

const STAGE_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  clone: Download,
  parse: Braces,
  graph: Share2,
  embed: Sparkles,
  docs: FileText,
};

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`;
  const m = Math.floor(ms / 60_000);
  const s = Math.round((ms % 60_000) / 1000);
  return `${m}m ${s}s`;
}

// ── Spinner ────────────────────────────────────────────────────────────────────

function SpinnerDot() {
  return (
    <span className="relative inline-flex h-2 w-2">
      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75" />
      <span className="relative inline-flex rounded-full h-2 w-2 bg-primary" />
    </span>
  );
}

// ── Status Icon ────────────────────────────────────────────────────────────────

function StatusIcon({ status, className }: { status: StageStatus; className?: string }) {
  switch (status) {
    case "done":
      return <CheckCircle2 className={cn("text-green-500", className)} />;
    case "error":
      return <XCircle className={cn("text-red-500", className)} />;
    case "running":
      return <Loader2 className={cn("text-primary animate-spin", className)} />;
    default:
      return <Clock className={cn("text-muted-foreground/40", className)} />;
  }
}

// ── Compact Stage Dot ──────────────────────────────────────────────────────────

function StageDot({ stage, isLast }: { stage: PipelineStage; isLast: boolean }) {
  const Icon = STAGE_ICONS[stage.key] ?? FileText;

  const dotColor =
    stage.status === "done"
      ? "bg-green-500 border-green-500"
      : stage.status === "error"
      ? "bg-red-500 border-red-500"
      : stage.status === "running"
      ? "bg-primary border-primary"
      : "bg-muted border-border";

  const lineColor =
    stage.status === "done"
      ? "bg-green-500"
      : stage.status === "running"
      ? "bg-gradient-to-r from-primary to-muted"
      : "bg-border";

  return (
    <div className="flex items-center">
      <div className="relative group flex flex-col items-center">
        {/* Dot */}
        <div
          className={cn(
            "h-8 w-8 rounded-full border-2 flex items-center justify-center transition-all duration-300",
            dotColor,
            stage.status === "running" && "shadow-[0_0_12px_2px_hsl(var(--primary)/0.4)]"
          )}
          aria-label={`${stage.label}: ${stage.status}`}
        >
          {stage.status === "running" ? (
            <Loader2 className="h-4 w-4 text-primary-foreground animate-spin" />
          ) : (
            <Icon
              className={cn(
                "h-4 w-4",
                stage.status === "done" || stage.status === "error"
                  ? "text-white"
                  : "text-muted-foreground"
              )}
            />
          )}
        </div>

        {/* Label */}
        <span
          className={cn(
            "mt-1.5 text-[10px] font-medium whitespace-nowrap",
            stage.status === "done"
              ? "text-green-600 dark:text-green-400"
              : stage.status === "error"
              ? "text-red-600 dark:text-red-400"
              : stage.status === "running"
              ? "text-primary"
              : "text-muted-foreground"
          )}
        >
          {stage.label}
        </span>

        {/* Tooltip on hover */}
        {stage.description && (
          <div className="pointer-events-none absolute bottom-full mb-2 z-10 hidden group-hover:flex flex-col items-center">
            <div className="rounded-lg bg-popover border border-border shadow-md px-3 py-2 text-xs text-foreground max-w-[160px] text-center">
              <p className="font-medium">{stage.label}</p>
              <p className="text-muted-foreground mt-0.5">{stage.description}</p>
              {stage.durationMs !== undefined && (
                <p className="mt-1 font-mono text-primary">{formatDuration(stage.durationMs)}</p>
              )}
              {stage.errorMessage && (
                <p className="mt-1 text-red-500">{stage.errorMessage}</p>
              )}
            </div>
            <div className="h-1.5 w-1.5 rotate-45 bg-popover border-r border-b border-border -mt-1" />
          </div>
        )}
      </div>

      {/* Connector line */}
      {!isLast && (
        <div className={cn("h-[2px] w-10 mx-1 flex-shrink-0 rounded transition-all duration-500", lineColor)} />
      )}
    </div>
  );
}

// ── Expanded Stage Row ─────────────────────────────────────────────────────────

function StageRow({ stage }: { stage: PipelineStage }) {
  const Icon = STAGE_ICONS[stage.key] ?? FileText;

  return (
    <div
      className={cn(
        "flex items-center gap-3 rounded-xl border px-4 py-3 transition-all duration-300",
        stage.status === "running"
          ? "border-primary/30 bg-primary/5 shadow-[0_0_0_1px_hsl(var(--primary)/0.15)]"
          : stage.status === "done"
          ? "border-green-200 dark:border-green-900/50 bg-green-50/50 dark:bg-green-950/20"
          : stage.status === "error"
          ? "border-red-200 dark:border-red-900/50 bg-red-50/50 dark:bg-red-950/20"
          : "border-border bg-muted/20"
      )}
      role="status"
      aria-label={`${stage.label}: ${stage.status}`}
    >
      {/* Stage icon */}
      <div
        className={cn(
          "h-8 w-8 rounded-lg flex items-center justify-center flex-shrink-0",
          stage.status === "running"
            ? "bg-primary/10"
            : stage.status === "done"
            ? "bg-green-100 dark:bg-green-950/60"
            : stage.status === "error"
            ? "bg-red-100 dark:bg-red-950/60"
            : "bg-muted"
        )}
      >
        <Icon
          className={cn(
            "h-4 w-4",
            stage.status === "running"
              ? "text-primary"
              : stage.status === "done"
              ? "text-green-600 dark:text-green-400"
              : stage.status === "error"
              ? "text-red-600 dark:text-red-400"
              : "text-muted-foreground"
          )}
        />
      </div>

      {/* Label + description */}
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <p className="text-sm font-medium text-foreground">{stage.label}</p>
          {stage.status === "running" && <SpinnerDot />}
        </div>
        {stage.description && (
          <p className="text-xs text-muted-foreground mt-0.5 truncate">
            {stage.errorMessage ?? stage.description}
          </p>
        )}
        {/* Mini progress bar when running */}
        {stage.status === "running" && stage.progress !== undefined && (
          <div className="mt-2 h-1 w-full overflow-hidden rounded-full bg-primary/20">
            <div
              className="h-full rounded-full bg-primary transition-all duration-300"
              style={{ width: `${stage.progress}%` }}
            />
          </div>
        )}
      </div>

      {/* Right side: status icon + duration */}
      <div className="flex items-center gap-2 flex-shrink-0">
        {stage.durationMs !== undefined && stage.status === "done" && (
          <span className="text-xs text-muted-foreground font-mono">
            {formatDuration(stage.durationMs)}
          </span>
        )}
        <StatusIcon status={stage.status} className="h-4 w-4" />
      </div>
    </div>
  );
}

// ── Overall Progress Bar ───────────────────────────────────────────────────────

function OverallProgress({ stages }: { stages: PipelineStage[] }) {
  const doneCount = stages.filter((s) => s.status === "done").length;
  const errorCount = stages.filter((s) => s.status === "error").length;
  const total = stages.length;
  const pct = Math.round(((doneCount + errorCount) / total) * 100);

  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs text-muted-foreground">
        <span>
          {doneCount} / {total} stages complete
        </span>
        <span className="tabular-nums">{pct}%</span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
        <div
          className="h-full rounded-full bg-primary transition-all duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

// ── Main Component ─────────────────────────────────────────────────────────────

export function PipelineBar({
  pipeline,
  variant = "expanded",
  className,
}: PipelineBarProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to the running stage in compact mode
  useEffect(() => {
    if (variant !== "compact" || !scrollRef.current) return;
    const running = scrollRef.current.querySelector("[data-running='true']");
    if (running) {
      running.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "center" });
    }
  }, [pipeline.stages, variant]);

  const isRunning = pipeline.overall === "running";
  const isDone = pipeline.overall === "done";
  const isError = pipeline.overall === "error";

  return (
    <div className={cn("rounded-2xl border border-border bg-card shadow-sm", className)}>
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3.5 border-b border-border/60">
        <div className="flex items-center gap-2.5">
          {isRunning && <SpinnerDot />}
          {isDone && <CheckCircle2 className="h-4 w-4 text-green-500" />}
          {isError && <XCircle className="h-4 w-4 text-red-500" />}
          {!isRunning && !isDone && !isError && (
            <Clock className="h-4 w-4 text-muted-foreground" />
          )}
          <h3 className="text-sm font-semibold text-foreground">
            {isRunning
              ? "Analyzing repository…"
              : isDone
              ? "Analysis complete"
              : isError
              ? "Analysis failed"
              : "Analysis pipeline"}
          </h3>
        </div>
        {pipeline.startedAt && (
          <span className="text-xs text-muted-foreground">
            Started <time dateTime={pipeline.startedAt}>{new Date(pipeline.startedAt).toLocaleTimeString()}</time>
          </span>
        )}
      </div>

      <div className="p-5 space-y-5">
        {/* Overall progress */}
        {(isRunning || isDone || isError) && (
          <OverallProgress stages={pipeline.stages} />
        )}

        {/* Stages */}
        {variant === "compact" ? (
          <div
            ref={scrollRef}
            className="flex items-start overflow-x-auto pb-2 scrollbar-none"
            role="list"
            aria-label="Pipeline stages"
          >
            {pipeline.stages.map((stage, i) => (
              <div
                key={stage.key}
                role="listitem"
                data-running={stage.status === "running" ? "true" : undefined}
              >
                <StageDot stage={stage} isLast={i === pipeline.stages.length - 1} />
              </div>
            ))}
          </div>
        ) : (
          <div
            className="space-y-2"
            role="list"
            aria-label="Pipeline stages"
          >
            {pipeline.stages.map((stage) => (
              <div key={stage.key} role="listitem">
                <StageRow stage={stage} />
              </div>
            ))}
          </div>
        )}

        {/* Completion footer */}
        {isDone && pipeline.completedAt && (
          <p className="text-xs text-muted-foreground text-center">
            Completed at{" "}
            <time dateTime={pipeline.completedAt}>
              {new Date(pipeline.completedAt).toLocaleTimeString()}
            </time>
          </p>
        )}
      </div>
    </div>
  );
}

export default PipelineBar;