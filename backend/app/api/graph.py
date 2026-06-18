from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from sqlalchemy.orm import Session
from app.db.session import get_db, SessionLocal
from app.db.models import Repository, GraphEdge, CodeFile
from app.db.cache import get_cache, set_cache, delete_cache
from app.services.graph_builder import detect_layers, resolve_import
import networkx as nx
from app.core.limiter import limiter

router = APIRouter(prefix="/graph", tags=["graph"])

# Current supported Groq model (llama-3.1-70b decommissioned)
_GROQ_MODEL = "llama-3.3-70b-versatile"


def _build_layer_map(files, edges) -> dict[str, str]:
    G = nx.DiGraph()
    for f in files:
        G.add_node(f.path)
    for e in edges:
        G.add_edge(e.source_path, e.target_path)
    return detect_layers(G)


@router.get("/{owner}/{name}")
async def get_graph(owner: str, name: str, db: Session = Depends(get_db)):
    """Return full graph data (nodes + edges) for React Flow."""
    full_name = f"{owner}/{name}"

    cached = get_cache(f"graph:{full_name}")
    if cached:
        return cached

    repo = db.query(Repository).filter_by(full_name=full_name).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    if repo.status != "ready":
        raise HTTPException(status_code=202, detail="Analysis still in progress")

    files = db.query(CodeFile).filter_by(repo_id=repo.id).all()
    edges = db.query(GraphEdge).filter_by(repo_id=repo.id).all()

    # Degree maps
    in_deg = {f.path: 0 for f in files}
    out_deg = {f.path: 0 for f in files}
    for e in edges:
        out_deg[e.source_path] = out_deg.get(e.source_path, 0) + 1
        in_deg[e.target_path] = in_deg.get(e.target_path, 0) + 1

    layer_map = _build_layer_map(files, edges)

    # Build nx graph for layout
    G = nx.DiGraph()
    for f in files:
        G.add_node(f.path)
    for e in edges:
        G.add_edge(e.source_path, e.target_path)

    pos = {}
    if G.number_of_nodes() > 0:
        pos = nx.spring_layout(G, k=2.5, iterations=60, seed=42)

    nodes = [
        {
            "id": f.path,
            "type": "fileNode",
            "position": {
                "x": float(pos.get(f.path, (0, 0))[0]) * 700,
                "y": float(pos.get(f.path, (0, 0))[1]) * 500,
            },
            "data": {
                "label": f.name,
                "path": f.path,
                "language": f.language,
                "lines": f.lines,
                "functions_count": len(f.functions or []),
                "classes_count": len(f.classes or []),
                "ai_summary": f.ai_summary,
                "layer": layer_map.get(f.path, "other"),
                "in_degree": in_deg.get(f.path, 0),
                "out_degree": out_deg.get(f.path, 0),
            },
        }
        for f in files
    ]

    edge_list = [
        {
            "id": f"e{i}",
            "source": e.source_path,
            "target": e.target_path,
            "type": "smoothstep",
            "data": {"edge_type": e.edge_type},
        }
        for i, e in enumerate(edges)
    ]

    all_layers = sorted(set(layer_map.values()))
    result = {
        "nodes": nodes,
        "edges": edge_list,
        "stats": {
            "total_nodes": len(nodes),
            "total_edges": len(edge_list),
            "is_dag": nx.is_directed_acyclic_graph(G),
            "layers": all_layers,
            "import_edges": sum(1 for e in edges if e.edge_type == "import"),
            "api_call_edges": sum(1 for e in edges if e.edge_type == "api_call"),
        },
    }

    set_cache(f"graph:{full_name}", result, ttl_seconds=600)
    return result


