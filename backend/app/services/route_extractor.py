from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


_HTTP_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}


def _route(
    method: str,
    path: str,
    handler_file: str,
    handler_function: Optional[str] = None,
    description: Optional[str] = None,
) -> dict:
    method = method.upper().strip()
    if method not in _HTTP_METHODS:
        return {}
    path = path.strip()
    if not path.startswith("/"):
        path = "/" + path
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")
    return {
        "method": method,
        "path": path,
        "handler_file": handler_file,
        "handler_function": handler_function or "",
        "description": description,
    }


def _join_paths(prefix: str, suffix: str) -> str:
    prefix = prefix.rstrip("/")
    suffix = suffix.strip()
    if not suffix or suffix == "/":
        return prefix or "/"
    if not suffix.startswith("/"):
        suffix = "/" + suffix
    return prefix + suffix


_FUNC_NAME_AFTER = re.compile(r'(?:async\s+)?def\s+(\w+)\s*\(')


_TRIPLE_DOUBLE = re.compile(r'"""(.*?)"""', re.DOTALL)
_TRIPLE_SINGLE = re.compile(r"'''(.*?)'''", re.DOTALL)
_JS_JSDOC      = re.compile(r'/\*\*(.*?)\*/', re.DOTALL)
_JS_INLINE_COMMENT = re.compile(r'//\s*(.*)')


def _extract_docstring(content: str, fn_start_pos: int, language: str) -> Optional[str]:
    """
    Find the docstring / leading comment of the function whose body starts
    at fn_start_pos.  Returns first non-empty line(s), stripped.
    """
    body_start = content.find("\n", fn_start_pos)
    if body_start == -1:
        return None
    snippet = content[body_start: body_start + 600]

    if language == "python":
        for pat in (_TRIPLE_DOUBLE, _TRIPLE_SINGLE):
            m = pat.search(snippet)
            if m:
                text = m.group(1).strip().splitlines()
                return text[0].strip() if text else None
    else:
        before = content[max(0, fn_start_pos - 400): fn_start_pos]
        jsdoc_m = list(_JS_JSDOC.finditer(before))
        if jsdoc_m:
            raw = jsdoc_m[-1].group(1)
            lines = [
                re.sub(r"^\s*\*\s?", "", l).strip()
                for l in raw.strip().splitlines()
            ]
            first = next((l for l in lines if l and not l.startswith("@")), None)
            if first:
                return first
        inline_m = list(_JS_INLINE_COMMENT.finditer(before[-200:]))
        if inline_m:
            return inline_m[-1].group(1).strip()
    return None


def _extract_handler_code(content: str, fn_start_pos: int, language: str, max_lines: int = 50) -> Optional[str]:
    """
    Extract the full source of the handler function starting at fn_start_pos.

    Python: indentation-based — stops when indent returns to function level.
    JS/TS:  brace-counting — stops when the opening { is matched by its }.
    """
    lines = content[fn_start_pos:].splitlines()
    if not lines:
        return None

    if language == "python":
        first_line = lines[0]
        base_indent = len(first_line) - len(first_line.lstrip())
        result = []
        for i, line in enumerate(lines[:max_lines]):
            if i == 0:
                result.append(line)
                continue
            if not line.strip():
                result.append(line)
                continue
            cur_indent = len(line) - len(line.lstrip())
            if cur_indent <= base_indent:
                break
            result.append(line)
        return "\n".join(result).strip() or None

    else:
        # JS/TS: count braces to find the matching closing }
        result = []
        depth = 0
        found_open = False
        in_str_single = False
        in_str_double = False
        in_str_template = False
        in_line_comment = False

        for i, line in enumerate(lines[:max_lines]):
            result.append(line)
            # Walk character by character to count braces correctly
            # (skip braces inside strings/comments)
            j = 0
            in_line_comment = False
            while j < len(line):
                ch = line[j]
                nxt = line[j + 1] if j + 1 < len(line) else ""

                if in_line_comment:
                    j += 1
                    continue
                if not in_str_single and not in_str_double and not in_str_template:
                    if ch == "/" and nxt == "/":
                        in_line_comment = True
                        j += 1
                        continue
                    if ch == "'":
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
                            return "\n".join(result).strip() or None
                else:
                    if in_str_single and ch == "'" and (j == 0 or line[j-1] != "\\"):
                        in_str_single = False
                    elif in_str_double and ch == '"' and (j == 0 or line[j-1] != "\\"):
                        in_str_double = False
                    elif in_str_template and ch == '`':
                        in_str_template = False
                j += 1

        return "\n".join(result).strip() or None


