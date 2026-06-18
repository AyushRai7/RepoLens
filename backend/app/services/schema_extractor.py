from __future__ import annotations

import ast
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ── Data classes ───────────────────────────────────────────────────────────────


@dataclass
class ColumnInfo:
    name: str
    col_type: str
    is_primary: bool = False
    is_foreign_key: bool = False
    is_nullable: bool = True
    is_unique: bool = False
    default_value: Optional[str] = None
    references: Optional[Dict[str, str]] = None  # {"table": "users", "column": "id"}


@dataclass
class TableInfo:
    name: str
    columns: List[ColumnInfo] = field(default_factory=list)
    source_file: str = ""
    orm: str = ""  # "sqlalchemy" | "django" | "prisma" | "typeorm"


@dataclass
class RelationshipInfo:
    from_table: str
    from_column: str
    to_table: str
    to_column: str
    cardinality: str = "1:N"  # "1:1" | "1:N" | "N:M"


@dataclass
class SchemaResult:
    tables: List[TableInfo] = field(default_factory=list)
    relationships: List[RelationshipInfo] = field(default_factory=list)


# ── SQLAlchemy extractor ───────────────────────────────────────────────────────

# Maps SQLAlchemy column type names to simpler display types
_SA_TYPE_MAP: Dict[str, str] = {
    "Integer": "integer",
    "BigInteger": "bigint",
    "SmallInteger": "smallint",
    "String": "varchar",
    "Text": "text",
    "Unicode": "varchar",
    "Boolean": "boolean",
    "DateTime": "timestamp",
    "Date": "date",
    "Time": "time",
    "Float": "float",
    "Numeric": "decimal",
    "DECIMAL": "decimal",
    "JSON": "json",
    "JSONB": "jsonb",
    "LargeBinary": "bytea",
    "UUID": "uuid",
    "Enum": "enum",
}


def _sa_type_name(node: ast.expr) -> str:
    """Extract a readable type name from a SQLAlchemy Column(...) call."""
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name):
            return _SA_TYPE_MAP.get(node.func.id, node.func.id.lower())
        if isinstance(node.func, ast.Attribute):
            return _SA_TYPE_MAP.get(node.func.attr, node.func.attr.lower())
    if isinstance(node, ast.Name):
        return _SA_TYPE_MAP.get(node.id, node.id.lower())
    return "unknown"


