from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models import Repository, Commit

router = APIRouter(prefix="/commits", tags=["commits"])


@router.get("/{owner}/{name}")
async def get_commits(
    owner: str, name: str, limit: int = 50, db: Session = Depends(get_db)
):
    full_name = f"{owner}/{name}"
    repo = db.query(Repository).filter_by(full_name=full_name).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Not found")

    commits = (
        db.query(Commit)
        .filter_by(repo_id=repo.id)
        .order_by(Commit.committed_at.desc())
        .limit(limit)
        .all()
    )

    return {
        "commits": [
            {
                "sha": c.sha,
                "sha_short": c.sha[:7],
                "message": c.message,
                "ai_summary": c.ai_summary,
                "author_name": c.author_name,
                "author_email": c.author_email,
                "committed_at": c.committed_at.isoformat() if c.committed_at else None,
                "files_changed": c.files_changed or [],
                "additions": c.additions,
                "deletions": c.deletions,
                "github_url": f"https://github.com/{owner}/{name}/commit/{c.sha}",
            }
            for c in commits
        ],
        "total": len(commits),
    }


@router.get("/{owner}/{name}/churn")
async def get_file_churn(owner: str, name: str, db: Session = Depends(get_db)):
    """Return file change frequency — used for the heatmap overlay."""
    full_name = f"{owner}/{name}"
    repo = db.query(Repository).filter_by(full_name=full_name).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Not found")

    commits = db.query(Commit).filter_by(repo_id=repo.id).all()
    churn: dict[str, int] = {}
    for c in commits:
        for f in c.files_changed or []:
            churn[f] = churn.get(f, 0) + 1

    # Normalize to 0-1 range
    if churn:
        max_val = max(churn.values())
        churn_normalized = {k: round(v / max_val, 3) for k, v in churn.items()}
    else:
        churn_normalized = {}

    return {"churn": churn_normalized}
