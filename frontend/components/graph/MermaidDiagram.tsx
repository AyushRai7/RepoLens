"use client";

import { useEffect, useRef, useState } from "react";
import { Loader2, AlertCircle, ZoomIn, ZoomOut, Maximize2 } from "lucide-react";

interface MermaidDiagramProps {
  mermaid: string;
  labelMap: Record<string, string>; // exact rendered node label -> real file path
  onNodeClick: (path: string) => void;
  selectedFile: string | null;
}

function getNodeLabelText(el: Element): string {
  const textEl = el.querySelector("span, p, div, foreignObject");
  return textEl?.textContent?.trim() ?? "";
}

export default function MermaidDiagram({ mermaid, labelMap, onNodeClick, selectedFile }: MermaidDiagramProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [rendered, setRendered] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const isPanning = useRef(false);
  const panStart = useRef({ x: 0, y: 0 });

  useEffect(() => {
    if (!mermaid || !containerRef.current) return;
    setRendered(false);
    setError(null);
    let cancelled = false;

    async function render() {
      try {
        const mermaidLib = (await import("mermaid")).default;
        mermaidLib.initialize({
          startOnLoad: false,
          theme: "dark",
          darkMode: true,
          themeVariables: {
            background: "#08080f",
            mainBkg: "#111118",
            nodeBorder: "#ffffff20",
            lineColor: "#ffffff40",
            edgeLabelBackground: "#0d0d14",
            primaryColor: "#1a1a28",
            primaryTextColor: "#e2e8f0",
            primaryBorderColor: "#ffffff20",
            clusterBkg: "#0f0f1a",
            clusterBorder: "#ffffff15",
            titleColor: "#94a3b8",
            fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
            fontSize: "13px",
          },
          flowchart: {
            htmlLabels: true,
            curve: "basis",
            padding: 20,
            nodeSpacing: 50,
            rankSpacing: 80,
            diagramPadding: 20,
          },
        });

        if (!containerRef.current || cancelled) return;

        const id = `mermaid-${Date.now()}`;
        const { svg } = await mermaidLib.render(id, mermaid);
        if (cancelled || !containerRef.current) return;

        containerRef.current.innerHTML = svg;
        const svgEl = containerRef.current.querySelector("svg") as SVGSVGElement;
        if (!svgEl) return;

        svgEl.style.width = "100%";
        svgEl.style.height = "100%";
        svgEl.style.maxWidth = "none";
        svgEl.removeAttribute("width");
        svgEl.removeAttribute("height");

        const nodeEls = svgEl.querySelectorAll(".node");
        nodeEls.forEach((el) => {
          const filePath = labelMap[getNodeLabelText(el)];
          if (!filePath) return; // not a recognised file node — leave inert

          (el as HTMLElement).style.cursor = "pointer";
          (el as HTMLElement).title = filePath;

          el.addEventListener("click", (e) => {
            e.stopPropagation();
            onNodeClick(filePath);
          });

          el.addEventListener("mouseenter", () => {
            (el as HTMLElement).style.filter = "brightness(1.3)";
            const existing = document.getElementById("mermaid-tooltip");
            if (existing) existing.remove();
            const tt = document.createElement("div");
            tt.id = "mermaid-tooltip";
            tt.style.cssText = `
              position: fixed; z-index: 9999; pointer-events: none;
              background: #0d0d18; border: 1px solid rgba(255,255,255,0.15);
              border-radius: 8px; padding: 6px 10px;
              font-family: ui-monospace, monospace; font-size: 11px;
              color: #a78bfa; max-width: 300px; word-break: break-all;
              box-shadow: 0 4px 20px rgba(0,0,0,0.6);
            `;
            tt.textContent = filePath;
            document.body.appendChild(tt);

            const move = (ev: MouseEvent) => {
              tt.style.left = `${ev.clientX + 12}px`;
              tt.style.top = `${ev.clientY - 8}px`;
            };
            window.addEventListener("mousemove", move);
            (el as any)._moveHandler = move;
          });

          el.addEventListener("mouseleave", () => {
            (el as HTMLElement).style.filter = "";
            const tt = document.getElementById("mermaid-tooltip");
            if (tt) tt.remove();
            if ((el as any)._moveHandler) {
              window.removeEventListener("mousemove", (el as any)._moveHandler);
            }
          });
        });

        // Highlight selected file node — same exact-text lookup
        if (selectedFile) {
          nodeEls.forEach((el) => {
            if (labelMap[getNodeLabelText(el)] !== selectedFile) return;
            const rect = el.querySelector("rect, circle, polygon");
            if (rect) {
              (rect as SVGElement).style.filter = "drop-shadow(0 0 8px #7c3aed)";
              (rect as SVGElement).style.stroke = "#7c3aed";
              (rect as SVGElement).style.strokeWidth = "2";
            }
          });
        }

        setRendered(true);
      } catch (err: any) {
        setError(err?.message ?? "Failed to render diagram");
      }
    }

    render();
    return () => { cancelled = true; };
  }, [mermaid, labelMap, selectedFile]);

  function handleWheel(e: React.WheelEvent) {
    e.preventDefault();
    const delta = e.deltaY > 0 ? 0.9 : 1.1;
    setZoom((z) => Math.min(Math.max(z * delta, 0.2), 4));
  }
  function handleMouseDown(e: React.MouseEvent) {
    if (e.button !== 0) return;
    isPanning.current = true;
    panStart.current = { x: e.clientX - pan.x, y: e.clientY - pan.y };
  }
  function handleMouseMove(e: React.MouseEvent) {
    if (!isPanning.current) return;
    setPan({ x: e.clientX - panStart.current.x, y: e.clientY - panStart.current.y });
  }
  function handleMouseUp() { isPanning.current = false; }
  function resetView() { setZoom(1); setPan({ x: 0, y: 0 }); }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3 text-white/40">
        <AlertCircle className="w-8 h-8 text-red-400/50" />
        <p className="text-sm">Failed to render diagram</p>
        <pre className="text-[10px] text-white/25 max-w-md text-center">{error}</pre>
      </div>
    );
  }

  return (
    <div className="relative w-full h-full overflow-hidden bg-[#08080f]">
      <div
        className="w-full h-full"
        style={{ cursor: isPanning.current ? "grabbing" : "grab" }}
        onWheel={handleWheel}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
      >
        <div
          style={{
            transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
            transformOrigin: "center center",
            transition: isPanning.current ? "none" : "transform 0.1s ease",
            width: "100%",
            height: "100%",
          }}
        >
          <div ref={containerRef} className="w-full h-full flex items-center justify-center p-8" />
        </div>
      </div>

      {!rendered && !error && (
        <div className="absolute inset-0 flex items-center justify-center bg-[#08080f]">
          <div className="text-center">
            <Loader2 className="w-6 h-6 text-violet-400 animate-spin mx-auto mb-2" />
            <p className="text-xs text-white/40">Rendering diagram…</p>
          </div>
        </div>
      )}

      {rendered && (
        <div className="absolute bottom-4 right-4 flex flex-col gap-1.5">
          <button onClick={() => setZoom((z) => Math.min(z * 1.2, 4))} className="w-8 h-8 flex items-center justify-center rounded-lg bg-[#111118] border border-white/10 text-white/40 hover:text-white/70 hover:bg-white/8 transition-all">
            <ZoomIn className="w-3.5 h-3.5" />
          </button>
          <button onClick={() => setZoom((z) => Math.max(z * 0.8, 0.2))} className="w-8 h-8 flex items-center justify-center rounded-lg bg-[#111118] border border-white/10 text-white/40 hover:text-white/70 hover:bg-white/8 transition-all">
            <ZoomOut className="w-3.5 h-3.5" />
          </button>
          <button onClick={resetView} className="w-8 h-8 flex items-center justify-center rounded-lg bg-[#111118] border border-white/10 text-white/40 hover:text-white/70 hover:bg-white/8 transition-all" title="Reset view">
            <Maximize2 className="w-3.5 h-3.5" />
          </button>
          <div className="text-[9px] text-white/20 text-center">{Math.round(zoom * 100)}%</div>
        </div>
      )}

      {rendered && (
        <div className="absolute bottom-4 left-4 text-[10px] text-white/25 bg-[#111118]/80 border border-white/6 rounded-lg px-3 py-2 backdrop-blur space-y-1">
          <div>🖱️ Scroll to zoom · Drag to pan</div>
          <div>🖱️ Click a node to inspect file</div>
          <div>🔵 Purple border = entry points</div>
        </div>
      )}
    </div>
  );
}