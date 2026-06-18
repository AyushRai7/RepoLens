from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models import Repository, CodeFile, Dependency, ApiRoute, DbSchema

router = APIRouter(prefix="/structure", tags=["structure"])


# ── Functions ──────────────────────────────────────────────────────────────────

@router.get("/{owner}/{name}/functions")
async def get_functions(owner: str, name: str, db: Session = Depends(get_db)):
    full_name = f"{owner}/{name}"
    repo = db.query(Repository).filter_by(full_name=full_name).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Not found")

    files = db.query(CodeFile).filter_by(repo_id=repo.id).all()
    all_functions = []
    for f in files:
        for fn in f.functions or []:
            all_functions.append(
                {
                    "name": fn.get("name"),
                    "file": f.path,
                    "line": fn.get("line"),
                    "signature": fn.get("signature", ""),
                    "source_code": fn.get("source_code"),   # ← full body
                    "language": f.language,
                    "ai_description": fn.get("description"),
                }
            )
    return {"functions": all_functions, "total": len(all_functions)}


# ── Explain function (on-demand LLM) ──────────────────────────────────────────

class ExplainFunctionRequest(BaseModel):
    function_name: str
    file: str
    signature: str | None = None
    source_code: str | None = None
    language: str | None = None


@router.post("/{owner}/{name}/explain-function")
async def explain_function(
    owner: str,
    name: str,
    body: ExplainFunctionRequest,
    db: Session = Depends(get_db),
):
    """
    Generate a plain-English explanation of a function using Groq.
    Called on demand from the frontend — never fires automatically.
    """
    from groq import Groq
    from app.config import get_settings

    settings = get_settings()
    full_name = f"{owner}/{name}"

    repo = db.query(Repository).filter_by(full_name=full_name).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    # Prefer full source; fall back to signature-only if body wasn't captured
    code_block = body.source_code or body.signature or "(source not available)"
    lang = body.language or "unknown"

    prompt = f"""You are a senior software engineer reviewing a codebase.

Explain the following {lang} function in plain English. Be specific and concise (3-5 sentences):
1. What it does and its purpose in the codebase
2. The key logic, algorithm, or pattern it uses
3. What it returns or what side effects it produces
4. Any important edge cases or notable design decisions

Function name: {body.function_name}
File: {body.file}

```{lang}
{code_block[:4000]}
```

Write ONLY the explanation. No preamble, no headers, no bullet points — just clear prose."""

    client = Groq(api_key=settings.groq_api_key)

    for model in ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]:
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=350,
                temperature=0.2,
            )
            explanation = response.choices[0].message.content.strip()
            return {"explanation": explanation, "function_name": body.function_name}
        except Exception:
            continue

    raise HTTPException(status_code=500, detail="Groq inference failed on all models")


# ── Dependencies ───────────────────────────────────────────────────────────────

@router.get("/{owner}/{name}/dependencies")
async def get_dependencies(owner: str, name: str, db: Session = Depends(get_db)):
    full_name = f"{owner}/{name}"
    repo = db.query(Repository).filter_by(full_name=full_name).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Not found")

    deps = db.query(Dependency).filter_by(repo_id=repo.id).all()
    return {
        "dependencies": [
            {
                "name": d.name,
                "version": d.version,
                "ecosystem": d.ecosystem,
                "is_dev": d.is_dev,
                "ai_purpose": d.ai_purpose,
                "has_vulnerability": d.has_vulnerability,
                "vuln_details": d.vuln_details,
            }
            for d in deps
        ],
        "total": len(deps),
        "vulnerable_count": sum(1 for d in deps if d.has_vulnerability),
    }


# ── API Routes ─────────────────────────────────────────────────────────────────

@router.get("/{owner}/{name}/api-routes")
async def get_api_routes(owner: str, name: str, db: Session = Depends(get_db)):
    full_name = f"{owner}/{name}"
    repo = db.query(Repository).filter_by(full_name=full_name).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Not found")

    routes = db.query(ApiRoute).filter_by(repo_id=repo.id).all()
    return {
        "routes": [
            {
                "method": r.method,
                "path": r.path,
                "handler_file": r.handler_file,
                "handler_function": r.handler_function,
                "description": r.description,
                "handler_code": r.handler_code,
                "frontend_callers": r.frontend_callers or [],
            }
            for r in routes
        ],
        "total": len(routes),
    }


# ── DB Schema ──────────────────────────────────────────────────────────────────

@router.get("/{owner}/{name}/db-schema")
async def get_db_schema(owner: str, name: str, db: Session = Depends(get_db)):
    full_name = f"{owner}/{name}"
    repo = db.query(Repository).filter_by(full_name=full_name).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Not found")

    schemas = db.query(DbSchema).filter_by(repo_id=repo.id).all()
    return {
        "tables": [
            {
                "table_name": s.table_name,
                "source_file": s.source_file,
                "columns": s.columns or [],
                "relationships": s.relationships or [],
            }
            for s in schemas
        ],
        "total": len(schemas),
    }