from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional

from groq import Groq
from app.core.config import settings

logger = logging.getLogger(__name__)

# ── Client ─────────────────────────────────────────────────────────────────────

def _get_client() -> Groq:
    return Groq(
        api_key=settings.groq_api_key
    )


# ── Data classes ───────────────────────────────────────────────────────────────

@dataclass
class RepoContext:
    """All the structured data we feed to the LLM as context."""
    repo_name: str
    description: Optional[str]
    language: Optional[str]
    languages: dict          # {"TypeScript": 60.2, "Python": 39.8}
    stars: int
    topics: List[str]
    license: Optional[str]
    default_branch: str

    # From pipeline stages
    top_functions: List[dict]    # [{name, signature, docstring, file_path}]
    api_routes: List[dict]       # [{method, path, handler, auth, params}]
    db_tables: List[dict]        # [{name, columns}]
    dependencies: List[dict]     # [{name, version, ecosystem}]
    file_tree: List[str]         # top-level file/folder paths


@dataclass
class GeneratedDocs:
    readme: str
    api_reference: str
    architecture: str


# ── Prompt builders ────────────────────────────────────────────────────────────

def _build_readme_prompt(ctx: RepoContext) -> str:
    langs = ", ".join(f"{k} ({v:.0f}%)" for k, v in ctx.languages.items())
    topics = ", ".join(ctx.topics) if ctx.topics else "none"
    top_fns = "\n".join(
        f"  - {f['name']}{f.get('signature', '')} ({f.get('file_path', '')})"
        for f in ctx.top_functions[:20]
    )
    file_tree = "\n".join(f"  {p}" for p in ctx.file_tree[:30])
    routes_summary = "\n".join(
        f"  {r['method']} {r['path']}"
        for r in ctx.api_routes[:15]
    ) or "  (none detected)"
    deps_summary = ", ".join(
        f"{d['name']} {d.get('version', '')}"
        for d in ctx.dependencies[:15]
    ) or "(none)"

    return f"""You are a technical writer. Generate a professional, detailed README.md for this GitHub repository.

## Repository Information
- Name: {ctx.repo_name}
- Description: {ctx.description or 'not provided'}
- Primary language: {ctx.language or 'unknown'}
- Language breakdown: {langs}
- Stars: {ctx.stars}
- Topics: {topics}
- License: {ctx.license or 'not specified'}
- Default branch: {ctx.default_branch}

## File Structure (top-level)
{file_tree}

## Key Functions Detected
{top_fns or '  (none detected)'}

## API Routes Detected
{routes_summary}

## Dependencies
{deps_summary}

## Instructions
Write a README.md that includes:
1. **Project title and badges** (language, license, stars)
2. **Description** — what this project does in 2–3 sentences
3. **Features** — bullet list of key capabilities
4. **Tech Stack** — languages, frameworks, key libraries
5. **Getting Started** — prerequisites, installation steps, configuration
6. **Usage** — how to run the project, basic examples
7. **API Overview** — brief mention of endpoints if any exist
8. **Project Structure** — explain the folder layout
9. **Contributing** — standard contributing guidelines
10. **License** section

Use Markdown formatting. Be specific and accurate — only describe what exists in the codebase.
Do not invent features. Write in a clear, professional tone.
Output ONLY the markdown content, no preamble."""


def _build_api_reference_prompt(ctx: RepoContext) -> str:
    routes_detail = "\n".join(
        f"  {r['method']} {r['path']}\n"
        f"    Handler: {r.get('handler', 'unknown')}\n"
        f"    Auth: {r.get('auth', 'unknown')}\n"
        f"    Params: {r.get('params', [])}"
        for r in ctx.api_routes
    ) or "  No API routes detected."

    return f"""You are a technical writer. Generate a complete API Reference document in Markdown for this project.

## Project: {ctx.repo_name}
## Description: {ctx.description or 'not provided'}

## Detected API Endpoints
{routes_detail}

## Instructions
Write an API_REFERENCE.md that includes:
1. **Overview** — base URL format, authentication explanation, request/response format
2. **Authentication** — explain the auth mechanism if detected (JWT, API key, etc.)
3. **Endpoints** — for each endpoint:
   - Method + path as a heading (e.g. `## GET /api/users`)
   - Description of what it does
   - Request parameters (path, query, body) in a table
   - Example request (curl)
   - Example response (JSON)
4. **Error Responses** — common error codes and meanings
5. **Rate Limiting** — if detectable from the code

If no routes are detected, write a placeholder noting the API reference could not be auto-generated
and explain how to document it manually.

Use Markdown with tables and code blocks. Output ONLY the markdown content."""