@router.post("/{owner}/{name}/rebuild-edges")
async def rebuild_edges(
    owner: str,
    name: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Re-run edge detection on stored CodeFile records without re-ingesting.
    Call this once for repos that were ingested before the import-resolution fix.
    Runs in background — returns immediately.
    """
    full_name = f"{owner}/{name}"
    repo = db.query(Repository).filter_by(full_name=full_name).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    background_tasks.add_task(_do_rebuild_edges, str(repo.id), full_name)
    return {
        "status": "rebuilding",
        "message": "Edge rebuild started in background. Refresh the graph in ~30s.",
    }


def _do_rebuild_edges(repo_id: str, full_name: str):
    """Background task: rebuild GraphEdge rows from stored imports."""
    db = SessionLocal()
    try:
        files = db.query(CodeFile).filter_by(repo_id=repo_id).all()
        all_paths = {f.path for f in files}

        # Build import map
        import_edges = set()
        for f in files:
            for imp in f.imports or []:
                resolved = resolve_import(imp, f.path, all_paths)
                if resolved and resolved != f.path:
                    import_edges.add((f.path, resolved))

        # Delete existing edges
        db.query(GraphEdge).filter_by(repo_id=repo_id).delete()

        # Insert new edges
        for src, tgt in import_edges:
            db.add(
                GraphEdge(
                    repo_id=repo_id,
                    source_path=src,
                    target_path=tgt,
                    edge_type="import",
                )
            )

        db.commit()

        # Bust graph cache
        delete_cache(f"graph:{full_name}")
    except Exception as e:
        db.rollback()
        raise
    finally:
        db.close()


@router.get("/{owner}/{name}/file")
async def get_file_detail(
    owner: str, name: str, path: str, db: Session = Depends(get_db)
):
    full_name = f"{owner}/{name}"
    repo = db.query(Repository).filter_by(full_name=full_name).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    file = db.query(CodeFile).filter_by(repo_id=repo.id, path=path).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    outgoing = db.query(GraphEdge).filter_by(repo_id=repo.id, source_path=path).all()
    incoming = db.query(GraphEdge).filter_by(repo_id=repo.id, target_path=path).all()

    return {
        "path": file.path,
        "name": file.name,
        "language": file.language,
        "lines": file.lines,
        "size_bytes": file.size_bytes,
        "content": file.content,
        "ai_summary": file.ai_summary,
        "functions": file.functions or [],
        "classes": file.classes or [],
        "imports": file.imports or [],
        "exports": file.exports or [],
        "imports_from": [e.target_path for e in outgoing],
        "imported_by": [e.source_path for e in incoming],
    }


@router.post("/{owner}/{name}/summarize")
@limiter.limit("30/hour")
async def summarize_file(
    request: Request, owner: str, name: str, body: dict, db: Session = Depends(get_db)
):
    """Generate an AI summary for a single file using Groq."""
    from groq import Groq
    from app.config import get_settings

    settings = get_settings()
    path = body.get("path", "")
    full_name = f"{owner}/{name}"

    repo = db.query(Repository).filter_by(full_name=full_name).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    file = db.query(CodeFile).filter_by(repo_id=repo.id, path=path).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    if file.ai_summary:
        return {"path": path, "summary": file.ai_summary}

    if not file.content:
        return {"path": path, "summary": "No source content available for this file."}

    fn_list = ", ".join(f["name"] for f in (file.functions or [])[:20])
    cls_list = ", ".join(c["name"] for c in (file.classes or [])[:10])
    imports_sample = ", ".join((file.imports or [])[:10])
    snippet = file.content[:4000]

    prompt = f"""You are a senior engineer reviewing a codebase. Write a concise 2-3 sentence summary of this file explaining:
1. Its primary purpose and responsibility in the codebase
2. The key logic or patterns it implements (be specific — mention algorithms, data flows, or design patterns if present)
3. Its role relative to other files (what it depends on or what consumes it)

File: {path}
Language: {file.language}
Lines: {file.lines}
Functions/exports: {fn_list or 'none'}
Classes: {cls_list or 'none'}
Imports from: {imports_sample or 'none'}

Source code:
```
{snippet}
```

Write ONLY the summary. Be specific about what the code actually does — not just listing names."""

    try:
        client = Groq(api_key=settings.groq_api_key)
        response = client.chat.completions.create(
            model=_GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0.15,
        )
        summary = response.choices[0].message.content.strip()
    except Exception as e:
        # Fallback: try smaller model
        try:
            response = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=0.15,
            )
            summary = response.choices[0].message.content.strip()
        except Exception as e2:
            raise HTTPException(status_code=500, detail=f"Groq error: {str(e2)[:200]}")

    file.ai_summary = summary
    db.commit()
    delete_cache(f"graph:{full_name}")

    return {"path": path, "summary": summary}


@router.get("/{owner}/{name}/trace")
async def trace_path(
    owner: str,
    name: str,
    source: str,
    target: str,
    db: Session = Depends(get_db),
):
    """Find the shortest import path between two files."""
    full_name = f"{owner}/{name}"
    repo = db.query(Repository).filter_by(full_name=full_name).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    edges = db.query(GraphEdge).filter_by(repo_id=repo.id).all()

    G = nx.DiGraph()
    edge_lookup = {}
    for i, e in enumerate(edges):
        G.add_edge(e.source_path, e.target_path)
        edge_lookup[(e.source_path, e.target_path)] = f"e{i}"

    try:
        path_nodes = nx.shortest_path(G, source=source, target=target)
        path_edges = [
            edge_lookup.get((path_nodes[i], path_nodes[i + 1]), "")
            for i in range(len(path_nodes) - 1)
        ]
        return {
            "found": True,
            "path": path_nodes,
            "edge_ids": path_edges,
            "hops": len(path_nodes) - 1,
        }
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return {"found": False, "path": [], "edge_ids": [], "hops": 0}


"""
ADD THIS TO graph.py — new endpoint for AI-generated Mermaid diagram.

Paste these two imports at the top of your existing graph.py:
    import json
    from groq import Groq

Then paste the two functions below anywhere in the file.
"""

import json
import re


_DIAGRAM_SYSTEM_PROMPT = """You are an expert software architect. Identify the most important
files in a codebase and how they relate, so a tool can render an architecture diagram.

Output ONLY valid JSON. No markdown fences, no explanation, no preamble — your entire response
must be a single JSON object matching this shape:

{
  "clusters": [
    {"name": "Frontend / UI", "files": ["exact/path/one.tsx", "exact/path/two.tsx"]},
    {"name": "API Routes", "files": ["exact/path/three.py"]}
  ],
  "edges": [
    {"from": "exact/path/one.tsx", "to": "exact/path/three.py", "label": "API call"}
  ],
  "entry_points": ["exact/path/one.tsx"]
}

CRITICAL RULES:
1. Every value in "files", "from", "to", and "entry_points" MUST be copied character-for-character
   from the FILE LIST you are given. Never invent, shorten, rename, or guess a path. If you are
   not certain a path is real, leave it out entirely.
2. Pick only the most important ~20-40 files. Skip tests, configs, and lock files.
3. Group files by architectural role, using names like: "Frontend / UI", "API Routes",
   "Services", "Models / ORM", "Database", "Utilities".
4. "label" on an edge is optional and should be short (e.g. "imports", "API call", "uses").
5. "entry_points" should list the 2-5 most important/central files.
"""


def _build_diagram_prompt(
    repo_name: str, file_tree: list[str], readme_snippet: str, language: str
) -> str:
    tree_str = "\n".join(file_tree[:300])
    return f"""Repository: {repo_name}
Primary language: {language or "unknown"}

FILE LIST (the only paths you are allowed to use):
{tree_str}

README EXCERPT:
{readme_snippet[:800] if readme_snippet else "(no README)"}

Identify the most important files, group them by architectural layer, and describe how they
connect. Output ONLY the JSON object described in the system prompt — every path must be copied
exactly from the FILE LIST above."""


_ID_INVALID_CHARS = re.compile(r"[^a-zA-Z0-9_]")


def _sanitize_node_id(path: str, used_ids: set[str]) -> str:
    """Turn a real file path into a unique, Mermaid-safe node id (used only
    internally, to wire up edges — never exposed to the frontend)."""
    base = _ID_INVALID_CHARS.sub("_", path).strip("_") or "node"
    if base[0].isdigit():
        base = f"n_{base}"
    node_id = base
    suffix = 1
    while node_id in used_ids:
        node_id = f"{base}_{suffix}"
        suffix += 1
    used_ids.add(node_id)
    return node_id


def _unique_display_label(
    path: str, all_paths: list[str], used_labels: set[str]
) -> str:
    """
    Basename by default. If another file ANYWHERE in the diagram (not just
    this cluster) shares the same basename, prefix with the parent folder.
    If that still collides, fall back to the full path. This guarantees
    every label rendered is unique, so the frontend can resolve a click by
    exact visible text — no dependency on Mermaid's internal SVG id format.
    """
    name = path.rsplit("/", 1)[-1]
    same_name = [p for p in all_paths if p.rsplit("/", 1)[-1] == name]

    label = name
    if len(same_name) > 1:
        parent = path.rsplit("/", 2)[-2] if "/" in path else ""
        label = f"{parent}/{name}" if parent else name

    if label in used_labels:
        label = path  # last-resort fallback — paths are always unique

    used_labels.add(label)
    return label


def _build_diagram_from_llm_json(
    raw: dict, valid_paths: set[str]
) -> tuple[str, dict[str, str]]:
    """
    Validate the LLM's proposed grouping against real file paths and
    deterministically build Mermaid syntax plus a label_map: the exact
    rendered label text for each node -> the real file path. The frontend
    reads each node's visible text and looks it up here directly — since
    labels are validated + globally unique, this is unambiguous.
    """
    clusters_raw = raw.get("clusters", [])
    if not isinstance(clusters_raw, list):
        clusters_raw = []

    kept_clusters: list[tuple[str, list[str]]] = []
    all_kept_paths: list[str] = []
    for ci, cluster in enumerate(clusters_raw):
        if not isinstance(cluster, dict):
            continue
        name = str(cluster.get("name", f"Group {ci+1}"))[:40]
        raw_files = cluster.get("files", [])
        if not isinstance(raw_files, list):
            continue
        files = [f for f in raw_files if isinstance(f, str) and f in valid_paths]
        if not files:
            continue
        kept_clusters.append((name, files))
        all_kept_paths.extend(files)

    if not kept_clusters:
        raise ValueError(
            "no valid files survived validation against the real file list"
        )

    # Pass 2 — build deterministic Mermaid text + the label->path map
    used_ids: set[str] = set()
    used_labels: set[str] = set()
    path_to_id: dict[str, str] = {}
    label_map: dict[str, str] = {}

    lines = ["flowchart TD"]
    for ci, (name, files) in enumerate(kept_clusters):
        cluster_id = f"C{ci}_" + _ID_INVALID_CHARS.sub("_", name)[:20]
        lines.append(f'    subgraph {cluster_id}["{name}"]')
        for path in files:
            node_id = _sanitize_node_id(path, used_ids)
            label = _unique_display_label(path, all_kept_paths, used_labels)
            path_to_id[path] = node_id
            label_map[label] = path
            lines.append(f'        {node_id}["{label}"]')
        lines.append("    end")

    lines.append("")
    for edge in raw.get("edges", []):
        if not isinstance(edge, dict):
            continue
        src, tgt = edge.get("from"), edge.get("to")
        if src not in path_to_id or tgt not in path_to_id:
            continue
        edge_label = edge.get("label")
        arrow = f" -- {edge_label} --> " if edge_label else " --> "
        lines.append(f"    {path_to_id[src]}{arrow}{path_to_id[tgt]}")

    entry_points = raw.get("entry_points", [])
    if isinstance(entry_points, list):
        valid_entries = [p for p in entry_points if p in path_to_id]
        if valid_entries:
            lines.append("")
            for p in valid_entries:
                lines.append(
                    f"    style {path_to_id[p]} fill:#7c3aed,color:#fff,stroke:#6d28d9"
                )

    return "\n".join(lines), label_map


@router.post("/{owner}/{name}/generate-diagram")
@limiter.limit("10/hour")
async def generate_diagram(
    request: Request, owner: str, name: str, db: Session = Depends(get_db)
):
    """
    Generate an AI-assisted architecture diagram. The LLM only proposes
    groupings as JSON — it never writes Mermaid syntax or node labels
    directly. Every path is checked against the real file list before
    anything renders.

    Returns: { mermaid: str, node_map: dict[str, str], cached: bool }
    """
    from groq import Groq
    from app.config import get_settings

    settings = get_settings()
    full_name = f"{owner}/{name}"

    cached = get_cache(f"diagram:{full_name}")
    if cached:
        return {**cached, "cached": True}

    repo = db.query(Repository).filter_by(full_name=full_name).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    if repo.status != "ready":
        raise HTTPException(status_code=202, detail="Analysis still in progress")

    files = db.query(CodeFile).filter_by(repo_id=repo.id).all()
    file_paths = sorted([f.path for f in files])
    valid_paths = set(file_paths)

    readme_file = next(
        (f for f in files if f.name.lower() in ("readme.md", "readme.txt", "readme")),
        None,
    )
    readme_snippet = (
        readme_file.content[:800] if (readme_file and readme_file.content) else ""
    )

    prompt = _build_diagram_prompt(
        repo_name=full_name,
        file_tree=file_paths,
        readme_snippet=readme_snippet,
        language=repo.language or "unknown",
    )

    client = Groq(api_key=settings.groq_api_key)

    parsed_json = None
    for model in ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]:
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": _DIAGRAM_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=3000,
                temperature=0.15,
                response_format={
                    "type": "json_object"
                },  
            )
            raw_text = response.choices[0].message.content.strip()
            raw_text = raw_text.replace("```json", "").replace("```", "").strip()
            parsed_json = json.loads(raw_text)
            break
        except Exception:
            continue

    if not parsed_json:
        raise HTTPException(
            status_code=500, detail="Failed to generate diagram from LLM"
        )

    try:
        mermaid_code, label_map = _build_diagram_from_llm_json(parsed_json, valid_paths)
    except ValueError as e:
        raise HTTPException(
            status_code=500, detail=f"Diagram generation produced no valid nodes: {e}"
        )

    result = {
        "mermaid": mermaid_code,
        "label_map": label_map,
        "repo_name": full_name,
        "total_files": len(file_paths),
    }
    set_cache(f"diagram:{full_name}", result, ttl_seconds=86400)

    return {**result, "cached": False}


@router.delete("/{owner}/{name}/generate-diagram")
@limiter.limit("5/hour")
async def clear_diagram_cache(request: Request, owner: str, name: str):
    """Clear cached diagram so it regenerates on next request."""
    full_name = f"{owner}/{name}"
    delete_cache(f"diagram:{full_name}")
    return {"status": "cleared"}