_FASTAPI_ROUTER_DEF = re.compile(
    r'(\w+)\s*=\s*(?:fastapi\.)?APIRouter\s*\([^)]*prefix\s*=\s*[\'"]([^\'"]*)[\'"]',
    re.DOTALL,
)
_FASTAPI_APP_DEF = re.compile(r'(\w+)\s*=\s*(?:fastapi\.)?FastAPI\s*\(')
_FASTAPI_DECORATOR = re.compile(
    r'@(\w+)\.(get|post|put|patch|delete|head|options)\s*\(\s*[\'"]([^\'"]*)[\'"]',
    re.IGNORECASE,
)


def _extract_fastapi(content: str, file_path: str) -> List[dict]:
    routes: List[dict] = []

    prefixes: Dict[str, str] = {}
    for m in _FASTAPI_ROUTER_DEF.finditer(content):
        prefixes[m.group(1)] = m.group(2)
    for m in _FASTAPI_APP_DEF.finditer(content):
        prefixes[m.group(1)] = ""

    for m in _FASTAPI_DECORATOR.finditer(content):
        obj_name = m.group(1)
        method   = m.group(2).upper()
        path_seg = m.group(3)
        prefix   = prefixes.get(obj_name, "")
        full_path = _join_paths(prefix, path_seg)

        fn_match = _FUNC_NAME_AFTER.search(content, m.end())
        fn_name = fn_match.group(1) if fn_match else None
        fn_pos  = fn_match.start() if fn_match else m.end()

        description  = _extract_docstring(content, fn_pos, "python") if fn_match else None
        handler_code = _extract_handler_code(content, fn_pos, "python") if fn_match else None

        r = _route(method, full_path, file_path, fn_name, description)
        if r:
            r["handler_code"] = handler_code
            routes.append(r)

    return routes


# -- Flask --------------------------------------------------------------------

_FLASK_BLUEPRINT_DEF = re.compile(
    r'(\w+)\s*=\s*Blueprint\s*\([^)]*url_prefix\s*=\s*[\'"]([^\'"]*)[\'"]',
    re.DOTALL,
)
_FLASK_ROUTE_DECORATOR = re.compile(
    r'@(\w+)\.route\s*\(\s*[\'"]([^\'"]+)[\'"]([^)]*)\)',
    re.DOTALL,
)
_FLASK_METHODS_ARG = re.compile(r'methods\s*=\s*\[([^\]]+)\]', re.DOTALL)


def _extract_flask(content: str, file_path: str) -> List[dict]:
    routes: List[dict] = []

    prefixes: Dict[str, str] = {}
    for m in _FLASK_BLUEPRINT_DEF.finditer(content):
        prefixes[m.group(1)] = m.group(2)

    for m in _FLASK_ROUTE_DECORATOR.finditer(content):
        obj_name = m.group(1)
        path_seg = m.group(2)
        extra    = m.group(3)
        prefix   = prefixes.get(obj_name, "")
        full_path = _join_paths(prefix, path_seg)

        methods_match = _FLASK_METHODS_ARG.search(extra)
        if methods_match:
            raw_methods = re.findall(r"['\"](\w+)['\"]", methods_match.group(1))
            methods = [x.upper() for x in raw_methods if x.upper() in _HTTP_METHODS]
        else:
            methods = ["GET"]

        fn_match = _FUNC_NAME_AFTER.search(content, m.end())
        fn_name = fn_match.group(1) if fn_match else None
        fn_pos  = fn_match.start() if fn_match else m.end()

        description  = _extract_docstring(content, fn_pos, "python") if fn_match else None
        handler_code = _extract_handler_code(content, fn_pos, "python") if fn_match else None

        for method in methods:
            r = _route(method, full_path, file_path, fn_name, description)
            if r:
                r["handler_code"] = handler_code
                routes.append(r)

    return routes


