// ── Repo ──────────────────────────────────────────────────────────
export interface RepoMeta {
  id: string;
  full_name: string;
  owner: string;
  name: string;
  description: string | null;
  url: string;
  stars: number;
  forks: number;
  language: string | null;
  topics: string[];
  license: string | null;
  language_breakdown: Record<string, number>;
  total_files: number;
  total_lines: number;
  health_score: number | null;
  health_breakdown: Array<{
    key: string;
    label: string;
    score: number;
    weight: number;
    description: string;
  }> | null;
  ai_summary: string | null;
  status: RepoStatus;
  analysed_at: string | null;
}

export type RepoStatus =
  | "pending"
  | "fetching"
  | "parsing"
  | "graphing"
  | "analyzing"
  | "ready"
  | "failed";

export interface PipelineStatus {
  status: RepoStatus;
  message: string;
  progress: number; // 0.0 – 1.0
  repo_id: string;
  description?: string;
  stars?: number;
  language?: string;
  language_breakdown?: Record<string, number>;
  total_files?: number;
  total_lines?: number;
  ai_summary?: string;
  analysed_at?: string;
}

// ── Graph ─────────────────────────────────────────────────────────
export interface GraphNode {
  id: string;
  type: "fileNode";
  position: { x: number; y: number };
  data: {
    label: string;
    path: string;
    language: string;
    lines: number;
    functions_count: number;
    classes_count: number;
    ai_summary: string | null;
    layer: string;
    in_degree: number;
    out_degree: number;
  };
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type: string;
  data: { edge_type: string };
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
  stats: {
    total_nodes: number;
    total_edges: number;
    is_dag: boolean;
    layers: string[];
  };
}

// ── Diagram (AI-generated architecture view) ─────────────────────
export interface DiagramResponse {
  mermaid: string;
  label_map: Record<string, string>; // exact rendered node label -> real file path
  repo_name: string;
  total_files: number;
  cached: boolean;
}

export interface FileDetail {
  path: string;
  name: string;
  language: string;
  lines: number;
  size_bytes: number;
  content: string | null;
  ai_summary: string | null;
  functions: FunctionInfo[];
  classes: ClassInfo[];
  imports: string[];
  exports: string[];
  imports_from: string[];
  imported_by: string[];
}

export interface FunctionInfo {
  name: string;
  line: number;
  signature: string;
  is_async?: boolean;
  description?: string;
}

export interface ClassInfo {
  name: string;
  line: number;
  bases: string[];
}

// ── Structure ─────────────────────────────────────────────────────
export interface FunctionEntry {
  name: string;
  file: string;
  line: number;
  signature: string;
  language: string;
  ai_description: string | null;
}

export interface Dependency {
  name: string;
  version: string | null;
  ecosystem: string | null;
  is_dev: boolean;
  ai_purpose: string | null;
  has_vulnerability: boolean;
  vuln_details: Array<{
    cve_id: string;
    severity: "critical" | "high" | "medium" | "low";
    summary: string;
    cvss_score: number;
    url: string;
    fixed_in: string | null;
  }> | null;
}

export interface ApiRoute {
  method: string;
  path: string;
  handler_file: string | null;
  handler_function: string | null;
  description: string | null;
}

export interface DbTable {
  table_name: string;
  source_file: string | null;
  columns: DbColumn[];
  relationships: DbRelationship[];
}

export interface DbColumn {
  name: string;
  type: string;
  nullable: boolean;
  pk: boolean;
  fk: boolean;
}

export interface DbRelationship {
  to_table: string;
  type: string;
}

// ── Commits ───────────────────────────────────────────────────────
export interface Commit {
  sha: string;
  sha_short: string;
  message: string;
  ai_summary: string | null;
  author_name: string;
  author_email: string;
  committed_at: string;
  files_changed: string[];
  additions: number;
  deletions: number;
}

// ── Chat ──────────────────────────────────────────────────────────
export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  isStreaming?: boolean;
  contextFiles?: string[];
}