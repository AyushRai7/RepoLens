import re
from typing import Optional
from dataclasses import dataclass, field


@dataclass
class ParsedFile:
    path: str
    language: str
    imports: list[str] = field(default_factory=list)
    exports: list[str] = field(default_factory=list)
    functions: list[dict] = field(default_factory=list)
    classes: list[dict] = field(default_factory=list)
    lines: int = 0


def detect_language(path: str, extension: str) -> str:
    mapping = {
        ".py": "python",
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".java": "java",
        ".go": "go",
        ".rs": "rust",
        ".rb": "ruby",
        ".php": "php",
        ".cs": "csharp",
        ".cpp": "cpp",
        ".c": "c",
        ".swift": "swift",
        ".kt": "kotlin",
        ".vue": "vue",
        ".svelte": "svelte",
        ".sql": "sql",
        ".prisma": "prisma",
        ".graphql": "graphql",
        ".md": "markdown",
        ".json": "json",
        ".yaml": "yaml",
        ".yml": "yaml",
    }
    return mapping.get(extension, "unknown")


# ── Body extractors ────────────────────────────────────────────────────────────

def _extract_python_body(content: str, match_start: int, max_lines: int = 100) -> str:
    """
    Extract a complete Python function body using indentation rules.
    Starts at the 'def' keyword position, returns the full function source.
    """
    lines = content[match_start:].splitlines()
    if not lines:
        return ""

    # The first line is the 'def ...' line — determine its indentation level
    first_line = lines[0]
    base_indent = len(first_line) - len(first_line.lstrip())

    result = []
    for i, line in enumerate(lines[:max_lines]):
        if i == 0:
            result.append(line)
            continue
        # Blank lines are always included (they're part of the body)
        if not line.strip():
            result.append(line)
            continue
        cur_indent = len(line) - len(line.lstrip())
        # Once we return to the same or lesser indent, the function is done
        if cur_indent <= base_indent:
            break
        result.append(line)

    # Strip trailing blank lines
    while result and not result[-1].strip():
        result.pop()

    return "\n".join(result)


def _extract_js_body(content: str, match_start: int, max_lines: int = 100) -> str:
    """
    Extract a complete JS/TS function body by counting braces.
    Starts at the function declaration position.
    """
    lines = content[match_start:].splitlines()
    if not lines:
        return ""

    result = []
    depth = 0
    found_open = False
    in_str_single = False
    in_str_double = False
    in_str_template = False

    for line in lines[:max_lines]:
        result.append(line)
        in_line_comment = False
        j = 0
        while j < len(line):
            ch = line[j]
            nxt = line[j + 1] if j + 1 < len(line) else ""

            if in_line_comment:
                j += 1
                continue

            if not in_str_single and not in_str_double and not in_str_template:
                if ch == "/" and nxt == "/":
                    in_line_comment = True
                elif ch == "'":
                    in_str_single = True
                elif ch == '"':
                    in_str_double = True
                elif ch == '`':
                    in_str_template = True
                elif ch == '{':
                    depth += 1
                    found_open = True
                elif ch == '}':
                    depth -= 1
                    if found_open and depth == 0:
                        return "\n".join(result)
            else:
                if in_str_single and ch == "'" and (j == 0 or line[j - 1] != "\\"):
                    in_str_single = False
                elif in_str_double and ch == '"' and (j == 0 or line[j - 1] != "\\"):
                    in_str_double = False
                elif in_str_template and ch == '`':
                    in_str_template = False
            j += 1

    return "\n".join(result)


# ── Python parser ──────────────────────────────────────────────────────────────

