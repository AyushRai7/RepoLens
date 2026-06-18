import re
import networkx as nx
from typing import Optional
from app.services.ast_parser import ParsedFile


def resolve_import(import_path: str, current_file: str, all_paths: set[str]) -> Optional[str]:
    """
    Resolve a relative or local import to a real file path in the repo.
    Handles:
      - Relative: ./foo, ../bar/baz
      - TS path alias: @/ maps to root, src/, app/
      - Bare module names matching a file
    Returns the matched repo path or None if external library.
    """
    import_path = import_path.split("?")[0].split("#")[0]

    normalized_candidates = []

    if import_path.startswith("@/"):
        rest = import_path[2:]
        normalized_candidates += [rest, "src/" + rest, "app/" + rest]

    elif import_path.startswith("."):
        base_dir = "/".join(current_file.split("/")[:-1])
        rel = import_path.lstrip(".")
        dots = len(import_path) - len(import_path.lstrip("."))
        parts = base_dir.split("/")
        base = "/".join(parts[:max(0, len(parts) - (dots - 1))])
        rel_stripped = rel.lstrip("/")
        prefix = (base + "/" + rel_stripped).strip("/") if rel_stripped else base
        normalized_candidates.append(prefix)

    else:
        normalized = import_path.replace(".", "/")
        normalized_candidates += [
            normalized,
            "src/" + normalized,
            "app/" + normalized,
            "lib/" + normalized,
        ]

    extensions = [
        ".ts", ".tsx", ".js", ".jsx",
        ".py",
        "/index.ts", "/index.tsx", "/index.js", "/index.jsx",
        "/__init__.py",
        ".vue", ".svelte",
    ]

    for base_candidate in normalized_candidates:
        if base_candidate in all_paths:
            return base_candidate
        for ext in extensions:
            candidate = base_candidate + ext
            if candidate in all_paths:
                return candidate

    return None


def build_graph(parsed_files: list[ParsedFile]) -> dict:
    """Build a directed graph from parsed files."""
    G = nx.DiGraph()
    all_paths = {f.path for f in parsed_files}

    for pf in parsed_files:
        G.add_node(pf.path, **{
            "label": pf.path.split("/")[-1],
            "path": pf.path,
            "language": pf.language,
            "lines": pf.lines,
            "functions_count": len(pf.functions),
            "classes_count": len(pf.classes),
            "imports_count": len(pf.imports),
        })

    for pf in parsed_files:
        for imp in pf.imports:
            resolved = resolve_import(imp, pf.path, all_paths)
            if resolved and resolved != pf.path:
                G.add_edge(pf.path, resolved, type="import")

    for node in G.nodes():
        G.nodes[node]["in_degree"] = G.in_degree(node)
        G.nodes[node]["out_degree"] = G.out_degree(node)

    pos = nx.spring_layout(G, k=2, iterations=50, seed=42)
    layers = detect_layers(G)

    nodes = []
    for node_id, data in G.nodes(data=True):
        x, y = pos.get(node_id, (0, 0))
        nodes.append({
            "id": node_id,
            "type": "fileNode",
            "position": {"x": float(x) * 600, "y": float(y) * 400},
            "data": {**data, "layer": layers.get(node_id, "unknown")}
        })

    edges = []
    for i, (source, target, data) in enumerate(G.edges(data=True)):
        edges.append({
            "id": f"e{i}",
            "source": source,
            "target": target,
            "type": "smoothstep",
            "data": {"edge_type": data.get("type", "import")},
        })

    import_count = sum(1 for _, _, d in G.edges(data=True) if d.get("type") == "import")

    return {
        "nodes": nodes,
        "edges": edges,
        "stats": {
            "total_nodes": G.number_of_nodes(),
            "total_edges": G.number_of_edges(),
            "is_dag": nx.is_directed_acyclic_graph(G),
            "layers": list(set(layers.values())),
            "import_edges": import_count,
            "api_call_edges": 0,
        }
    }


def detect_layers(G: nx.DiGraph) -> dict[str, str]:
    layers = {}
    layer_keywords = {
        "route": ["route", "router", "routes", "controller", "handler", "endpoint", "api/"],
        "service": ["service", "services", "usecase", "business", "logic", "action"],
        "model": ["model", "models", "entity", "entities", "schema", "orm", "prisma"],
        "db": ["db", "database", "migration", "repository", "repo", "seed"],
        "util": ["util", "utils", "helper", "helpers", "lib/", "common", "shared", "hooks/"],
        "config": ["config", "settings", "env", "constants", "middleware"],
        "test": ["test", "tests", "spec", "__tests__", "fixtures", ".test.", ".spec."],
        "ui": ["component", "components", "page", "pages", "layout", "widget", "app/"],
    }
    for node in G.nodes():
        path_lower = node.lower()
        assigned = "other"
        for layer, keywords in layer_keywords.items():
            if any(kw in path_lower for kw in keywords):
                assigned = layer
                break
        layers[node] = assigned
    return layers


def get_flow_path(graph_data: dict, source_path: str, target_path: str) -> list[str]:
    G = nx.DiGraph()
    for edge in graph_data["edges"]:
        G.add_edge(edge["source"], edge["target"])
    try:
        return nx.shortest_path(G, source=source_path, target=target_path)
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return []