from sqlalchemy import Column, String, Integer, Float, Text, DateTime, JSON, Boolean, ForeignKey
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid


class Base(DeclarativeBase):
    pass


class Repository(Base):
    __tablename__ = "repositories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner = Column(String(255), nullable=False, index=True)
    name = Column(String(255), nullable=False, index=True)
    full_name = Column(String(511), nullable=False, unique=True)  # owner/name
    description = Column(Text, nullable=True)
    url = Column(String(512), nullable=False)
    default_branch = Column(String(100), default="main")
    stars = Column(Integer, default=0)
    forks = Column(Integer, default=0)
    language = Column(String(100), nullable=True)
    topics = Column(JSON, default=list)
    license = Column(String(100), nullable=True)
    last_commit_sha = Column(String(40), nullable=True)
    last_commit_date = Column(DateTime, nullable=True)

    # Analysis state
    status = Column(String(50), default="pending")
    # pending | fetching | parsing | embedding | ready | failed
    status_message = Column(Text, nullable=True)
    progress = Column(Float, default=0.0)  # 0.0 to 1.0
    health_score = Column(Float, nullable=True)
    health_breakdown = Column(JSON, nullable=True)
    ai_summary = Column(Text, nullable=True)
    language_breakdown = Column(JSON, nullable=True)  # {lang: percentage}
    total_files = Column(Integer, default=0)
    total_lines = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    analysed_at = Column(DateTime, nullable=True)

    # Relationships
    files = relationship("CodeFile", back_populates="repo", cascade="all, delete-orphan")
    graph_edges = relationship("GraphEdge", back_populates="repo", cascade="all, delete-orphan")
    commits = relationship("Commit", back_populates="repo", cascade="all, delete-orphan")
    dependencies = relationship("Dependency", back_populates="repo", cascade="all, delete-orphan")
    api_routes = relationship("ApiRoute", back_populates="repo", cascade="all, delete-orphan")
    db_schemas = relationship("DbSchema", back_populates="repo", cascade="all, delete-orphan")


class CodeFile(Base):
    __tablename__ = "code_files"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repo_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id"), nullable=False, index=True)
    path = Column(String(1024), nullable=False)       # relative path in repo
    name = Column(String(255), nullable=False)
    extension = Column(String(50), nullable=True)
    language = Column(String(100), nullable=True)
    size_bytes = Column(Integer, default=0)
    lines = Column(Integer, default=0)
    content = Column(Text, nullable=True)             # raw source (capped)
    ai_summary = Column(Text, nullable=True)          # one-line AI description
    imports = Column(JSON, default=list)              # list of imported paths
    exports = Column(JSON, default=list)              # list of exported names
    functions = Column(JSON, default=list)            # [{name, line, signature, description}]
    classes = Column(JSON, default=list)              # [{name, line, methods}]
    embedding_stored = Column(Boolean, default=False)

    repo = relationship("Repository", back_populates="files")


class GraphEdge(Base):
    __tablename__ = "graph_edges"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repo_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id"), nullable=False, index=True)
    source_path = Column(String(1024), nullable=False)
    target_path = Column(String(1024), nullable=False)
    edge_type = Column(String(50), default="import")  # import | call | extends

    repo = relationship("Repository", back_populates="graph_edges")


class Commit(Base):
    __tablename__ = "commits"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repo_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id"), nullable=False, index=True)
    sha = Column(String(40), nullable=False)
    message = Column(Text, nullable=True)
    ai_summary = Column(Text, nullable=True)          # plain-English explanation
    author_name = Column(String(255), nullable=True)
    author_email = Column(String(255), nullable=True)
    committed_at = Column(DateTime, nullable=True)
    files_changed = Column(JSON, default=list)        # list of file paths changed
    additions = Column(Integer, default=0)
    deletions = Column(Integer, default=0)

    repo = relationship("Repository", back_populates="commits")


class Dependency(Base):
    __tablename__ = "dependencies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repo_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id"), nullable=False, index=True)

    name = Column(String(255), nullable=False)
    version = Column(String(100), nullable=True)
    ecosystem = Column(String(50), nullable=True)

    ai_purpose = Column(Text, nullable=True)

    is_dev = Column(Boolean, default=False)

    has_vulnerability = Column(Boolean, default=False)
    vuln_details = Column(JSON, nullable=True)

    # ADD THESE BACK
    latest_version = Column(String(100), nullable=True)
    update_status = Column(String(50), nullable=True)
    license = Column(String(100), nullable=True)
    license_ok = Column(Boolean, default=True)
    description = Column(Text, nullable=True)
    homepage = Column(String(512), nullable=True)

    repo = relationship("Repository", back_populates="dependencies")


class ApiRoute(Base):
    __tablename__ = "api_routes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repo_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id"), nullable=False, index=True)
    method = Column(String(10), nullable=False)       # GET, POST, etc.
    path = Column(String(512), nullable=False)
    handler_file = Column(String(1024), nullable=True)
    handler_function = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    handler_code = Column(Text, nullable=True)        # raw source of the handler function
    frontend_callers = Column(JSON, default=list)     # [{file, line, snippet}]

    repo = relationship("Repository", back_populates="api_routes")


class DbSchema(Base):
    __tablename__ = "db_schemas"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repo_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id"), nullable=False, index=True)
    table_name = Column(String(255), nullable=False)
    source_file = Column(String(1024), nullable=True)
    columns = Column(JSON, default=list)              # [{name, type, nullable, pk, fk}]
    relationships = Column(JSON, default=list)        # [{to_table, type}]

    repo = relationship("Repository", back_populates="db_schemas")