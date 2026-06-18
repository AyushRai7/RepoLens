"use client";

import { useEffect, useRef, useState } from "react";
import {
  ShieldCheck,
  BookOpen,
  GitCommitHorizontal,
  TestTube2,
  Package,
  Activity,
  TrendingUp,
  TrendingDown,
  Minus,
  Info,
} from "lucide-react";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

// ── Types ──────────────────────────────────────────────────────────────────────

export interface HealthCategory {
  key: string;
  label: string;
  score: number;        // 0–100
  weight: number;       // 0–1, weights must sum to 1
  description: string;
}

export interface HealthScoreData {
  overall: number;             // 0–100
  grade: "A+" | "A" | "B+" | "B" | "C+" | "C" | "D" | "F";
  trend: "up" | "down" | "stable";
  categories: HealthCategory[];
  generatedAt: string;         // ISO date
}

interface HealthScoreProps {
  data: HealthScoreData;
  /** Size of the SVG ring in px. Default 160 */
  ringSize?: number;
  className?: string;
}

// ── Helpers ────────────────────────────────────────────────────────────────────

const CATEGORY_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  documentation: BookOpen,
  commits: GitCommitHorizontal,
  tests: TestTube2,
  dependencies: Package,
  security: ShieldCheck,
  activity: Activity,
};

function scoreColor(score: number): string {
  if (score >= 85) return "#22c55e"; // green-500
  if (score >= 70) return "#84cc16"; // lime-500
  if (score >= 55) return "#eab308"; // yellow-500
  if (score >= 40) return "#f97316"; // orange-500
  return "#ef4444";                  // red-500
}

function gradeColor(grade: string): string {
  if (grade.startsWith("A")) return "#22c55e";
  if (grade.startsWith("B")) return "#84cc16";
  if (grade.startsWith("C")) return "#eab308";
  if (grade === "D") return "#f97316";
  return "#ef4444";
}

function useAnimatedValue(target: number, duration = 1200): number {
  const [value, setValue] = useState(0);
  const raf = useRef<number | null>(null);
  const start = useRef<number | null>(null);

  useEffect(() => {
    start.current = null;
    const animate = (ts: number) => {
      if (start.current === null) start.current = ts;
      const progress = Math.min((ts - start.current) / duration, 1);
      // ease-out-cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      setValue(Math.round(eased * target));
      if (progress < 1) raf.current = requestAnimationFrame(animate);
    };
    raf.current = requestAnimationFrame(animate);
    return () => { if (raf.current) cancelAnimationFrame(raf.current); };
  }, [target, duration]);

  return value;
}

// ── Ring SVG ───────────────────────────────────────────────────────────────────

function ScoreRing({
  score,
  size = 160,
  grade,
}: {
  score: number;
  size?: number;
  grade: string;
}) {
  const animatedScore = useAnimatedValue(score);
  const strokeWidth = size * 0.075;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const cx = size / 2;
  const cy = size / 2;

  // We only draw 270° arc (start top-left, end top-right, leaving 90° gap at bottom)
  const arcFraction = 0.75;
  const dashArray = circumference * arcFraction;
  const dashOffset = circumference * arcFraction * (1 - animatedScore / 100);

  // rotate so arc starts at ~225° (bottom-left) and ends at ~135° (bottom-right)
  const rotation = 135;
  const color = scoreColor(animatedScore);

  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        className="rotate-0"
        aria-label={`Health score ring: ${score}`}
        role="img"
      >
        {/* Track */}
        <circle
          cx={cx}
          cy={cy}
          r={radius}
          fill="none"
          stroke="currentColor"
          strokeWidth={strokeWidth}
          strokeDasharray={`${dashArray} ${circumference}`}
          strokeLinecap="round"
          className="text-muted/30"
          style={{ transform: `rotate(${rotation}deg)`, transformOrigin: "50% 50%" }}
        />
        {/* Value arc */}
        <circle
          cx={cx}
          cy={cy}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={strokeWidth}
          strokeDasharray={`${dashArray} ${circumference}`}
          strokeDashoffset={dashOffset}
          strokeLinecap="round"
          style={{
            transform: `rotate(${rotation}deg)`,
            transformOrigin: "50% 50%",
            transition: "stroke-dashoffset 0.05s linear",
            filter: `drop-shadow(0 0 ${strokeWidth * 0.6}px ${color}66)`,
          }}
        />
        {/* Glow dot at tip */}
        <circle
          r={strokeWidth * 0.7}
          fill={color}
          style={{
            filter: `drop-shadow(0 0 4px ${color})`,
            // position the dot at the arc tip — approximate for animated value
            display: animatedScore > 2 ? "block" : "none",
          }}
        >
          {/* We compute tip coords via animateMotion on a path — simpler: just center it */}
          <animateMotion
            dur="0s"
            fill="freeze"
            path={`M ${cx} ${cy - radius}`}
          />
        </circle>
      </svg>

      {/* Center text */}
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span
          className="text-4xl font-black tabular-nums leading-none"
          style={{ color }}
        >
          {animatedScore}
        </span>
        <span
          className="mt-1 text-sm font-bold tracking-wider"
          style={{ color: gradeColor(grade) }}
        >
          {grade}
        </span>
      </div>
    </div>
  );
}