# -- Django -------------------------------------------------------------------

_DJANGO_PATH = re.compile(
    r'(?:^|\s)path\s*\(\s*[\'"]([^\'"]*)[\'"]',
    re.MULTILINE,
)
_DJANGO_RE_PATH = re.compile(
    r're_path\s*\(\s*r[\'"]([^\'"]+)[\'"]',
)
_DRF_ROUTER_REGISTER = re.compile(
    r'router\.register\s*\(\s*r?[\'"]([^\'"]+)[\'"](?:\s*,\s*(\w+))?',
    re.DOTALL,
)
_DRF_ACTION = re.compile(
    r'@action\s*\(\s*([^)]+)\)',
    re.DOTALL,
)
_DRF_ACTION_METHODS = re.compile(r'methods\s*=\s*\[([^\]]+)\]', re.DOTALL)
_DRF_ACTION_DETAIL  = re.compile(r'detail\s*=\s*(True|False)')
_DRF_ACTION_URL     = re.compile(r'url_path\s*=\s*[\'"]([^\'"]+)[\'"]')

_DRF_CRUD_ROUTES = [
    ("GET",    "/{prefix}"),
    ("POST",   "/{prefix}"),
    ("GET",    "/{prefix}/{id}"),
    ("PUT",    "/{prefix}/{id}"),
    ("PATCH",  "/{prefix}/{id}"),
    ("DELETE", "/{prefix}/{id}"),
]


def _clean_django_path(path: str) -> str:
    path = re.sub(r"^\^", "", path)
    path = re.sub(r"\$$", "", path)
    path = re.sub(r"\(\?P<(\w+)>[^)]+\)", r"{\1}", path)
    path = re.sub(r"<(?:\w+:)?(\w+)>", r"{\1}", path)
    if not path.startswith("/"):
        path = "/" + path
    return path.rstrip("/") or "/"


def _extract_django(content: str, file_path: str) -> List[dict]:
    routes: List[dict] = []

    for m in _DJANGO_PATH.finditer(content):
        raw_path = m.group(1)
        if not raw_path or raw_path in ("", "admin/"):
            continue
        clean = _clean_django_path(raw_path)
        has_id = bool(re.search(r"\{(pk|id|slug)\}", clean))
        methods = ["GET", "PUT", "PATCH", "DELETE"] if has_id else ["GET", "POST"]
        for method in methods:
            r = _route(method, clean, file_path)
            if r:
                routes.append(r)

    for m in _DJANGO_RE_PATH.finditer(content):
        clean = _clean_django_path(m.group(1))
        has_id = bool(re.search(r"\{(pk|id|slug)\}", clean))
        methods = ["GET", "PUT", "PATCH", "DELETE"] if has_id else ["GET", "POST"]
        for method in methods:
            r = _route(method, clean, file_path)
            if r:
                routes.append(r)

    for m in _DRF_ROUTER_REGISTER.finditer(content):
        prefix = m.group(1).strip("/")
        for method, path_tmpl in _DRF_CRUD_ROUTES:
            path = path_tmpl.replace("{prefix}", prefix)
            routes.append(_route(method, path, file_path, m.group(2)))

    for m in _DRF_ACTION.finditer(content):
        body = m.group(1)
        methods_m = _DRF_ACTION_METHODS.search(body)
        detail_m  = _DRF_ACTION_DETAIL.search(body)
        url_m     = _DRF_ACTION_URL.search(body)
        if not methods_m:
            continue
        raw_methods = re.findall(r"['\"](\w+)['\"]", methods_m.group(1))
        is_detail = detail_m and detail_m.group(1) == "True"
        fn_match = _FUNC_NAME_AFTER.search(content, m.end())
        fn_name = fn_match.group(1) if fn_match else "action"
        action_path = url_m.group(1) if url_m else fn_name
        path = ("/{id}/" if is_detail else "/") + action_path
        for method in raw_methods:
            r = _route(method.upper(), path, file_path, fn_name)
            if r:
                routes.append(r)

    return routes



