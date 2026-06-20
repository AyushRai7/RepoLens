"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { analyzeRepo } from "../lib/api";
import {
  ArrowRight,
  GitBranch,
  MessageSquare,
  FileText,
  Zap,
  BookOpen,
  Network,
} from "lucide-react";
import { FaGithub } from "react-icons/fa";
import { cn } from "../lib/utils";
import Image from "next/image";

const EXAMPLE_REPOS = [
  "https://github.com/tiangolo/fastapi",
  "https://github.com/vercel/next.js",
  "https://github.com/django/django",
  "https://github.com/expressjs/express",
];

const FEATURES = [
  {
    icon: Network,
    title: "Visual code graph",
    desc: "See every file and how they connect — imports, layers, call flows",
  },
  {
    icon: MessageSquare,
    title: "AI chat",
    desc: "Ask anything about the code. Click any file to chat about it specifically",
  },
  {
    icon: FileText,
    title: "Auto documentation",
    desc: "Generate and download full docs for any file or the entire repo",
  },
  {
    icon: GitBranch,
    title: "Commit timeline",
    desc: "Interactive history with AI explanations of every change",
  },
  {
    icon: Zap,
    title: "DB schema & APIs",
    desc: "Auto-extracted ERDs, API routes, and dependency analysis",
  },
  {
    icon: BookOpen,
    title: "Health score",
    desc: "Instant quality score — tests, docs, security, complexity",
  },
];

export default function HomePage() {
  const router = useRouter();
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e: React.FormEvent | null, overrideUrl?: string) {
    if (e) e.preventDefault();
    const repoUrl = overrideUrl || url;
    if (!repoUrl.trim()) return;

    setLoading(true);
    setError("");

    try {
      const result = await analyzeRepo(repoUrl.trim());
      const [owner, name] = result.full_name.split("/");
      router.push(`/repo/${owner}/${name}`);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else if (typeof err === "string") {
        setError(err);
      } else {
        setError("Failed to analyze repository");
      }
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen bg-[#0a0a0f] text-white overflow-hidden">
      {/* Background glow */}
      <div className="fixed inset-0 pointer-events-none">
        <div className="absolute top-[-20%] left-[50%] translate-x-[-50%] w-[800px] h-[500px] bg-violet-600/10 rounded-full blur-[120px]" />
        <div className="absolute bottom-[-10%] left-[20%] w-[400px] h-[300px] bg-blue-600/8 rounded-full blur-[100px]" />
      </div>

      <div className="relative z-10">
        {/* Nav */}
        <nav className="flex items-center justify-between px-6 py-4 border-b border-white/5">
          <div className="flex items-center gap-3">
            <Image
              src="/logo.png"
              alt="RepoLens Logo"
              width={38}
              height={38}
              priority
              className="rounded-lg"
            />

            <span className="text-xl font-bold tracking-tight">
              <span className="text-white">Repo</span>
              <span className="bg-gradient-to-r from-violet-500 via-purple-400 to-blue-400 bg-clip-text text-transparent">
                Lens
              </span>
            </span>
          </div>
          <a
            href="https://github.com"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 text-sm text-white/50 hover:text-white/80 transition-colors"
          >
            <FaGithub className="w-4 h-4" />
            GitHub
          </a>
        </nav>

        {/* Hero */}
        <section className="flex flex-col items-center text-center px-4 pt-24 pb-16">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-violet-500/30 bg-violet-500/10 text-violet-300 text-xs mb-6">
            <Zap className="w-3 h-3" />
            Powered by LangGraph + Groq LLaMA 3.1
          </div>

          <h1 className="text-5xl sm:text-6xl font-bold tracking-tight mb-5 max-w-3xl">
            Understand any{" "}
            <span className="bg-gradient-to-r from-violet-400 to-blue-400 bg-clip-text text-transparent">
              GitHub repo
            </span>{" "}
            instantly
          </h1>

          <p className="text-lg text-white/50 max-w-xl mb-10">
            Stop reading READMEs. Paste a URL and get an interactive code graph,
            AI chat, auto-docs, and deep architecture insights — in seconds.
          </p>

          {/* URL input */}
          <form onSubmit={handleSubmit} className="w-full max-w-2xl mb-4">
            <div
              className={cn(
                "flex items-center gap-2 p-2 rounded-xl border bg-white/5 backdrop-blur-sm transition-all",
                error
                  ? "border-red-500/50"
                  : "border-white/10 focus-within:border-violet-500/50",
              )}
            >
              <FaGithub className="w-5 h-5 text-white/30 ml-2 flex-shrink-0" />
              <input
                type="text"
                value={url}
                onChange={(e) => {
                  setUrl(e.target.value);
                  setError("");
                }}
                placeholder="https://github.com/owner/repository"
                className="flex-1 bg-transparent text-white placeholder:text-white/25 text-sm outline-none py-2"
                disabled={loading}
              />
              <button
                type="submit"
                disabled={loading || !url.trim()}
                className={cn(
                  "flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all",
                  loading || !url.trim()
                    ? "bg-violet-600/40 text-white/40 cursor-not-allowed"
                    : "bg-violet-600 hover:bg-violet-500 text-white cursor-pointer",
                )}
              >
                {loading ? (
                  <>
                    <span className="w-3.5 h-3.5 rounded-full border-2 border-white/30 border-t-white animate-spin" />
                    Analyzing...
                  </>
                ) : (
                  <>
                    Explore
                    <ArrowRight className="w-3.5 h-3.5" />
                  </>
                )}
              </button>
            </div>
            {error && (
              <p className="text-red-400 text-xs mt-2 text-left pl-2">
                {error}
              </p>
            )}
          </form>

          {/* Example repos */}
          <div className="flex flex-wrap justify-center gap-2">
            <span className="text-xs text-white/30">Try:</span>
            {EXAMPLE_REPOS.map((repo) => {
              const short = repo.replace("https://github.com/", "");
              return (
                <button
                  key={repo}
                  onClick={() => {
                    setUrl(repo);
                    handleSubmit(null, repo);
                  }}
                  disabled={loading}
                  className="text-xs px-3 py-1 rounded-full border border-white/10 text-white/40 hover:text-white/70 hover:border-white/20 transition-all disabled:opacity-30"
                >
                  {short}
                </button>
              );
            })}
          </div>
        </section>

        {/* Features grid */}
        <section className="max-w-5xl mx-auto px-6 pb-24">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {FEATURES.map((feature) => (
              <div
                key={feature.title}
                className="p-5 rounded-xl border border-white/8 bg-white/3 hover:bg-white/5 hover:border-white/12 transition-all group"
              >
                <div className="w-8 h-8 rounded-lg bg-violet-600/20 flex items-center justify-center mb-3 group-hover:bg-violet-600/30 transition-colors">
                  <feature.icon className="w-4 h-4 text-violet-400" />
                </div>
                <h3 className="font-medium text-white/90 text-sm mb-1">
                  {feature.title}
                </h3>
                <p className="text-xs text-white/40 leading-relaxed">
                  {feature.desc}
                </p>
              </div>
            ))}
          </div>
        </section>
      </div>
    </main>
  );
}