// ── Category Bar ───────────────────────────────────────────────────────────────

function CategoryBar({
  category,
  delay = 0,
}: {
  category: HealthCategory;
  delay?: number;
}) {
  const [width, setWidth] = useState(0);
  const Icon = CATEGORY_ICONS[category.key] ?? Activity;
  const color = scoreColor(category.score);

  useEffect(() => {
    const t = setTimeout(() => setWidth(category.score), delay);
    return () => clearTimeout(t);
  }, [category.score, delay]);

  return (
    <TooltipProvider delayDuration={200}>
      <Tooltip>
        <TooltipTrigger asChild>
          <div className="group space-y-1.5 cursor-default">
            <div className="flex items-center justify-between text-xs">
              <span className="flex items-center gap-1.5 font-medium text-foreground">
                <Icon className="h-3.5 w-3.5 text-muted-foreground group-hover:text-foreground transition-colors" />
                {category.label}
              </span>
              <span
                className="tabular-nums font-semibold"
                style={{ color }}
              >
                {category.score}
              </span>
            </div>
            <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
              <div
                className="h-full rounded-full transition-all duration-700 ease-out"
                style={{
                  width: `${width}%`,
                  background: color,
                  boxShadow: `0 0 6px ${color}66`,
                  transitionDelay: `${delay}ms`,
                }}
              />
            </div>
          </div>
        </TooltipTrigger>
        <TooltipContent side="top" className="max-w-[220px] text-xs">
          <p>{category.description}</p>
          <p className="mt-1 text-muted-foreground">Weight: {(category.weight * 100).toFixed(0)}%</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

// ── Trend Icon ─────────────────────────────────────────────────────────────────

function TrendBadge({ trend }: { trend: "up" | "down" | "stable" }) {
  if (trend === "up") return (
    <span className="inline-flex items-center gap-1 rounded-full bg-green-100 dark:bg-green-950/60 px-2 py-0.5 text-xs font-medium text-green-700 dark:text-green-400">
      <TrendingUp className="h-3 w-3" /> Improving
    </span>
  );
  if (trend === "down") return (
    <span className="inline-flex items-center gap-1 rounded-full bg-red-100 dark:bg-red-950/60 px-2 py-0.5 text-xs font-medium text-red-700 dark:text-red-400">
      <TrendingDown className="h-3 w-3" /> Declining
    </span>
  );
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground">
      <Minus className="h-3 w-3" /> Stable
    </span>
  );
}

// ── Main Component ─────────────────────────────────────────────────────────────

export function HealthScore({ data, ringSize = 160, className }: HealthScoreProps) {
  return (
    <div
      className={cn(
        "rounded-2xl border border-border bg-card shadow-sm p-6 space-y-6",
        className
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ShieldCheck className="h-4 w-4 text-muted-foreground" />
          <h3 className="text-sm font-semibold text-foreground">Repo Health</h3>
          <TooltipProvider delayDuration={200}>
            <Tooltip>
              <TooltipTrigger asChild>
                <button className="text-muted-foreground hover:text-foreground transition-colors" aria-label="Info">
                  <Info className="h-3.5 w-3.5" />
                </button>
              </TooltipTrigger>
              <TooltipContent className="max-w-[240px] text-xs">
                Overall health is a weighted composite of documentation, commit activity,
                test coverage, dependency freshness, security, and community activity.
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>
        <TrendBadge trend={data.trend} />
      </div>

      {/* Ring + Categories layout */}
      <div className="flex gap-6 items-start">
        {/* Ring */}
        <div className="flex-shrink-0 flex flex-col items-center gap-2">
          <ScoreRing score={data.overall} size={ringSize} grade={data.grade} />
          <p className="text-xs text-muted-foreground text-center leading-tight">
            Overall Score
          </p>
        </div>

        {/* Category bars */}
        <div className="flex-1 min-w-0 space-y-3">
          {data.categories.map((cat, i) => (
            <CategoryBar
              key={cat.key}
              category={cat}
              delay={i * 80 + 300}
            />
          ))}
        </div>
      </div>

      {/* Footer */}
      <p className="text-xs text-muted-foreground border-t border-border/60 pt-4">
        Calculated{" "}
        <time dateTime={data.generatedAt}>
          {new Date(data.generatedAt).toLocaleString()}
        </time>
      </p>
    </div>
  );
}

export default HealthScore;