def _extract_sqlalchemy(source: str, file_path: str) -> List[TableInfo]:
    """
    Parse Python source with ast and find SQLAlchemy ORM models.
    Looks for classes that inherit from Base, db.Model, or DeclarativeBase.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    tables: List[TableInfo] = []
    sa_bases = {"Base", "db.Model", "DeclarativeBase", "DeclarativeBaseNoMeta"}

    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue

        # Check if class inherits from a SQLAlchemy base
        base_names = set()
        for base in node.bases:
            if isinstance(base, ast.Name):
                base_names.add(base.id)
            elif isinstance(base, ast.Attribute):
                base_names.add(
                    f"{base.value.id}.{base.attr}"
                    if isinstance(base.value, ast.Name)
                    else base.attr
                )

        if not base_names.intersection(sa_bases):
            continue

        table = TableInfo(name=node.name, source_file=file_path, orm="sqlalchemy")

        # Scan class body for Column assignments
        for stmt in node.body:
            if not isinstance(stmt, ast.Assign):
                continue
            for target in stmt.targets:
                if not isinstance(target, ast.Name):
                    continue
                col_name = target.id
                if not isinstance(stmt.value, ast.Call):
                    continue

                # Only process Column(...) calls
                func = stmt.value.func
                func_name = (
                    func.id
                    if isinstance(func, ast.Name)
                    else (func.attr if isinstance(func, ast.Attribute) else "")
                )
                if func_name not in ("Column", "mapped_column"):
                    continue

                col = ColumnInfo(name=col_name, col_type="unknown")

                # First positional arg is usually the type
                if stmt.value.args:
                    col.col_type = _sa_type_name(stmt.value.args[0])

                # Parse keyword arguments
                for kw in stmt.value.keywords:
                    if (
                        kw.arg == "primary_key"
                        and isinstance(kw.value, ast.Constant)
                        and kw.value.value
                    ):
                        col.is_primary = True
                        col.is_nullable = False
                    elif kw.arg == "nullable" and isinstance(kw.value, ast.Constant):
                        col.is_nullable = bool(kw.value.value)
                    elif (
                        kw.arg == "unique"
                        and isinstance(kw.value, ast.Constant)
                        and kw.value.value
                    ):
                        col.is_unique = True
                    elif kw.arg == "ForeignKey":
                        col.is_foreign_key = True

                # Check for ForeignKey in positional args
                for arg in stmt.value.args:
                    if isinstance(arg, ast.Call):
                        fk_func = arg.func
                        fk_name = (
                            fk_func.id
                            if isinstance(fk_func, ast.Name)
                            else (
                                fk_func.attr
                                if isinstance(fk_func, ast.Attribute)
                                else ""
                            )
                        )
                        if fk_name == "ForeignKey" and arg.args:
                            col.is_foreign_key = True
                            if isinstance(arg.args[0], ast.Constant):
                                ref = str(arg.args[0].value)  # e.g. "users.id"
                                parts = ref.split(".")
                                if len(parts) == 2:
                                    col.references = {
                                        "table": parts[0],
                                        "column": parts[1],
                                    }

                table.columns.append(col)

        if table.columns:
            tables.append(table)

    return tables


# ── Django ORM extractor ───────────────────────────────────────────────────────

_DJANGO_TYPE_MAP: Dict[str, str] = {
    "AutoField": "serial",
    "BigAutoField": "bigserial",
    "IntegerField": "integer",
    "BigIntegerField": "bigint",
    "SmallIntegerField": "smallint",
    "CharField": "varchar",
    "TextField": "text",
    "SlugField": "varchar",
    "EmailField": "varchar",
    "URLField": "varchar",
    "BooleanField": "boolean",
    "NullBooleanField": "boolean",
    "DateTimeField": "timestamp",
    "DateField": "date",
    "TimeField": "time",
    "FloatField": "float",
    "DecimalField": "decimal",
    "JSONField": "json",
    "BinaryField": "bytea",
    "UUIDField": "uuid",
    "ForeignKey": "integer",
    "OneToOneField": "integer",
    "ManyToManyField": "integer",
}


def _extract_django(
    source: str, file_path: str
) -> Tuple[List[TableInfo], List[RelationshipInfo]]:
    """
    Parse Python source and find Django ORM models.
    Looks for classes inheriting from models.Model.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return [], []

    tables: List[TableInfo] = []
    relationships: List[RelationshipInfo] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue

        is_django_model = any(
            (isinstance(b, ast.Attribute) and b.attr == "Model")
            or (isinstance(b, ast.Name) and b.id == "Model")
            for b in node.bases
        )
        if not is_django_model:
            continue

        # Convert CamelCase class name to snake_case table name
        table_name = re.sub(r"(?<!^)(?=[A-Z])", "_", node.name).lower()
        table = TableInfo(name=table_name, source_file=file_path, orm="django")

        # Django adds implicit `id` primary key
        table.columns.append(
            ColumnInfo(
                name="id", col_type="bigserial", is_primary=True, is_nullable=False
            )
        )

        for stmt in node.body:
            if not isinstance(stmt, ast.Assign):
                continue
            for target in stmt.targets:
                if not isinstance(target, ast.Name):
                    continue
                col_name = target.id
                if not isinstance(stmt.value, ast.Call):
                    continue

                func = stmt.value.func
                field_type = ""
                if isinstance(func, ast.Attribute):
                    field_type = func.attr
                elif isinstance(func, ast.Name):
                    field_type = func.id

                if field_type not in _DJANGO_TYPE_MAP:
                    continue

                col = ColumnInfo(
                    name=col_name
                    + ("_id" if field_type in ("ForeignKey", "OneToOneField") else ""),
                    col_type=_DJANGO_TYPE_MAP[field_type],
                )

                # Parse kwargs
                for kw in stmt.value.keywords:
                    if kw.arg == "null" and isinstance(kw.value, ast.Constant):
                        col.is_nullable = bool(kw.value.value)
                    elif kw.arg == "unique" and isinstance(kw.value, ast.Constant):
                        col.is_unique = bool(kw.value.value)
                    elif (
                        kw.arg == "primary_key"
                        and isinstance(kw.value, ast.Constant)
                        and kw.value.value
                    ):
                        col.is_primary = True

                # Handle FK relationships
                if field_type == "ForeignKey" and stmt.value.args:
                    col.is_foreign_key = True
                    ref_arg = stmt.value.args[0]
                    ref_model = (
                        ref_arg.id
                        if isinstance(ref_arg, ast.Name)
                        else (
                            ref_arg.value if isinstance(ref_arg, ast.Constant) else ""
                        )
                    )
                    if ref_model:
                        ref_table = re.sub(r"(?<!^)(?=[A-Z])", "_", ref_model).lower()
                        col.references = {"table": ref_table, "column": "id"}
                        relationships.append(
                            RelationshipInfo(
                                from_table=table_name,
                                from_column=col.name,
                                to_table=ref_table,
                                to_column="id",
                                cardinality="1:N",
                            )
                        )

                if field_type == "OneToOneField":
                    col.is_foreign_key = True
                    col.is_unique = True

                if field_type == "ManyToManyField":
                    # M2M creates a join table; skip column, add relationship
                    if stmt.value.args:
                        ref_arg = stmt.value.args[0]
                        ref_model = ref_arg.id if isinstance(ref_arg, ast.Name) else ""
                        if ref_model:
                            ref_table = re.sub(
                                r"(?<!^)(?=[A-Z])", "_", ref_model
                            ).lower()
                            relationships.append(
                                RelationshipInfo(
                                    from_table=table_name,
                                    from_column=col_name,
                                    to_table=ref_table,
                                    to_column="id",
                                    cardinality="N:M",
                                )
                            )
                    continue

                table.columns.append(col)

        if len(table.columns) > 1:  # more than just the implicit id
            tables.append(table)

    return tables, relationships


