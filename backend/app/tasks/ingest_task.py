import asyncio
from datetime import datetime
from sqlalchemy.orm import Session
from app.tasks.celery_app import celery_app
from app.db.session import SessionLocal
from app.db.cache import set_job_status
from app.services.route_extractor import extract_routes
from app.db.models import (
    ApiRoute,
    DbSchema,
    Repository,
    CodeFile,
    GraphEdge,
    Commit,
    Dependency,
)
from app.services.github_fetcher import (
    fetch_repo_meta,
    fetch_file_tree,
    fetch_file_content,
    fetch_commits,
    fetch_languages,
)
from app.services.ast_parser import parse_file
from app.services.graph_builder import build_graph
from app.services.dep_analyzer import analyze_dependencies
from app.services.schema_extractor import extract_schema
from app.services.health_scorer import compute_health_score


def update_status(
    db: Session, repo: Repository, status: str, message: str, progress: float
):
    repo.status = status
    repo.status_message = message
    repo.progress = progress
    repo.updated_at = datetime.utcnow()
    db.commit()
    set_job_status(
        repo.full_name,
        {
            "status": status,
            "message": message,
            "progress": progress,
            "repo_id": str(repo.id),
        },
    )


@celery_app.task(bind=True, max_retries=2)
def ingest_repo(self, repo_full_name: str):
    """
    Full pipeline task: fetch → parse → graph → deps → schema → commits → health → done.
    Runs as a background Celery task.
    """
    db = SessionLocal()
    try:
        repo = db.query(Repository).filter_by(full_name=repo_full_name).first()
        if not repo:
            return {"error": "Repo not found in DB"}

        owner, name = repo_full_name.split("/", 1)

        # ── Stage 1: Fetch repo metadata ─────────────────────────
        update_status(db, repo, "fetching", "Fetching repository metadata...", 0.05)
        meta = asyncio.run(fetch_repo_meta(owner, name))
        languages = asyncio.run(fetch_languages(owner, name))

        repo.description = meta.description
        repo.default_branch = meta.default_branch
        repo.stars = meta.stars
        repo.forks = meta.forks
        repo.language = meta.language
        repo.topics = meta.topics
        repo.license = meta.license
        repo.last_commit_sha = meta.last_commit_sha
        repo.language_breakdown = languages
        db.commit()

        # ── Stage 2: Fetch file tree ──────────────────────────────
        update_status(db, repo, "fetching", "Fetching file tree...", 0.10)
        files = asyncio.run(fetch_file_tree(owner, name, meta.default_branch))
        repo.total_files = len(files)
        db.commit()

        # ── Stage 3: Parse each file ──────────────────────────────
        parsed_files = []
        file_dicts = []  # keep a serializable version for health scorer

        for i, file_info in enumerate(files):
            progress = 0.10 + (i / max(len(files), 1)) * 0.35
            if i % 20 == 0:
                update_status(
                    db, repo, "parsing", f"Parsing files... {i}/{len(files)}", progress
                )

            content = asyncio.run(fetch_file_content(file_info.download_url))
            if not content:
                continue

            parsed = parse_file(content, file_info.path, file_info.extension)
            parsed_files.append(parsed)
            file_dicts.append(
                {
                    "path": file_info.path,
                    "content": content,
                    "language": parsed.language,
                }
            )

            code_file = CodeFile(
                repo_id=repo.id,
                path=file_info.path,
                name=file_info.name,
                extension=file_info.extension,
                language=parsed.language,
                size_bytes=file_info.size_bytes,
                lines=parsed.lines,
                content=content[:50000],  # cap at 50k chars
                imports=parsed.imports,
                exports=parsed.exports,
                functions=parsed.functions,
                classes=parsed.classes,
            )
            db.add(code_file)

        db.commit()
        repo.total_lines = sum(p.lines for p in parsed_files)
        db.commit()

        routes = extract_routes(file_dicts)
        for route in routes:
            db.add(
                ApiRoute(
                    repo_id=repo.id,
                    method=route["method"],
                    path=route["path"],
                    handler_file=route["handler_file"],
                    handler_function=route["handler_function"],
                    description=route["description"],
                    handler_code=route.get("handler_code"),
                    frontend_callers=route.get("frontend_callers", []),
                )
            )
        db.commit()

        # ── Stage 4: Build graph ──────────────────────────────────
        update_status(db, repo, "graphing", "Building relationship graph...", 0.50)
        graph_data = build_graph(parsed_files)

        for edge in graph_data["edges"]:
            db.add(
                GraphEdge(
                    repo_id=repo.id,
                    source_path=edge["source"],
                    target_path=edge["target"],
                    edge_type=edge["data"]["edge_type"],
                )
            )
        db.commit()

        # Cache full graph JSON in Redis for fast frontend retrieval
        from app.db.cache import set_cache

        set_cache(f"graph:{repo.full_name}", graph_data, ttl_seconds=120)

        # ── Stage 5: Extract dependencies ─────────────────────────
        update_status(db, repo, "analyzing", "Analyzing dependencies...", 0.62)

        # Only pass dependency manifest files, not all source files
        MANIFEST_NAMES = {
            "requirements.txt",
            "package.json",
            "cargo.toml",
            "go.mod",
            "pipfile",
            "pyproject.toml",
        }
        dep_files = [
            {"path": cf.path, "content": cf.content}
            for cf in db.query(CodeFile).filter_by(repo_id=repo.id).all()
            if cf.content and cf.name.lower() in MANIFEST_NAMES
        ]

        deps = analyze_dependencies(dep_files)

        for dep in deps:
            has_vuln = len(dep.cves) > 0
            db.add(
                Dependency(
                    repo_id=repo.id,
                    name=dep.name,
                    version=dep.current_version,
                    latest_version=dep.latest_version,
                    update_status=dep.update_status,
                    license=dep.license,
                    license_ok=dep.license_ok,
                    is_dev=dep.is_dev,
                    ecosystem=dep.ecosystem,
                    description=dep.description,
                    homepage=dep.homepage,
                    has_vulnerability=has_vuln,
                    vuln_details=(
                        [
                            {
                                "cve_id": c.cve_id,
                                "severity": c.severity,
                                "summary": c.summary,
                                "cvss_score": c.cvss_score,
                                "url": c.url,
                                "fixed_in": c.fixed_in,
                            }
                            for c in dep.cves
                        ]
                        if has_vuln
                        else []
                    ),
                )
            )
        db.commit()

        # ── Stage 6: Extract DB schemas ───────────────────────────
        update_status(db, repo, "analyzing", "Extracting database schemas...", 0.75)

        # FIX: extract_schema expects ("", List[dict]) not a dict
        schemas = extract_schema("", file_dicts)

        for table in schemas.tables:
            db.add(
                DbSchema(
                    repo_id=repo.id,
                    table_name=table.name,
                    source_file=table.source_file,
                    columns=[
                        {
                            "name": c.name,
                            "type": c.col_type,
                            "is_primary": c.is_primary,
                            "is_foreign_key": c.is_foreign_key,
                            "is_nullable": c.is_nullable,
                            "is_unique": c.is_unique,
                            "references": c.references,
                        }
                        for c in table.columns
                    ],
                    relationships=[
                        {
                            "from_table": r.from_table,
                            "from_column": r.from_column,
                            "to_table": r.to_table,
                            "to_column": r.to_column,
                            "cardinality": r.cardinality,
                        }
                        for r in schemas.relationships
                        if r.from_table == table.name
                    ],
                )
            )
        db.commit()

        # ── Stage 7: Fetch commits ─────────────────────────────────
        update_status(db, repo, "analyzing", "Fetching commit history...", 0.85)
        commits_raw = asyncio.run(fetch_commits(owner, name, limit=50))

        for c in commits_raw:
            db.add(
                Commit(
                    repo_id=repo.id,
                    sha=c["sha"],
                    message=c["message"],
                    author_name=c["author_name"],
                    author_email=c["author_email"],
                    committed_at=datetime.fromisoformat(
                        c["committed_at"].replace("Z", "+00:00")
                    ),
                    files_changed=c["files_changed"],
                    additions=c["additions"],
                    deletions=c["deletions"],
                )
            )
        db.commit()

        # ── Stage 8: Compute health score ─────────────────────────
        update_status(db, repo, "analyzing", "Computing health score...", 0.93)

        all_functions = [fn for pf in parsed_files for fn in pf.functions]
        commit_dicts = [
            {
                "date": c["committed_at"],
                "message": c["message"],
                "author": c["author_name"],
            }
            for c in commits_raw
        ]
        dep_dicts = [
            {
                "name": dep.name,
                "update_status": dep.update_status,
                "cves": [{"severity": c.severity} for c in dep.cves],
            }
            for dep in deps
        ]

        health = compute_health_score(
            files=file_dicts,
            functions=all_functions,
            commits=commit_dicts,
            dependencies=dep_dicts,
            stars=meta.stars,
            forks=meta.forks,
            open_issues=0,  # not fetched from GitHub API currently
            watchers=0,
            pushed_at=None,
        )

        repo.health_score = health.overall
        repo.health_grade = health.grade
        repo.health_trend = health.trend
        repo.health_breakdown = [
            {
                "key": cat.key,
                "label": cat.label,
                "score": cat.score,
                "weight": cat.weight,
                "description": cat.description,
            }
            for cat in health.categories
        ]
        db.commit()

        # ── Done ───────────────────────────────────────────────────
        repo.analysed_at = datetime.utcnow()
        update_status(db, repo, "ready", "Analysis complete", 1.0)
        return {"status": "ready", "repo": repo_full_name}

    except Exception as exc:
        if db:
            try:
                repo = db.query(Repository).filter_by(full_name=repo_full_name).first()
                if repo:
                    update_status(db, repo, "failed", str(exc)[:500], 0)
            except Exception:
                pass  # don't let error handling crash
        raise self.retry(exc=exc, countdown=10)
    finally:
        db.close()


# After collecting all routes, resolve prefixes
def resolve_route_prefixes(parsed_files: list) -> list:
    """
    Find app.use('/prefix', routerVar) calls and prepend
    the prefix to all routes defined in the linked file.
    """
    # Map: variable name → file path
    router_vars = {}
    prefix_map = {}  # file_path → prefix

    for pf in parsed_files:
        content_lines = "\n".join(str(f) for f in pf.functions)

        # Find: app.use('/api/auth', authRoutes)
        for m in re.finditer(
            r"app\.use\s*\(\s*['\"`]([^'\"` ]+)['\"`]\s*,\s*(\w+)",
            "\n".join(pf.imports),
        ):
            prefix = m.group(1)
            var_name = m.group(2)
            prefix_map[var_name] = prefix

    # Apply prefixes
    resolved = []
    for pf in parsed_files:
        for route in pf.routes:
            resolved.append(route)
    return resolved