from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from app.db.session import get_db
from app.db.models import Repository, CodeFile
from app.config import get_settings
import markdown as md
from app.core.limiter import limiter

router = APIRouter(prefix="/docs", tags=["docs"])
settings = get_settings()


def get_llm():
    return ChatGroq(
        model="llama-3.3-70b-versatile",
        api_key=settings.groq_api_key,
        temperature=0.2,
    )


@router.get("/{owner}/{name}/generate")
@limiter.limit("15/hour")
async def generate_docs(request: Request, owner: str, name: str, path: str | None = None, db: Session = Depends(get_db)):
    """
    Generate documentation for a specific file or the entire repo.
    If path is provided, generates docs for that file only.
    """
    full_name = f"{owner}/{name}"
    repo = db.query(Repository).filter_by(full_name=full_name).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Not found")

    llm = get_llm()

    if path:
        # Single file documentation
        file = db.query(CodeFile).filter_by(repo_id=repo.id, path=path).first()
        if not file:
            raise HTTPException(status_code=404, detail="File not found")

        prompt = f"""Generate clear, professional documentation for this code file.
Include: purpose, functions/classes with descriptions, parameters, return values, usage examples.
Format as Markdown.

File: {file.path}
Language: {file.language}

{file.content[:8000]}"""

        response = llm.invoke([SystemMessage(content="You are a technical documentation writer."),
                               HumanMessage(content=prompt)])
        return {"path": path, "documentation": response.content, "format": "markdown"}

    else:
        # Repo-level overview documentation
        files_summary = []
        for f in db.query(CodeFile).filter_by(repo_id=repo.id).limit(50).all():
            if f.functions:
                fns = ", ".join(fn["name"] for fn in f.functions[:5])
                files_summary.append(f"- `{f.path}` ({f.language}): {fns}")

        prompt = f"""Generate a comprehensive README-style documentation for this project.
Include: Project overview, architecture, key files and their roles, how to navigate the codebase, main flows.
Format as Markdown.

Repo: {full_name}
Description: {repo.description}
Language: {repo.language}
Total files: {repo.total_files}

Key files:
{chr(10).join(files_summary[:40])}"""

        response = llm.invoke([SystemMessage(content="You are a senior technical writer."),
                               HumanMessage(content=prompt)])
        return {"path": None, "documentation": response.content, "format": "markdown"}


@router.get("/{owner}/{name}/download")
@limiter.limit("15/hour")
async def download_docs(request: Request, owner: str, name: str, format: str = "md", db: Session = Depends(get_db)):
    """Download generated docs as Markdown or HTML."""
    full_name = f"{owner}/{name}"
    repo = db.query(Repository).filter_by(full_name=full_name).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Not found")

    llm = get_llm()
    files_summary = []
    for f in db.query(CodeFile).filter_by(repo_id=repo.id).limit(100).all():
        fns = [fn["name"] for fn in (f.functions or [])[:3]]
        files_summary.append(f"### `{f.path}`\n**Language**: {f.language} | **Lines**: {f.lines}\n" +
                             (f"**Functions**: {', '.join(fns)}\n" if fns else ""))

    prompt = f"""Generate complete project documentation for {full_name}.
Include all sections: Overview, Setup, Architecture, File Reference, API Reference.
Use proper Markdown with headers, code blocks, and tables."""

    response = llm.invoke([HumanMessage(content=prompt)])
    doc_content = response.content

    if format == "html":
        html_content = md.markdown(doc_content, extensions=["fenced_code", "tables"])
        full_html = f"<html><body style='font-family:sans-serif;max-width:900px;margin:auto;padding:2rem'>{html_content}</body></html>"
        return Response(
            content=full_html,
            media_type="text/html",
            headers={"Content-Disposition": f'attachment; filename="{repo.name}-docs.html"'}
        )
    else:
        return Response(
            content=doc_content,
            media_type="text/markdown",
            headers={"Content-Disposition": f'attachment; filename="{repo.name}-docs.md"'}
        )