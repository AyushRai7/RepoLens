import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatNumber(num: number): string {
  if (num >= 1_000_000_000) {
    return `${(num / 1_000_000_000).toFixed(1)}B`;
  }

  if (num >= 1_000_000) {
    return `${(num / 1_000_000).toFixed(1)}M`;
  }

  if (num >= 1_000) {
    return `${(num / 1_000).toFixed(1)}K`;
  }

  return num.toString();
}

export function timeAgo(dateString: string): string {
  const date = new Date(dateString);
  const seconds = Math.floor((Date.now() - date.getTime()) / 1000);

  const intervals = [
    { label: "year", seconds: 31536000 },
    { label: "month", seconds: 2592000 },
    { label: "day", seconds: 86400 },
    { label: "hour", seconds: 3600 },
    { label: "minute", seconds: 60 },
  ];

  for (const interval of intervals) {
    const count = Math.floor(seconds / interval.seconds);

    if (count >= 1) {
      return `${count} ${interval.label}${count > 1 ? "s" : ""} ago`;
    }
  }

  return "just now";
}

export function getLangColor(language?: string): string {
  const colors: Record<string, string> = {
    TypeScript: "#3178C6",
    JavaScript: "#F7DF1E",
    Python: "#3776AB",
    Java: "#ED8B00",
    Go: "#00ADD8",
    Rust: "#DEA584",
    C: "#A8B9CC",
    "C++": "#00599C",
    "C#": "#239120",
    PHP: "#777BB4",
    Ruby: "#CC342D",
    Swift: "#FA7343",
    Kotlin: "#7F52FF",
    Dart: "#0175C2",
    HTML: "#E34F26",
    CSS: "#1572B6",
    SCSS: "#CC6699",
    Vue: "#4FC08D",
    Svelte: "#FF3E00",
    Shell: "#89E051",
  };

  return colors[language || ""] || "#6B7280";
}

export const LAYER_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  route: {
    bg: "rgba(79, 142, 247, 0.15)",
    text: "#4f8ef7",
    border: "rgba(79, 142, 247, 0.35)",
  },
  service: {
    bg: "rgba(62, 207, 142, 0.15)",
    text: "#3ecf8e",
    border: "rgba(62, 207, 142, 0.35)",
  },
  model: {
    bg: "rgba(245, 166, 35, 0.15)",
    text: "#f5a623",
    border: "rgba(245, 166, 35, 0.35)",
  },
  db: {
    bg: "rgba(232, 121, 160, 0.15)",
    text: "#e879a0",
    border: "rgba(232, 121, 160, 0.35)",
  },
  util: {
    bg: "rgba(45, 212, 191, 0.15)",
    text: "#2dd4bf",
    border: "rgba(45, 212, 191, 0.35)",
  },
  config: {
    bg: "rgba(124, 93, 249, 0.15)",
    text: "#7c5df9",
    border: "rgba(124, 93, 249, 0.35)",
  },
  test: {
    bg: "rgba(240, 107, 107, 0.15)",
    text: "#f06b6b",
    border: "rgba(240, 107, 107, 0.35)",
  },
  ui: {
    bg: "rgba(167, 139, 250, 0.15)",
    text: "#a78bfa",
    border: "rgba(167, 139, 250, 0.35)",
  },
  other: {
    bg: "rgba(107, 114, 128, 0.15)",
    text: "#6b7280",
    border: "rgba(107, 114, 128, 0.35)",
  },
}