_EXPRESS_ROUTE = re.compile(
    r'(\w+)\s*\.\s*(get|post|put|patch|delete|head|options)\s*'
    r'\(\s*[\'"`]([^\'"`]+)[\'"`]',
    re.IGNORECASE,
)
_EXPRESS_USE = re.compile(
    r'(?:app|server)\.use\s*\(\s*[\'"`]([^\'"`]+)[\'"`]\s*,\s*(\w+)',
    re.IGNORECASE,
)
_EXPRESS_ROUTER_DEF = re.compile(
    r'(?:const|let|var)\s+(\w+)\s*=\s*(?:express\.Router|Router)\s*\(',
    re.IGNORECASE,
)


def _extract_express(
    content: str,
    file_path: str,
    global_prefixes: Optional[Dict[str, str]] = None,
) -> List[dict]:
    routes: List[dict] = []

    # Per-file prefix mounts (e.g. app.use within the same file)
    use_prefixes: Dict[str, str] = {}
    for m in _EXPRESS_USE.finditer(content):
        use_prefixes[m.group(2)] = m.group(1)

    # Merge cross-file prefixes (from server.js/app.js) — lower priority than local
    if global_prefixes:
        for var, prefix in global_prefixes.items():
            if var not in use_prefixes:
                use_prefixes[var] = prefix

    # All variable names that are Express routers in this file
    router_vars: set = {"router", "app", "server"}
    for m in _EXPRESS_ROUTER_DEF.finditer(content):
        router_vars.add(m.group(1))

    # Also treat any variable that appears in use_prefixes as a router var
    router_vars.update(use_prefixes.keys())

    for m in _EXPRESS_ROUTE.finditer(content):
        obj_name = m.group(1)
        method   = m.group(2).upper()
        path_seg = m.group(3)

        # Skip objects that clearly aren't routers
        if (obj_name not in router_vars
                and obj_name.lower() not in ("router", "app", "server")):
            continue

        prefix = use_prefixes.get(obj_name, "")
        full_path = _join_paths(prefix, path_seg)

        after = content[m.end():]
        fn_match = re.search(r',\s*(?:async\s+)?(?:function\s+)?(\w+)\s*[,)\n]', after[:200])
        fn_name = None
        if fn_match and fn_match.group(1) not in ("req", "res", "next", "err"):
            fn_name = fn_match.group(1)

        # Try to grab inline handler (arrow / function expression on this same line)
        inline_fn = re.search(
            r',\s*((?:async\s+)?\([^)]*\)\s*=>\s*\{.*?\}|(?:async\s+)?function\s*\([^)]*\)\s*\{.*?\})',
            after[:800], re.DOTALL
        )
        description  = _extract_docstring(content, m.start(), "javascript")
        handler_code = inline_fn.group(1).strip() if inline_fn else None

        r = _route(method, full_path, file_path, fn_name, description)
        if r:
            r["handler_code"] = handler_code
            routes.append(r)

    return routes


# -- Next.js ------------------------------------------------------------------

_NEXTJS_EXPORT_HANDLER = re.compile(
    r'export\s+(?:async\s+)?function\s+(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s*\(',
    re.IGNORECASE,
)
_NEXTJS_PAGES_METHOD = re.compile(
    r"req\.method\s*===?\s*['\"](\w+)['\"]",
    re.IGNORECASE,
)


def _nextjs_path_from_file(file_path: str) -> str:
    p = file_path.replace("\\", "/")
    # App Router: app/api/**/route.{ts,js,tsx,jsx}
    app_m = re.search(r"app/(api/.+)/route\.[jt]sx?$", p)
    if app_m:
        seg = re.sub(r"\[(\w+)\]", r"{\1}", app_m.group(1))
        return "/" + seg
    # Pages API
    pages_m = re.search(r"pages/(api/.+)\.[jt]sx?$", p)
    if pages_m:
        seg = re.sub(r"\[(\w+)\]", r"{\1}", pages_m.group(1))
        seg = re.sub(r"/index$", "", seg)
        return "/" + seg
    return "/"


