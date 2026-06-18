from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime
from app.db.session import get_db
from app.db.models import Repository
from app.db.cache import get_job_status, set_job_status
from app.services.github_fetcher import parse_github_url, fetch_repo_meta
from app.tasks.ingest_task import ingest_repo
import asyncio
from datetime import datetime, timedelta
from app.core.limiter import limiter

router = APIRouter(prefix="/repos", tags=["repos"])

_IN_PROGRESS_STATUSES = {"pending", "fetching", "parsing", "graphing", "analyzing"}
_STALE_AFTER = timedelta(minutes=10)


class AnalyzeRequest(BaseModel):
    url: str


class RepoStatusResponse(BaseModel):
    repo_id: str
    full_name: str
    status: str
    message: str
    progress: float
    owner: str
    name: str
    description: str | None
    stars: int
    forks: int
    language: str | None
    topics: list
    language_breakdown: dict
    total_files: int
    total_lines: int
    health_score: float | None
    ai_summary: str | None
    last_commit_sha: str | None
    analysed_at: str | None


@router.post("/analyze")
@limiter.limit("5/hour")
async def analyze_repo(
    request: Request, body: AnalyzeRequest, db: Session = Depends(get_db)
):
    """
    Submit a GitHub URL for analysis.
    Returns immediately with repo_id and starts background job.
    """
    try:
        owner, name = parse_github_url(body.url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    full_name = f"{owner}/{name}"

    existing = db.query(Repository).filter_by(full_name=full_name).first()
    if existing and existing.status == "ready":
        return {
            "repo_id": str(existing.id),
            "full_name": full_name,
            "status": "ready",
            "cached": True,
        }

    if existing and existing.status in _IN_PROGRESS_STATUSES:
        last_update = existing.updated_at or datetime.min
        if datetime.utcnow() - last_update < _STALE_AFTER:
            return {
                "repo_id": str(existing.id),
                "full_name": full_name,
                "status": existing.status,
                "cached": False,
                "message": "Analysis already in progress for this repository.",
            }
        
    try:
        meta = await fetch_repo_meta(owner, name)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Cannot access repo: {str(e)}")

    if existing:
        existing.status = "pending"
        existing.progress = 0
        existing.status_message = "Re-analysis queued"
        db.commit()
        repo = existing
    else:
        repo = Repository(
            owner=owner,
            name=name,
            full_name=full_name,
            description=meta.description,
            url=meta.url,
            default_branch=meta.default_branch,
            stars=meta.stars,
            forks=meta.forks,
            language=meta.language,
            topics=meta.topics,
            license=meta.license,
            status="pending",
        )
        db.add(repo)
        db.commit()
        db.refresh(repo)

    # Queue background task
    ingest_repo.delay(full_name)

    set_job_status(
        full_name,
        {
            "status": "pending",
            "message": "Analysis queued",
            "progress": 0.0,
            "repo_id": str(repo.id),
        },
    )

    return {
        "repo_id": str(repo.id),
        "full_name": full_name,
        "status": "pending",
        "cached": False,
    }


@router.get("/{owner}/{name}/status")
async def get_status(owner: str, name: str, db: Session = Depends(get_db)):
    """Poll this endpoint to get live pipeline progress."""
    full_name = f"{owner}/{name}"

    # Try Redis first (fastest, most current)
    cached = get_job_status(full_name)
    if cached:
        repo = db.query(Repository).filter_by(full_name=full_name).first()
        if repo:
            cached["description"] = repo.description
            cached["stars"] = repo.stars
            cached["language"] = repo.language
            cached["language_breakdown"] = repo.language_breakdown or {}
            cached["total_files"] = repo.total_files
            cached["total_lines"] = repo.total_lines
            cached["ai_summary"] = repo.ai_summary
        return cached

    repo = db.query(Repository).filter_by(full_name=full_name).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    return {
        "status": repo.status,
        "message": repo.status_message or "",
        "progress": repo.progress,
        "repo_id": str(repo.id),
        "description": repo.description,
        "stars": repo.stars,
        "language": repo.language,
        "language_breakdown": repo.language_breakdown or {},
        "total_files": repo.total_files,
        "total_lines": repo.total_lines,
        "ai_summary": repo.ai_summary,
        "analysed_at": repo.analysed_at.isoformat() if repo.analysed_at else None,
    }


@router.get("/{owner}/{name}")
async def get_repo(owner: str, name: str, db: Session = Depends(get_db)):
    """Get full repo details once analysis is complete."""
    full_name = f"{owner}/{name}"
    repo = db.query(Repository).filter_by(full_name=full_name).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    return {
        "id": str(repo.id),
        "full_name": repo.full_name,
        "owner": repo.owner,
        "name": repo.name,
        "description": repo.description,
        "url": repo.url,
        "stars": repo.stars,
        "forks": repo.forks,
        "language": repo.language,
        "topics": repo.topics or [],
        "license": repo.license,
        "language_breakdown": repo.language_breakdown or {},
        "total_files": repo.total_files,
        "total_lines": repo.total_lines,
        "health_score": repo.health_score,
        "health_breakdown": repo.health_breakdown,
        "ai_summary": repo.ai_summary,
        "status": repo.status,
        "analysed_at": repo.analysed_at.isoformat() if repo.analysed_at else None,
    }