# ── Prisma schema extractor ────────────────────────────────────────────────────

_PRISMA_TYPE_MAP: Dict[str, str] = {
    "Int": "integer",
    "BigInt": "bigint",
    "String": "varchar",
    "Json": "json",
    "Boolean": "boolean",
    "DateTime": "timestamp",
    "Float": "float",
    "Decimal": "decimal",
    "Bytes": "bytea",
}


def _extract_prisma_model_bodies(source: str) -> List[Tuple[str, str]]:
    """
    Extract (model_name, body) pairs from a Prisma schema using brace-counting
    instead of a [^}]+ regex.

    Why: Prisma model bodies can contain nested braces inside @default({...})
    or @@index([...]) or multi-line @relation(...) calls.  The simple [^}]+
    regex stops at the first } it encounters, which cuts the body short and
    causes fields defined after any nested brace to be silently dropped.
    """
    models: List[Tuple[str, str]] = []
    for m in re.finditer(r"\bmodel\s+(\w+)\s*\{", source):
        name = m.group(1)
        start = m.end() - 1  # position of the opening {
        depth = 0
        i = start
        while i < len(source):
            if source[i] == "{":
                depth += 1
            elif source[i] == "}":
                depth -= 1
                if depth == 0:
                    models.append((name, source[start + 1 : i]))
                    break
            i += 1
    return models