def parse_python(content: str, path: str) -> ParsedFile:
    result = ParsedFile(path=path, language="python")
    result.lines = content.count("\n") + 1

    # Imports
    for line in content.splitlines():
        line = line.strip()
        m = re.match(r"^from\s+([\w.]+)\s+import", line)
        if m:
            result.imports.append(m.group(1))
            continue
        m = re.match(r"^import\s+([\w.,\s]+)", line)
        if m:
            for mod in m.group(1).split(","):
                result.imports.append(mod.strip().split(" ")[0])

    # Functions — capture full body
    for m in re.finditer(
        r"^(async\s+)?def\s+(\w+)\s*\(([^)]*)\)", content, re.MULTILINE
    ):
        source_code = _extract_python_body(content, m.start())
        result.functions.append(
            {
                "name": m.group(2),
                "line": content[: m.start()].count("\n") + 1,
                "signature": f"{'async ' if m.group(1) else ''}def {m.group(2)}({m.group(3)})",
                "is_async": bool(m.group(1)),
                "source_code": source_code,
            }
        )

    # Classes
    for m in re.finditer(r"^class\s+(\w+)\s*(?:\(([^)]*)\))?:", content, re.MULTILINE):
        result.classes.append(
            {
                "name": m.group(1),
                "line": content[: m.start()].count("\n") + 1,
                "bases": [
                    b.strip() for b in (m.group(2) or "").split(",") if b.strip()
                ],
            }
        )

    # Exports (module-level names)
    all_match = re.search(r"^__all__\s*=\s*\[([^\]]+)\]", content, re.MULTILINE)
    if all_match:
        result.exports = re.findall(r"['\"](\w+)['\"]", all_match.group(1))

    return result


# ── JavaScript / TypeScript parser ─────────────────────────────────────────────

def parse_javascript_typescript(content: str, path: str, language: str) -> ParsedFile:
    result = ParsedFile(path=path, language=language)
    result.lines = content.count("\n") + 1

    # Imports
    for m in re.finditer(r"""import\s+.*?\s+from\s+['"]([^'"]+)['"]""", content):
        result.imports.append(m.group(1))
    for m in re.finditer(r"""require\s*\(\s*['"]([^'"]+)['"]\s*\)""", content):
        result.imports.append(m.group(1))

    # Exports
    for m in re.finditer(
        r"export\s+(?:default\s+)?(?:function|class|const|let|var)\s+(\w+)", content
    ):
        result.exports.append(m.group(1))
    for m in re.finditer(r"export\s+\{([^}]+)\}", content):
        for name in m.group(1).split(","):
            result.exports.append(name.strip().split(" ")[0])

    # Functions — capture full body
    seen_positions: set = set()

    patterns = [
        r"(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)",
        r"(?:export\s+)?const\s+(\w+)\s*=\s*(?:async\s+)?\([^)]*\)\s*=>",
        r"(?:export\s+)?const\s+(\w+)\s*=\s*(?:async\s+)?function",
    ]
    for pattern in patterns:
        for m in re.finditer(pattern, content):
            if m.start() in seen_positions:
                continue
            seen_positions.add(m.start())
            source_code = _extract_js_body(content, m.start())
            result.functions.append(
                {
                    "name": m.group(1),
                    "line": content[: m.start()].count("\n") + 1,
                    "signature": m.group(0)[:120],
                    "source_code": source_code,
                }
            )

    # Classes
    for m in re.finditer(
        r"(?:export\s+)?class\s+(\w+)(?:\s+extends\s+(\w+))?", content
    ):
        result.classes.append(
            {
                "name": m.group(1),
                "line": content[: m.start()].count("\n") + 1,
                "bases": [m.group(2)] if m.group(2) else [],
            }
        )

    return result


# ── Main entry point ───────────────────────────────────────────────────────────

def parse_file(content: str, path: str, extension: str) -> ParsedFile:
    """Main entry point — route to correct parser by extension."""
    language = detect_language(path, extension)

    if language == "python":
        return parse_python(content, path)
    elif language in ("javascript", "typescript"):
        return parse_javascript_typescript(content, path, language)
    else:
        # Minimal fallback for unsupported languages — just count lines
        return ParsedFile(path=path, language=language, lines=content.count("\n") + 1)