def _extract_nextjs(content: str, file_path: str) -> List[dict]:
    routes: List[dict] = []
    path = _nextjs_path_from_file(file_path)

    is_app_router = bool(re.search(r"route\.[jt]sx?$", file_path))
    is_pages_api  = "/api/" in file_path and not is_app_router

    if is_app_router:
        for m in _NEXTJS_EXPORT_HANDLER.finditer(content):
            fn_pos = m.start()
            description  = _extract_docstring(content, fn_pos, "javascript")
            handler_code = _extract_handler_code(content, fn_pos, "javascript")
            r = _route(m.group(1).upper(), path, file_path, m.group(1).upper(), description)
            if r:
                r["handler_code"] = handler_code
                routes.append(r)

    elif is_pages_api:
        methods_found: set = set()
        for m in _NEXTJS_PAGES_METHOD.finditer(content):
            method = m.group(1).upper()
            if method in _HTTP_METHODS and method not in methods_found:
                methods_found.add(method)
                r = _route(method, path, file_path, "handler")
                if r:
                    r["handler_code"] = None
                    routes.append(r)
        if not methods_found and path != "/":
            for method in ["GET", "POST"]:
                r = _route(method, path, file_path, "handler")
                if r:
                    r["handler_code"] = None
                    routes.append(r)

    return routes


# -- Fastify ------------------------------------------------------------------

_FASTIFY_ROUTE = re.compile(
    r'(?:fastify|server|app)\s*\.\s*(get|post|put|patch|delete|head|options)\s*'
    r'\(\s*[\'"`]([^\'"`]+)[\'"`]',
    re.IGNORECASE,
)


def _extract_fastify(content: str, file_path: str) -> List[dict]:
    routes: List[dict] = []
    for m in _FASTIFY_ROUTE.finditer(content):
        r = _route(m.group(1).upper(), m.group(2), file_path)
        if r:
            routes.append(r)
    return routes


# -- Hapi ---------------------------------------------------------------------

_HAPI_ROUTE = re.compile(
    r'server\.route\s*\(\s*\{[^}]*method\s*:\s*[\'"](\w+)[\'"][^}]*path\s*:\s*[\'"]([^\'"]+)[\'"]',
    re.DOTALL,
)
_HAPI_ROUTE_MULTI = re.compile(
    r'server\.route\s*\(\s*\{[^}]*method\s*:\s*\[([^\]]+)\][^}]*path\s*:\s*[\'"]([^\'"]+)[\'"]',
    re.DOTALL,
)


def _extract_hapi(content: str, file_path: str) -> List[dict]:
    routes: List[dict] = []
    for m in _HAPI_ROUTE.finditer(content):
        r = _route(m.group(1).upper(), m.group(2), file_path)
        if r:
            routes.append(r)
    for m in _HAPI_ROUTE_MULTI.finditer(content):
        for method in re.findall(r"['\"](\w+)['\"]", m.group(1)):
            r = _route(method.upper(), m.group(2), file_path)
            if r:
                routes.append(r)
    return routes


# ==============================================================================
# Framework detection + pre-filter
# ==============================================================================

def _detect_frameworks(content: str, file_path: str, language: str) -> List[str]:
    detected = []
    p = file_path.lower()

    if language == "python":
        if "APIRouter" in content or "FastAPI" in content:
            detected.append("fastapi")
        if ".route(" in content and ("Blueprint" in content or "Flask" in content):
            detected.append("flask")
        if "urlpatterns" in content or "path(" in content or "re_path(" in content:
            detected.append("django")

    elif language in ("javascript", "typescript"):
        if ("express" in content.lower() or "Router()" in content
                or "express.Router" in content):
            detected.append("express")
        if (re.search(r"route\.[jt]sx?$", p) and "/api/" in p) or \
           ("pages/api" in p) or \
           ("NextResponse" in content or "NextApiRequest" in content) or \
           bool(_NEXTJS_EXPORT_HANDLER.search(content)):
            detected.append("nextjs")
        if "fastify" in content.lower() and re.search(
                r'fastify\.(get|post|put|delete|patch)\s*\(', content, re.IGNORECASE):
            detected.append("fastify")
        if "server.route(" in content:
            detected.append("hapi")

    return detected


