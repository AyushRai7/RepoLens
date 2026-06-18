"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import { useRepoStore } from "@/store/repoStore";
import {
  generateDiagram as fetchDiagram,
  clearDiagramCache,
  DiagramPendingError,
} from "@/lib/api";
import { cn } from "@/lib/utils";
import type { DiagramResponse } from "@/lib/types";
import { Loader2 } from "lucide-react";

import MermaidDiagram from "@/components/graph/MermaidDiagram";
import FileDetailPanel from "@/components/graph/FileDetailPanel";
import DiagramToolbar from "@/components/graph/DiagramToolbar";
import {
  DiagramIdleState,
  DiagramLoadingState,
  DiagramErrorState,
} from "@/components/graph/DiagramStatusViews";

type DiagramState =
  | { status: "idle" }
  | { status: "loading" }
  | {
      status: "ready";
      mermaid: string;
      labelMap: Record<string, string>;
      cached: boolean;
    }
  | { status: "error"; message: string };

export default function GraphPage() {
  const params = useParams<{ owner: string; name: string }>();
  const { owner, name } = params;
  const { graphData, selectedFile, setSelectedFile } = useRepoStore();

  const [diagram, setDiagram] = useState<DiagramState>({ status: "idle" });

  const generateDiagram = useCallback(
    async (force = false) => {
      setDiagram({ status: "loading" });
      try {
        if (force) {
          await clearDiagramCache(owner, name);
        }
        const data: DiagramResponse = await fetchDiagram(owner, name);
        setDiagram({
          status: "ready",
          mermaid: data.mermaid,
          labelMap: data.label_map,
          cached: data.cached,
        });
      } catch (e: any) {
        const message =
          e instanceof DiagramPendingError
            ? e.message
            : (e?.message ?? "Network error");
        setDiagram({ status: "error", message });
      }
    },
    [owner, name],
  );

  useEffect(() => {
    if (graphData) {
      generateDiagram();
    }
  }, [graphData]);

  function downloadMermaid() {
    if (diagram.status !== "ready") return;
    const blob = new Blob([diagram.mermaid], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${owner}-${name}-architecture.mmd`;
    a.click();
    URL.revokeObjectURL(url);
  }

  if (!graphData) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-130px)] text-white/30">
        <div className="text-center">
          <Loader2 className="w-6 h-6 text-violet-500/40 animate-spin mx-auto mb-3" />
          <p className="text-sm">Loading repository data…</p>
        </div>
      </div>
    );
  }

  return (
    <div className="relative flex flex-col w-full h-[calc(100vh-130px)] bg-[#08080f]">
      <DiagramToolbar
        totalFiles={graphData.nodes.length}
        cached={diagram.status === "ready" ? diagram.cached : false}
        ready={diagram.status === "ready"}
        onDownload={downloadMermaid}
        onRegenerate={() => generateDiagram(true)}
      />

      <div
        className={cn(
          "flex-1 relative overflow-hidden transition-all",
          selectedFile ? "mr-80" : "",
        )}
      >
        {diagram.status === "idle" && (
          <DiagramIdleState onGenerate={() => generateDiagram()} />
        )}
        {diagram.status === "loading" && <DiagramLoadingState />}
        {diagram.status === "error" && (
          <DiagramErrorState
            message={diagram.message}
            onRetry={() => generateDiagram()}
          />
        )}
        {diagram.status === "ready" && (
          <MermaidDiagram
            mermaid={diagram.mermaid}
            labelMap={diagram.labelMap}
            onNodeClick={(path) =>
              setSelectedFile(selectedFile === path ? null : path)
            }
            selectedFile={selectedFile}
          />
        )}
      </div>

      {selectedFile && (
        <FileDetailPanel
          owner={owner}
          name={name}
          path={selectedFile}
          onClose={() => setSelectedFile(null)}
        />
      )}
    </div>
  );
}
