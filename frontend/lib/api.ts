import type {
  RepoMeta,
  PipelineStatus,
  GraphData,
  FileDetail,
  FunctionEntry,
  Dependency,
  ApiRoute,
  DbTable,
  Commit,
  DiagramResponse,
} from "./types";
const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function req<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

// ── Repos ─────────────────────────────────────────────────────────
export const analyzeRepo = (url: string) =>
  req<{ repo_id: string; full_name: string; status: string; cached: boolean }>(
    "/api/repos/analyze",
    { method: "POST", body: JSON.stringify({ url }) },
  );

export const getRepoStatus = (owner: string, name: string) =>
  req<PipelineStatus>(`/api/repos/${owner}/${name}/status`);

export const getRepo = (owner: string, name: string) =>
  req<RepoMeta>(`/api/repos/${owner}/${name}`);

// ── Graph ─────────────────────────────────────────────────────────
export const getGraph = (owner: string, name: string) =>
  req<GraphData>(`/api/graph/${owner}/${name}`);

export const getFileDetail = (owner: string, name: string, path: string) =>
  req<FileDetail>(
    `/api/graph/${owner}/${name}/file?path=${encodeURIComponent(path)}`,
  );



// ── Diagram ───────────────────────────────────────────────────────
export class DiagramPendingError extends Error {}

export async function generateDiagram(owner: string, name: string): Promise<DiagramResponse> {
  const res = await fetch(`${BASE}/api/graph/${owner}/${name}/generate-diagram`, { method: "POST" });
  if (res.status === 202) {
    throw new DiagramPendingError("Repository is still being analyzed. Please wait for analysis to complete.");
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export const clearDiagramCache = (owner: string, name: string) =>
  fetch(`${BASE}/api/graph/${owner}/${name}/generate-diagram`, { method: "DELETE" });



// ── Structure ─────────────────────────────────────────────────────
export const getFunctions = (owner: string, name: string) =>
  req<{
    functions: FunctionEntry[];
    total: number;
  }>(`/api/structure/${owner}/${name}/functions`);

export const getDependencies = (owner: string, name: string) =>
  req<{
    dependencies: Dependency[];
    total: number;
    vulnerable_count: number;
  }>(`/api/structure/${owner}/${name}/dependencies`);

export const getApiRoutes = (owner: string, name: string) =>
  req<{
    routes: ApiRoute[];
    total: number;
  }>(`/api/structure/${owner}/${name}/api-routes`);

export const getDbSchema = (owner: string, name: string) =>
  req<{
    tables: DbTable[];
    total: number;
  }>(`/api/structure/${owner}/${name}/db-schema`);

export const getCommits = (owner: string, name: string, limit = 50) =>
  req<{
    commits: Commit[];
    total: number;
  }>(`/api/commits/${owner}/${name}?limit=${limit}`);


// ── Docs ──────────────────────────────────────────────────────────
export const generateDocs = (owner: string, name: string, path?: string) =>
  req<{ path: string | null; documentation: string; format: string }>(
    `/api/docs/${owner}/${name}/generate${path ? `?path=${encodeURIComponent(path)}` : ""}`,
  );

export const downloadDocsUrl = (
  owner: string,
  name: string,
  format: "md" | "html",
) => `${BASE}/api/docs/${owner}/${name}/download?format=${format}`;