def _is_route_file(path: str, content: str, language: str) -> bool:
    p = path.lower()

    skip_dirs = {
        "node_modules", ".next", "dist", "build", "__pycache__",
        "vendor", "migrations", "test", "tests", "__tests__", "spec",
        "coverage", ".git",
    }
    if any(d in skip_dirs for d in p.split("/")):
        return False

    skip_exts = {
        ".md", ".json", ".yaml", ".yml", ".css", ".scss",
        ".html", ".svg", ".png", ".jpg", ".lock", ".prisma",
        ".sql", ".txt", ".env",
    }
    if any(p.endswith(ext) for ext in skip_exts):
        return False

    if language == "python":
        return any(kw in content for kw in (
            "@app.", "@router.", "@bp.", "urlpatterns", "APIRouter",
            "FastAPI", "Blueprint", "path(", "re_path(",
        ))

    if language in ("javascript", "typescript"):
        # Standard router/app method calls
        if any(kw in content for kw in (
            "router.get(", "router.post(", "router.put(", "router.delete(",
            "router.patch(", "app.get(", "app.post(", "app.put(", "app.delete(",
            "app.patch(", "server.route(", "fastify.",
            "NextResponse", "NextApiRequest",
            "export async function GET", "export async function POST",
            "export function GET", "export function POST",
            "req.method",
        )):
            return True
        # Custom-named Express routers: adminRouter.post(, doctorRouter.get( etc.
        # Detect by presence of .Router() definition + at least one .get/post/put call
        if ".Router()" in content or "express.Router()" in content:
            if re.search(r'(\w+)\.(get|post|put|patch|delete)\s*\(', content, re.IGNORECASE):
                return True
        # app.use() prefix mounts in entry files (server.js, index.js, app.js)
        if "app.use(" in content:
            return True
        return False

    return False


# ==============================================================================
# Frontend caller detection
# ==============================================================================

# Patterns for fetch / axios / custom api client calls in JS/TS
_FETCH_PATTERN = re.compile(
    r'fetch\s*\(\s*[`\'"]([^`\'"]+)[`\'"]',
    re.IGNORECASE,
)
_AXIOS_PATTERN = re.compile(
    r'axios\s*\.\s*(?:get|post|put|patch|delete)\s*\(\s*[`\'"]([^`\'"]+)[`\'"]',
    re.IGNORECASE,
)
_API_CLIENT_PATTERN = re.compile(
    r'(?:api|client|http|request|axios)\s*\.\s*(?:get|post|put|patch|delete|request)\s*\(\s*[`\'"]([^`\'"]+)[`\'"]',
    re.IGNORECASE,
)
_TEMPLATE_LITERAL = re.compile(
    r'[`\'"]([/\w\-\${}]+(?:/[/\w\-\${}]+)*)[`\'"]',
)

_FRONTEND_EXTENSIONS = {".ts", ".tsx", ".js", ".jsx", ".vue", ".svelte"}

_BACKEND_ROUTE_FILE_PATTERNS = [
    re.compile(r'/route\.[jt]sx?$'),               # Next.js App Router handler
    re.compile(r'pages/api/.*\.[jt]sx?$'),          # Next.js Pages API
]


def _is_backend_route_file(path: str) -> bool:
    """Return True if this file IS a route handler (not a caller)."""
    return any(p.search(path) for p in _BACKEND_ROUTE_FILE_PATTERNS)


def _path_matches_route(url_fragment: str, route_path: str) -> bool:
    """
    Check whether a URL fragment found in frontend code matches a backend route path.
    Handles:
      - Exact match after stripping params: /api/auth/refresh-session
      - Partial path strings that are substrings of the route
      - Template-literal fragments like /auth/refresh-session (missing /api prefix)
    """
    url_fragment = url_fragment.strip("/").lower()
    # Remove path params from route: /users/{id} → /users/
    route_static = re.sub(r"\{[^}]+\}", "", route_path).strip("/").lower()
    route_static = re.sub(r"//+", "/", route_static)

    if not url_fragment or not route_static:
        return False

    # Too-short fragments cause false positives (e.g. "id", "get")
    if len(url_fragment) < 4:
        return False

    # Direct contains: one is substring of the other
    if url_fragment in route_static or route_static in url_fragment:
        return True

    # Segment-level: all static route segments appear consecutively in URL
    route_segs = [s for s in route_static.split("/") if s]
    url_segs   = [s for s in url_fragment.split("/") if s]
    if len(route_segs) < 2:
        return False
    for i in range(len(url_segs) - len(route_segs) + 1):
        if url_segs[i: i + len(route_segs)] == route_segs:
            return True

    return False