def _extract_prisma(
    source: str, file_path: str
) -> Tuple[List[TableInfo], List[RelationshipInfo]]:
    """
    Parse a Prisma schema file (.prisma) and extract tables, columns, and
    relationships with correct PK / FK / nullable flags.

    Key fixes vs the original:
    1. Model body extraction uses brace-counting (not [^}]+) so nested braces
       inside @default({}) or @relation() arguments don't truncate the body.
    2. FK scalar columns are identified by reading the `fields: [...]` list
       from every @relation(...) annotation in the body *before* iterating
       fields — so `userId String` gets is_foreign_key=True even though the
       @relation attribute lives on the virtual relation field, not on userId.
    3. is_nullable is set correctly: False by default, True only when the
       Prisma type is suffixed with `?`.
    4. Virtual relation fields (e.g. `user User @relation(...)`) are skipped
       as actual DB columns but still recorded as RelationshipInfo entries.
    """
    tables: List[TableInfo] = []
    relationships: List[RelationshipInfo] = []

    # Regex to pull scalar FK field names out of @relation(fields: [...])
    _relation_fields_re = re.compile(
        r"@relation\s*\([^)]*fields\s*:\s*\[([^\]]+)\]", re.DOTALL
    )
    # Regex to pull the referenced model out of @relation(..., references: [...])
    _relation_refs_re = re.compile(
        r"@relation\s*\([^)]*references\s*:\s*\[([^\]]+)\]", re.DOTALL
    )
    # Per-field line pattern
    _field_re = re.compile(r"^\s*(\w+)\s+([\w\[\]?!]+)(.*?)$", re.MULTILINE)

    for model_name, body in _extract_prisma_model_bodies(source):
        table = TableInfo(name=model_name.lower(), source_file=file_path, orm="prisma")

        # ── Step 1: collect FK scalar names from all @relation annotations ──
        # Example line:  user  User  @relation(fields: [userId], references: [id])
        # We need to mark "userId" as is_foreign_key=True on the scalar column.
        fk_scalar_names: set = set()
        relation_targets: Dict[str, str] = {}  # scalar_name -> referenced_table

        for rel_line_m in _field_re.finditer(body):
            modifiers = rel_line_m.group(3)
            if "@relation" not in modifiers:
                continue
            raw_type_full = rel_line_m.group(2)
            raw_type = raw_type_full.replace("?", "").replace("!", "").replace("[]", "")

            # Extract scalar field names from fields:[...]
            fm = _relation_fields_re.search(modifiers)
            if fm:
                scalars = [s.strip() for s in fm.group(1).split(",")]
                fk_scalar_names.update(scalars)
                # Map each scalar to the referenced model (for references dict)
                for s in scalars:
                    relation_targets[s] = raw_type.lower()

            # Also record this as a relationship
            cardinality = "N:M" if "[]" in raw_type_full else "1:N"
            relationships.append(
                RelationshipInfo(
                    from_table=model_name.lower(),
                    from_column=rel_line_m.group(1),
                    to_table=raw_type.lower(),
                    to_column="id",
                    cardinality=cardinality,
                )
            )

        # ── Step 2: iterate field lines and build ColumnInfo objects ──
        for field_match in _field_re.finditer(body):
            col_name = field_match.group(1)
            raw_type_full = field_match.group(2)
            raw_type = raw_type_full.replace("?", "").replace("!", "").replace("[]", "")
            modifiers = field_match.group(3).strip()

            # Skip virtual relation fields — they are not real DB columns.
            # A virtual relation field has a model-name type (starts uppercase)
            # that is NOT in the Prisma scalar type map.
            if raw_type[0].isupper() and raw_type not in _PRISMA_TYPE_MAP:
                continue

            # Skip Prisma block-level attributes that start with @@
            if col_name.startswith("@@"):
                continue

            is_nullable = "?" in raw_type_full  # True only when marked with ?
            is_primary = "@id" in modifiers
            is_unique = "@unique" in modifiers
            is_fk = col_name in fk_scalar_names

            references: Optional[Dict[str, str]] = None
            if is_fk and col_name in relation_targets:
                references = {"table": relation_targets[col_name], "column": "id"}

            col = ColumnInfo(
                name=col_name,
                col_type=_PRISMA_TYPE_MAP.get(raw_type, raw_type.lower()),
                is_nullable=is_nullable,
                is_primary=is_primary,
                is_unique=is_unique,
                is_foreign_key=is_fk,
                references=references,
            )
            table.columns.append(col)

        if table.columns:
            tables.append(table)

    return tables, relationships


# ── Public entry point ─────────────────────────────────────────────────────────


