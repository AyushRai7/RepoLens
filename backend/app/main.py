import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from contextlib import asynccontextmanager

from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from app.core.limiter import limiter

from app.config import get_settings
from app.db.session import create_tables
from app.api import repos, graph, chat, structure, commits, docs

settings = get_settings()

os.environ["LANGCHAIN_TRACING_V2"] = settings.langchain_tracing_v2
os.environ["LANGCHAIN_API_KEY"] = settings.langchain_api_key
os.environ["LANGCHAIN_PROJECT"] = settings.langchain_project


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()
    print("✓ Database tables created")
    print("✓ RepoLens API started")
    yield
    print("RepoLens API shutting down")


_fastapi_app = FastAPI(
    title="RepoLens API",
    description="Understand any GitHub repository instantly with AI",
    version="1.0.0",
    lifespan=lifespan,
)

_fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

_fastapi_app.include_router(repos.router,      prefix="/api")
_fastapi_app.include_router(graph.router,      prefix="/api")
_fastapi_app.include_router(chat.router,       prefix="/api")
_fastapi_app.include_router(structure.router,  prefix="/api")
_fastapi_app.include_router(commits.router,    prefix="/api")
_fastapi_app.include_router(docs.router,       prefix="/api")


@_fastapi_app.get("/")
async def root():
    return {"name": "RepoLens API", "version": "1.0.0", "status": "running", "docs": "/docs"}


@_fastapi_app.get("/health")
async def health():
    return {"status": "healthy"}


@_fastapi_app.get("/api/health")
async def api_health():
    """Convenience alias — frontend can ping /api/health."""
    return {"status": "healthy"}


class _WSCORSWrapper:
    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        if scope["type"] == "websocket":
            scope = {
                **scope,
                "headers": [
                    (k, v) for k, v in scope["headers"]
                    if k.lower() != b"origin"
                ],
            }
        await self.inner(scope, receive, send)


app = _WSCORSWrapper(_fastapi_app)

