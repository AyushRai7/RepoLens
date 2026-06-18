from langchain_core.tools import tool
from sqlalchemy.orm import Session
from app.db.models import CodeFile, GraphEdge, ApiRoute, Dependency
import json


def make_tools(db: Session, repo_id: str, retriever):
    """
    Factory: returns a list of LangChain tools scoped to a specific repo.
    The retriever is a LangChain retriever over the repo's vector store.
    """

    @tool
    def search_code(query: str) -> str:
        """
        Semantically search the codebase for files or functions relevant to a query.
        Use this to find where a feature is implemented, e.g. 'where is authentication handled'.
        """
        docs = retriever.invoke(query)
        if not docs:
            return "No relevant code found."
        results = []
        for doc in docs[:4]:
            results.append(f"File: {doc.metadata.get('path')}\n{doc.page_content[:400]}")
        return "\n\n---\n\n".join(results)

    @tool
    def get_file(path: str) -> str:
        """
        Get the full content and metadata of a specific file by its path.
        Use when you need to read exact code in a file.
        """
        file = db.query(CodeFile).filter_by(repo_id=repo_id, path=path).first()
        if not file:
            return f"File not found: {path}"
        return (
            f"File: {file.path}\nLanguage: {file.language}\nLines: {file.lines}\n\n"
            f"{file.content or '[no content]'}"
        )

    @tool
    def get_neighbors(path: str) -> str:
        """
        Get the direct imports and files that import a given file.
        Use to understand a file's dependencies and dependents.
        """
        outgoing = db.query(GraphEdge).filter_by(repo_id=repo_id, source_path=path).all()
        incoming = db.query(GraphEdge).filter_by(repo_id=repo_id, target_path=path).all()
        result = {
            "file": path,
            "imports": [e.target_path for e in outgoing],
            "imported_by": [e.source_path for e in incoming],
        }
        return json.dumps(result, indent=2)

    @tool
    def list_functions(path: str) -> str:
        """
        List all functions and classes defined in a file.
        Use when asked about what a file contains or its API surface.
        """
        file = db.query(CodeFile).filter_by(repo_id=repo_id, path=path).first()
        if not file:
            return f"File not found: {path}"
        functions = file.functions or []
        classes = file.classes or []
        out = [f"Functions in {path}:"]
        for fn in functions:
            out.append(f"  - {fn.get('name')} (line {fn.get('line')}): {fn.get('signature', '')}")
        if classes:
            out.append(f"\nClasses in {path}:")
            for cls in classes:
                out.append(f"  - {cls.get('name')} (line {cls.get('line')})")
        return "\n".join(out)

    @tool
    def get_api_routes(filter: str = "") -> str:
        """
        List all API routes/endpoints in the project.
        Use when asked about what endpoints exist or what the API looks like.
        Optionally pass a filter string to narrow results by path or method.
        """
        routes = db.query(ApiRoute).filter_by(repo_id=repo_id).all()
        if not routes:
            return "No API routes found or not yet extracted."
        lines = ["API Routes:"]
        for r in routes:
            line = f"  {r.method} {r.path} → {r.handler_file} ({r.description or 'no description'})"
            if not filter or filter.lower() in line.lower():
                lines.append(line)
        return "\n".join(lines)

    return [search_code, get_file, get_neighbors, list_functions, get_api_routes]