def extract_schema(repo_path: str, files: List[dict]) -> SchemaResult:
    """
    Scan all files in a repo and extract database schema information.

    Args:
        repo_path: Root path of the cloned repository (unused directly,
                   kept for future use with file system walking).
        files:     List of dicts: [{"path": str, "content": str, "language": str}]
                   — the same list produced by github_fetcher.py.

    Returns:
        SchemaResult containing all found tables and relationships.
    """
    result = SchemaResult()
    seen_tables: Dict[str, TableInfo] = {}

    for file_info in files:
        # Support both dict-style and dataclass/object-style access
        if isinstance(file_info, dict):
            path = file_info.get("path", "")
            content = file_info.get("content", "")
            language = file_info.get("language", "")
        else:
            path = getattr(file_info, "path", "")
            content = getattr(file_info, "content", "")
            language = getattr(file_info, "language", "")

        if not content:
            continue

        # ── SQLAlchemy (Python files with "Base" or "Column") ──
        if language == "python" and ("Column" in content or "mapped_column" in content):
            sa_tables = _extract_sqlalchemy(content, path)
            for t in sa_tables:
                seen_tables[t.name] = t

        # ── Django ORM (Python files with "models.Model") ──
        if language == "python" and "models.Model" in content:
            dj_tables, dj_rels = _extract_django(content, path)
            for t in dj_tables:
                seen_tables[t.name] = t
            result.relationships.extend(dj_rels)

        # ── Prisma schema files ──
        if path.endswith(".prisma"):
            pr_tables, pr_rels = _extract_prisma(content, path)
            for t in pr_tables:
                seen_tables[t.name] = t
            result.relationships.extend(pr_rels)

        # ── Mongoose (JS/TS files with Schema) ──
        if language in ("javascript", "typescript") and "mongoose" in content.lower():
            mg_tables, mg_rels = _extract_mongoose(content, path)
            for t in mg_tables:
                seen_tables[t.name] = t
            result.relationships.extend(mg_rels)

        # ── MongoEngine (Python files with Document) ──
        if language == "python" and "Document" in content:
            me_tables, me_rels = _extract_mongoengine(content, path)
            for t in me_tables:
                seen_tables[t.name] = t
            result.relationships.extend(me_rels)

    result.tables = list(seen_tables.values())

    # Build relationships from FK column references (SQLAlchemy / Django)
    for table in result.tables:
        for col in table.columns:
            if col.is_foreign_key and col.references:
                rel = RelationshipInfo(
                    from_table=table.name,
                    from_column=col.name,
                    to_table=col.references["table"],
                    to_column=col.references["column"],
                    cardinality="1:1" if col.is_unique else "1:N",
                )
                # Avoid duplicate relationships
                exists = any(
                    r.from_table == rel.from_table and r.from_column == rel.from_column
                    for r in result.relationships
                )
                if not exists:
                    result.relationships.append(rel)

    logger.info(
        "Schema extraction complete: %d tables, %d relationships",
        len(result.tables),
        len(result.relationships),
    )
    return result


def schema_result_to_db_rows(result: SchemaResult) -> List[dict]:
    """
    Convert a SchemaResult into a list of plain dicts ready to be written
    into the DbSchema table as JSON columns.

    IMPORTANT: SQLAlchemy's JSON column type can only store plain Python
    objects (dicts/lists/primitives).  If you pass ColumnInfo dataclass
    instances directly, they will raise a serialisation error at commit time.
    Always call this function before writing to the database.

    Usage in ingest_task.py:
        schema_result = extract_schema(repo_path, files)
        rows = schema_result_to_db_rows(schema_result)
        for row in rows:
            db_schema = DbSchema(
                repo_id=repo.id,
                table_name=row["table_name"],
                source_file=row["source_file"],
                columns=row["columns"],        # already plain dicts
                relationships=row["relationships"],
            )
            db.add(db_schema)
        db.commit()
    """
    from dataclasses import asdict

    # Build a lookup: table_name -> [RelationshipInfo serialised as dict, ...]
    rel_by_table: Dict[str, list] = {}
    for rel in result.relationships:
        rel_by_table.setdefault(rel.from_table, []).append(asdict(rel))

    rows = []
    for table in result.tables:
        rows.append(
            {
                "table_name": table.name,
                "source_file": table.source_file,
                "orm": table.orm,
                # Each column is a plain dict with all flag fields present
                "columns": [asdict(col) for col in table.columns],
                "relationships": rel_by_table.get(table.name, []),
            }
        )
    return rows


# ── Mongoose (Node.js MongoDB ODM) extractor ──────────────────────────────────

