# RepoLens — AI-Powered GitHub Repository Analyzer

**Understand any GitHub repository instantly with AI.** 

RepoLens is an AI-powered repository analysis platform that transforms complex GitHub repositories into an interactive, searchable, and explainable knowledge base. Instead of manually exploring hundreds of files, developers can visualize project architecture, inspect relationships between components, and ask natural language questions about the codebase. 

The platform automatically clones a public GitHub repository, analyzes its structure, extracts architectural metadata, builds a semantic knowledge index, and enables contextual conversations powered by Large Language Models.

## Live Demo

- Application: https://repolens-ayush.vercel.app
- Backend API and interactive documentation: https://repolens-ayush.duckdns.org/docs
- Paste any public GitHub repository URL into the analyzer to see the full pipeline run end to end

## Problem and Motivation

- Understanding an unfamiliar codebase is one of the most time-consuming parts of software engineering
- File trees and README files only go so far real structure lives in import relationships, API surface, and data models
- RepoLens treats a repository as both a graph problem and a retrieval problem, automating that investigation

## Core Features

- **Architecture and dependency graph** — files are parsed and linked by imports and API calls into an interactive, layer-clustered node diagram
- **AI-generated architecture diagrams** — a Mermaid flowchart of the codebase, validated against the real file tree to prevent hallucinated paths
- **Retrieval-augmented chat** — WebSocket-based Q&A grounded in locally embedded source code, with optional file-scoped context
- **Dependency auditing** — manifests are cross-referenced against the OSV.dev vulnerability database for known CVEs
- **Database schema extraction** — ORM models and SQL are statically analyzed into an entity-relationship view
- **API route discovery** — route definitions are extracted with their handler functions and inferred descriptions
- **Commit history analysis** — commit diffs, contributor breakdowns, and AI-generated summaries of commit intent
- **Documentation generation** — AI-generated documentation for the full repository or any individual file, exportable as Markdown or HTML
- **Repository health scoring** — a composite score from code quality, dependency freshness, and commit activity

## Technology Stack

**Backend**
- FastAPI
- PostgreSQL with the `pgvector` extension
- Redis
- LangChain and LangGraph for agent orchestration
- Groq for LLM inference
- sentence-transformers for local embedding generation
- NetworkX for graph analysis
- tree-sitter for multi-language source parsing

**Frontend**
- Next.js 14 (App Router)
- TypeScript
- Tailwind CSS
- Zustand for client state management
- A node-based graph rendering library for the dependency visualization
- Mermaid for AI-generated architecture diagrams

**Infrastructure**
- Docker and Docker Compose for containerized deployment
- Caddy as a reverse proxy with automatic TLS certificate management
- Vercel for frontend hosting

## Running Locally

Clone the repository:
```bash
git clone https://github.com/AyushRai7/RepoLens.git
cd RepoLens
```

Populate `backend/.env` with the required credentials (Groq API key, GitHub token, database and cache connection strings), then bring up the full stack:
```bash
docker compose up -d --build
docker compose exec backend alembic upgrade head
```

- The API will be available at `http://localhost:8000`, with interactive documentation at `/docs`
- The frontend can be run separately:
```bash
cd frontend
npm install
npm run dev
```

## License

This project is available under the MIT License.