def _build_architecture_prompt(ctx: RepoContext) -> str:
    tables_summary = "\n".join(
        f"  - {t['name']}: {', '.join(c['name'] for c in t.get('columns', [])[:6])}"
        for t in ctx.db_tables[:10]
    ) or "  (no database models detected)"

    langs = ", ".join(ctx.languages.keys())
    top_fns = "\n".join(
        f"  - {f['name']} in {f.get('file_path', 'unknown')}"
        for f in ctx.top_functions[:15]
    ) or "  (none detected)"

    return f"""You are a senior software architect. Generate an ARCHITECTURE.md document for this codebase.

## Repository: {ctx.repo_name}
## Description: {ctx.description or 'not provided'}
## Languages: {langs}
## License: {ctx.license or 'unknown'}

## Database Tables Detected
{tables_summary}

## Key Functions / Entry Points
{top_fns}

## API Surface
{len(ctx.api_routes)} endpoints detected: {', '.join(r['method'] + ' ' + r['path'] for r in ctx.api_routes[:8])}

## Dependencies (key ones)
{', '.join(d['name'] for d in ctx.dependencies[:20])}

## Instructions
Write an ARCHITECTURE.md that includes:
1. **System Overview** — high-level description of what the system does and how it's structured
2. **Technology Choices** — why these languages/frameworks were likely chosen
3. **Directory Structure** — explain what each major folder/module does
4. **Data Flow** — describe how data moves through the system (request → processing → storage → response)
5. **Database Design** — describe detected tables and their relationships
6. **Key Components** — explain the most important classes/functions and their roles
7. **API Design** — describe the API layer if present
8. **Dependencies & Integrations** — explain key external libraries and why they're used
9. **Development Notes** — how to understand the codebase as a new contributor

Be specific about what was detected. Do not invent components.
Output ONLY the markdown content."""


# ── LLM call ───────────────────────────────────────────────────────────────────

def _call_claude(prompt: str, max_tokens: int = 4096) -> str:
    """
    Call Claude claude-sonnet-4-20250514 with a prompt and return the response text.
    Uses a simple single-turn call (not streaming) since this is a background task.
    """
    client = _get_client()

    logger.debug("Calling Claude for doc generation (~%d prompt chars)", len(prompt))

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=max_tokens,
        messages=[
            {"role": "user", "content": prompt}
        ],
    )

    return message.content[0].text


# ── Public entry point ─────────────────────────────────────────────────────────

def generate_docs(ctx: RepoContext) -> GeneratedDocs:
    """
    Generate all three documentation files for a repo.

    Args:
        ctx: RepoContext containing all structured data about the repo.

    Returns:
        GeneratedDocs with readme, api_reference, and architecture strings.

    This function makes 3 separate Claude API calls, one for each doc.
    Each call takes ~10–20 seconds depending on repo complexity.
    """
    logger.info("Starting doc generation for repo: %s", ctx.repo_name)

    # README
    logger.info("Generating README.md...")
    readme = _call_claude(_build_readme_prompt(ctx), max_tokens=4096)

    # API Reference
    logger.info("Generating API_REFERENCE.md...")
    api_reference = _call_claude(_build_api_reference_prompt(ctx), max_tokens=3000)

    # Architecture
    logger.info("Generating ARCHITECTURE.md...")
    architecture = _call_claude(_build_architecture_prompt(ctx), max_tokens=3000)

    logger.info(
        "Doc generation complete for %s. Sizes: README=%d, API=%d, ARCH=%d chars",
        ctx.repo_name, len(readme), len(api_reference), len(architecture)
    )

    return GeneratedDocs(
        readme=readme,
        api_reference=api_reference,
        architecture=architecture,
    )


def build_combined_markdown(docs: GeneratedDocs, repo_name: str) -> str:
    """
    Combine all three docs into a single markdown file for download.
    The frontend's "Download" button hits this combined output.
    """
    return f"""# {repo_name} — Documentation Pack

---

{docs.readme}

---

{docs.api_reference}

---

{docs.architecture}
"""