_MONGOOSE_TYPE_MAP: Dict[str, str] = {
    "String": "string",
    "Number": "number",
    "Boolean": "boolean",
    "Date": "date",
    "Buffer": "binary",
    "ObjectId": "objectId",
    "Mixed": "mixed",
    "Array": "array",
    "Map": "map",
}


def _mongoose_extract_body(source: str, start: int) -> str:
    """
    Extract the Mongoose schema body using brace counting from the opening {.
    Handles nested braces like: slots_booked: { type: Object, default: {} }
    """
    depth = 0
    i = start
    while i < len(source):
        if source[i] == "{":
            depth += 1
        elif source[i] == "}":
            depth -= 1
            if depth == 0:
                return source[start + 1 : i]
        i += 1
    return ""


def _extract_mongoose(
    source: str, file_path: str
) -> Tuple[List[TableInfo], List[RelationshipInfo]]:

    tables: List[TableInfo] = []
    relationships: List[RelationshipInfo] = []

    schema_header = re.compile(
        r"(?:const|let|var)\s+(\w+Schema)\s*=\s*"
        r"(?:new\s+)?(?:mongoose\.)?Schema\s*\(\s*\{",
        re.IGNORECASE | re.DOTALL,
    )

    for header_m in schema_header.finditer(source):

        raw_name = header_m.group(1)  # applicationSchema

        model_name = raw_name
        if model_name.lower().endswith("schema"):
            model_name = model_name[:-6]

        body_start = header_m.end() - 1
        body = _mongoose_extract_body(source, body_start)

        if not body:
            continue

        table = TableInfo(
            name=model_name.lower(),
            source_file=file_path,
            orm="mongoose",
        )

        table.columns.append(
            ColumnInfo(
                name="_id",
                col_type="objectId",
                is_primary=True,
                is_nullable=False,
                is_unique=True,
            )
        )

        depth = 0
        field_start = 0
        fields = []

        for i, ch in enumerate(body):

            if ch in "{[":
                depth += 1

            elif ch in "}]":
                depth -= 1

            elif ch == "," and depth == 0:
                fields.append(body[field_start:i].strip())
                field_start = i + 1

        remaining = body[field_start:].strip()
        if remaining:
            fields.append(remaining)

        for field in fields:

            if ":" not in field:
                continue

            col_name, field_val = field.split(":", 1)

            col_name = col_name.strip()
            field_val = field_val.strip()

            raw_type = "Mixed"
            is_required = False
            is_unique = False
            ref_name = None

            if field_val.startswith("{"):

                type_m = re.search(
                    r"type\s*:\s*([A-Za-z0-9_.]+)",
                    field_val,
                    re.IGNORECASE,
                )

                if type_m:
                    raw_type = type_m.group(1).strip()

                required_m = re.search(
                    r"required\s*:\s*(true|false)",
                    field_val,
                    re.IGNORECASE,
                )

                if required_m:
                    is_required = required_m.group(1).lower() == "true"

                unique_m = re.search(
                    r"unique\s*:\s*(true|false)",
                    field_val,
                    re.IGNORECASE,
                )

                if unique_m:
                    is_unique = unique_m.group(1).lower() == "true"

                ref_m = re.search(
                    r"ref\s*:\s*[\"'](\w+)[\"']",
                    field_val,
                    re.IGNORECASE,
                )

                if ref_m:
                    ref_name = ref_m.group(1)

            elif field_val.startswith("["):

                raw_type = "Array"

                type_m = re.search(
                    r"type\s*:\s*([A-Za-z0-9_.]+)",
                    field_val,
                    re.IGNORECASE,
                )

                if type_m:
                    raw_type = type_m.group(1).strip()

                ref_m = re.search(
                    r"ref\s*:\s*[\"'](\w+)[\"']",
                    field_val,
                    re.IGNORECASE,
                )

                if ref_m:
                    ref_name = ref_m.group(1)

            else:

                word_m = re.match(
                    r"([A-Za-z0-9_.]+)",
                    field_val,
                    re.IGNORECASE,
                )

                if word_m:
                    raw_type = word_m.group(1).strip()

            if (
                raw_type.endswith("ObjectId")
                or raw_type.endswith("Types.ObjectId")
                or raw_type == "Schema.Types.ObjectId"
                or raw_type == "mongoose.Schema.Types.ObjectId"
            ):
                raw_type = "ObjectId"

            if raw_type.startswith("mongoose.Schema.Types.ObjectId"):
                raw_type = "ObjectId"

            col_type = _MONGOOSE_TYPE_MAP.get(
                raw_type,
                raw_type.lower(),
            )

            col = ColumnInfo(
                name=col_name,
                col_type=col_type,
                is_primary=False,
                is_foreign_key=bool(ref_name),
                is_nullable=not is_required,
                is_unique=is_unique,
                references=(
                    {
                        "table": ref_name.lower(),
                        "column": "_id",
                    }
                    if ref_name
                    else None
                ),
            )

            table.columns.append(col)

            if ref_name:
                relationships.append(
                    RelationshipInfo(
                        from_table=model_name.lower(),
                        from_column=col_name,
                        to_table=ref_name.lower(),
                        to_column="_id",
                        cardinality="1:N",
                    )
                )

        if len(table.columns) > 1:
            tables.append(table)

    return tables, relationships