def _extract_url_fragments(line: str) -> List[str]:
    """
    Pull every plausible URL path fragment out of a source line.
    Handles:
      - fetch('/api/foo')
      - axios.get(`/api/foo/${id}`)   → extracts "/api/foo/"
      - api.post('/auth/login')
      - const URL = '/api/users'
      - url: '/api/orders'
      - endpoint = `/api/items/${id}`
    """
    fragments: List[str] = []

    # 1. fetch( "..." ) or fetch( `...` ) — grab up to first ${ or end of string
    for m in re.finditer(r'fetch\s*\(\s*[`\'"]([^`\'"$\n]+)', line, re.IGNORECASE):
        fragments.append(m.group(1))

    # 2. axios.METHOD( "..." )
    for m in re.finditer(
        r'axios\s*\.\s*\w+\s*\(\s*[`\'"]([^`\'"$\n]+)', line, re.IGNORECASE
    ):
        fragments.append(m.group(1))

    # 3. Generic api/client/http/request client method call
    for m in re.finditer(
        r'(?:api|client|http|request|service)\s*\.\s*\w+\s*\(\s*[`\'"]([^`\'"$\n]+)',
        line, re.IGNORECASE
    ):
        fragments.append(m.group(1))

    # 4. Any string/template-literal that looks like a URL path (/something/...)
    #    Captures static prefix of template literals up to the first ${
    for m in re.finditer(r'[`\'"](\s*/[a-zA-Z0-9_\-/]+)', line):
        val = m.group(1).strip()
        if len(val) > 3 and "/" in val:
            fragments.append(val)

    # 5. url/endpoint/path assignment:  url = '/api/foo'
    for m in re.finditer(
        r'(?:url|endpoint|path|route|href)\s*[=:]\s*[`\'"]([^`\'"$\n]+)',
        line, re.IGNORECASE
    ):
        fragments.append(m.group(1))

    return fragments


def _find_frontend_callers(files: List, routes: List[dict]) -> Dict[str, List[dict]]:
    """
    Scan all frontend/client files for fetch/axios/api calls and map them
    to backend routes.

    Returns a dict keyed by "METHOD:path" → list of caller dicts:
        [{"file": str, "line": int, "snippet": str}]
    """
    # Build index: route_key → route  (method-agnostic secondary index too,
    # because frontend callers often don't encode the HTTP method explicitly)
    route_index: Dict[str, dict] = {}
    path_index:  Dict[str, List[str]] = {}   # route_path → [key, ...]
    for r in routes:
        key = f"{r['method']}:{r['path']}"
        route_index[key] = r
        path_index.setdefault(r["path"], []).append(key)

    callers: Dict[str, List[dict]] = {k: [] for k in route_index}

    for file_info in files:
        if isinstance(file_info, dict):
            path    = file_info.get("path", "")
            content = file_info.get("content", "")
        else:
            path    = getattr(file_info, "path", "")
            content = getattr(file_info, "content", "")

        if not content or not path:
            continue

        # Only scan JS/TS/Vue/Svelte files
        ext = ("." + path.rsplit(".", 1)[-1]) if "." in path else ""
        if ext not in _FRONTEND_EXTENSIONS:
            continue

        # Skip the actual backend route handler files — they're not callers
        if _is_backend_route_file(path):
            continue

        lines = content.splitlines()

        for line_no, line in enumerate(lines, start=1):
            fragments = _extract_url_fragments(line)

            for url_fragment in fragments:
                for key, route in route_index.items():
                    if _path_matches_route(url_fragment, route["path"]):
                        snippet = line.strip()[:120]
                        existing = callers[key]
                        if not any(
                            c["file"] == path and c["line"] == line_no
                            for c in existing
                        ):
                            existing.append({
                                "file": path,
                                "line": line_no,
                                "snippet": snippet,
                            })

    return callers