# ── MongoEngine (Python MongoDB ODM) extractor ────────────────────────────────

_MONGOENGINE_TYPE_MAP: Dict[str, str] = {
    "StringField": "string",
    "IntField": "integer",
    "FloatField": "float",
    "BooleanField": "boolean",
    "DateTimeField": "date",
    "ObjectIdField": "objectId",
    "ListField": "array",
    "DictField": "object",
    "ReferenceField": "objectId",
    "EmbeddedDocumentField": "object",
    "EmailField": "string",
    "URLField": "string",
    "UUIDField": "uuid",
    "BinaryField": "binary",
}


def _extract_mongoengine(
    source: str, file_path: str
) -> Tuple[List[TableInfo], List[RelationshipInfo]]:
    """
    Parse MongoEngine document definitions from Python files.
    Looks for: class MyDoc(Document): ...
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return [], []

    tables: List[TableInfo] = []
    relationships: List[RelationshipInfo] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue

        is_document = any(
            (isinstance(b, ast.Name) and b.id in ("Document", "EmbeddedDocument"))
            or (
                isinstance(b, ast.Attribute)
                and b.attr in ("Document", "EmbeddedDocument")
            )
            for b in node.bases
        )
        if not is_document:
            continue

        table = TableInfo(
            name=node.name.lower(), source_file=file_path, orm="mongoengine"
        )

        table.columns.append(
            ColumnInfo(
                name="_id", col_type="objectId", is_primary=True, is_nullable=False
            )
        )

        for stmt in node.body:
            if not isinstance(stmt, ast.Assign):
                continue
            for target in stmt.targets:
                if not isinstance(target, ast.Name):
                    continue
                col_name = target.id
                if not isinstance(stmt.value, ast.Call):
                    continue

                func = stmt.value.func
                field_type = (
                    func.id
                    if isinstance(func, ast.Name)
                    else func.attr if isinstance(func, ast.Attribute) else ""
                )

                if field_type not in _MONGOENGINE_TYPE_MAP:
                    continue

                col = ColumnInfo(
                    name=col_name,
                    col_type=_MONGOENGINE_TYPE_MAP[field_type],
                    is_foreign_key=field_type == "ReferenceField",
                )

                # Extract reference target
                if field_type == "ReferenceField" and stmt.value.args:
                    ref_arg = stmt.value.args[0]
                    ref_model = (
                        ref_arg.id
                        if isinstance(ref_arg, ast.Name)
                        else ref_arg.value if isinstance(ref_arg, ast.Constant) else ""
                    )
                    if ref_model:
                        col.references = {"table": ref_model.lower(), "column": "_id"}
                        relationships.append(
                            RelationshipInfo(
                                from_table=node.name.lower(),
                                from_column=col_name,
                                to_table=ref_model.lower(),
                                to_column="_id",
                                cardinality="1:N",
                            )
                        )

                table.columns.append(col)

        if len(table.columns) > 1:
            tables.append(table)

    return tables, relationships