# ==============================================================================
# Public entry point
# ==============================================================================

def _build_global_prefix_map(files: List) -> Dict[str, str]:
    """
    Build a cross-file map of router-variable -> prefix by scanning entry
    files (server.js, app.js, index.js) for app.use('/prefix', routerVar).

    This is needed because Express projects define prefixes in a central
    entry file but declare individual routes in separate route files.
    Without this cross-file resolution, routes get no prefix applied.

    Example:
        server.js:     app.use('/api/admin', adminRouter)
        adminRoute.js: adminRouter.post('/login', loginAdmin)
        Result:        POST /api/admin/login
    """
    global_prefixes: Dict[str, str] = {}
    entry_names = {"server.js", "app.js", "index.js", "main.js",
                   "server.ts", "app.ts", "index.ts", "main.ts"}

    for file_info in files:
        if isinstance(file_info, dict):
            path    = file_info.get("path", "")
            content = file_info.get("content", "")
        else:
            path    = getattr(file_info, "path", "")
            content = getattr(file_info, "content", "")

        if not content:
            continue

        # Only scan entry-point files
        filename = path.split("/")[-1].lower()
        if filename not in entry_names:
            continue

        # app.use('/api/admin', adminRouter)
        for m in _EXPRESS_USE.finditer(content):
            prefix   = m.group(1)
            var_name = m.group(2)
            global_prefixes[var_name] = prefix

    return global_prefixes


def extract_routes(files: List) -> List[dict]:
    """
    Scan all repo files and extract API route definitions.

    Args:
        files:  List of file records — accepts either:
                  - dicts: {"path", "content", "language"}
                  - FileInfo dataclass objects from github_fetcher.py
                    (these only have path/extension, no content — they are
                     skipped automatically since content will be empty)
                  - Any object with .path / .content / .language attributes
                    or dict-style .get() access

    Returns:
        List of route dicts, each containing:
            method, path, handler_file, handler_function, description,
            handler_code, frontend_callers
        Deduplicated by (method, path) — first occurrence wins.
    """
    all_routes: List[dict] = []
    seen: set = set()

    # Build cross-file prefix map from entry files before processing routes
    global_prefixes = _build_global_prefix_map(files)

    for file_info in files:
        # Support both dict-style and dataclass/object-style access
        if isinstance(file_info, dict):
            path     = file_info.get("path", "")
            content  = file_info.get("content", "")
            language = file_info.get("language", "")
        else:
            path     = getattr(file_info, "path", "")
            content  = getattr(file_info, "content", "")
            language = getattr(file_info, "language", "")
            # FileInfo from github_fetcher has no content/language yet —
            # those are added after fetching. Skip bare FileInfo objects.
            if not content:
                continue

        if not content or not path:
            continue

        if not _is_route_file(path, content, language):
            continue

        frameworks = _detect_frameworks(content, path, language)
        if not frameworks:
            continue

        file_routes: List[dict] = []
        for fw in frameworks:
            if fw == "fastapi":
                file_routes.extend(_extract_fastapi(content, path))
            elif fw == "flask":
                file_routes.extend(_extract_flask(content, path))
            elif fw == "django":
                file_routes.extend(_extract_django(content, path))
            elif fw == "express":
                file_routes.extend(_extract_express(content, path, global_prefixes))
            elif fw == "nextjs":
                file_routes.extend(_extract_nextjs(content, path))
            elif fw == "fastify":
                file_routes.extend(_extract_fastify(content, path))
            elif fw == "hapi":
                file_routes.extend(_extract_hapi(content, path))

        for r in file_routes:
            if not r:
                continue
            # Ensure handler_code key exists (extractors that don't set it)
            r.setdefault("handler_code", None)
            key = (r["method"], r["path"])
            if key not in seen:
                seen.add(key)
                all_routes.append(r)

    # ── Frontend caller detection ─────────────────────────────────────────────
    callers_map = _find_frontend_callers(files, all_routes)
    for r in all_routes:
        key = f"{r['method']}:{r['path']}"
        r["frontend_callers"] = callers_map.get(key, [])

    logger.info("Route extraction complete: %d routes found", len(all_routes))
    return all_routes