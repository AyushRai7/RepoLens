from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)


_HTTP_TIMEOUT = 10.0  # seconds per request


@dataclass
class CVEInfo:
    cve_id: str
    severity: str         
    summary: str
    cvss_score: float
    url: str
    fixed_in: Optional[str] = None


@dataclass
class DependencyInfo:
    name: str
    current_version: str
    latest_version: str
    update_status: str    
    license: Optional[str]
    license_ok: bool
    is_dev: bool
    is_transitive: bool
    cves: List[CVEInfo] = field(default_factory=list)
    description: Optional[str] = None
    homepage: Optional[str] = None
    ecosystem: str = "unknown"


# ── Version comparison ─────────────────────────────────────────────────────────

def _parse_semver(version: str) -> Tuple[int, int, int]:
    """Parse a semver string into (major, minor, patch) integers."""
    version = re.sub(r"[^\d.]", "", version)   
    parts = version.split(".")
    try:
        major = int(parts[0]) if len(parts) > 0 else 0
        minor = int(parts[1]) if len(parts) > 1 else 0
        patch = int(parts[2]) if len(parts) > 2 else 0
        return major, minor, patch
    except (ValueError, IndexError):
        return 0, 0, 0


def _update_status(current: str, latest: str) -> str:
    """
    Compare current vs latest version and return the update status.
    """
    if not current or not latest:
        return "unknown"
    cur = _parse_semver(current)
    lat = _parse_semver(latest)
    if cur == lat:
        return "up-to-date"
    if lat[0] > cur[0]:
        return "major"
    if lat[1] > cur[1]:
        return "minor"
    if lat[2] > cur[2]:
        return "patch"
    return "up-to-date"


# ── OSV vulnerability lookup ───────────────────────────────────────────────────

_OSV_API = "https://api.osv.dev/v1/query"

_SEVERITY_MAP: Dict[str, str] = {
    "CRITICAL": "critical",
    "HIGH": "high",
    "MODERATE": "medium",
    "MEDIUM": "medium",
    "LOW": "low",
}


def _cvss_to_severity(score: float) -> str:
    if score >= 9.0:
        return "critical"
    if score >= 7.0:
        return "high"
    if score >= 4.0:
        return "medium"
    return "low"


def _query_osv(package_name: str, version: str, ecosystem: str) -> List[CVEInfo]:
    """
    Query the OSV API for known vulnerabilities for a package+version.

    OSV is a free, open database of vulnerabilities maintained by Google.
    It covers PyPI, npm, crates.io, Go, Maven, and more.

    Docs: https://osv.dev/docs/
    """
    # Map our ecosystem names to OSV ecosystem names
    osv_ecosystem_map = {
        "pip": "PyPI",
        "npm": "npm",
        "cargo": "crates.io",
        "go": "Go",
        "maven": "Maven",
        "gem": "RubyGems",
    }
    osv_ecosystem = osv_ecosystem_map.get(ecosystem, ecosystem)

    payload = {
        "version": version,
        "package": {
            "name": package_name,
            "ecosystem": osv_ecosystem,
        },
    }

    try:
        with httpx.Client(timeout=_HTTP_TIMEOUT) as client:
            resp = client.post(_OSV_API, json=payload)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning("OSV query failed for %s@%s: %s", package_name, version, exc)
        return []

    cves: List[CVEInfo] = []
    for vuln in data.get("vulns", []):
        # Get severity
        severity = "medium"
        cvss_score = 0.0

        for sev in vuln.get("severity", []):
            if sev.get("type") == "CVSS_V3":
                # Parse CVSS score from vector string like "CVSS:3.1/AV:N/AC:L/..."
                score_match = re.search(r"(\d+\.\d+)$", sev.get("score", ""))
                if score_match:
                    cvss_score = float(score_match.group(1))
                    severity = _cvss_to_severity(cvss_score)
                break

        # Try database_specific for severity label
        for db_specific in vuln.get("database_specific", {}).values():
            if isinstance(db_specific, str) and db_specific.upper() in _SEVERITY_MAP:
                severity = _SEVERITY_MAP[db_specific.upper()]
                break

        # Get fix version
        fixed_in: Optional[str] = None
        for affected in vuln.get("affected", []):
            for rng in affected.get("ranges", []):
                for event in rng.get("events", []):
                    if "fixed" in event:
                        fixed_in = event["fixed"]
                        break

        # Get CVE id (OSV may have aliases like CVE-XXXX-YYYY)
        cve_id = vuln.get("id", "")
        for alias in vuln.get("aliases", []):
            if alias.startswith("CVE-"):
                cve_id = alias
                break

        cves.append(CVEInfo(
            cve_id=cve_id,
            severity=severity,
            summary=vuln.get("summary", vuln.get("details", "")[:200]),
            cvss_score=cvss_score,
            url=f"https://osv.dev/vulnerability/{vuln.get('id', '')}",
            fixed_in=fixed_in,
        ))

    return cves


# ── PyPI metadata ──────────────────────────────────────────────────────────────

def _pypi_metadata(package_name: str) -> Dict:
    """Fetch package metadata from PyPI JSON API."""
    try:
        with httpx.Client(timeout=_HTTP_TIMEOUT) as client:
            resp = client.get(f"https://pypi.org/pypi/{package_name}/json")
            if resp.status_code == 200:
                return resp.json().get("info", {})
    except Exception as exc:
        logger.debug("PyPI metadata fetch failed for %s: %s", package_name, exc)
    return {}


# ── npm metadata ───────────────────────────────────────────────────────────────

def _npm_metadata(package_name: str) -> Dict:
    """Fetch package metadata from the npm registry."""
    try:
        with httpx.Client(timeout=_HTTP_TIMEOUT) as client:
            # Use abbreviated manifest (faster)
            resp = client.get(
                f"https://registry.npmjs.org/{package_name}/latest",
                headers={"Accept": "application/vnd.npm.install-v1+json"},
            )
            if resp.status_code == 200:
                return resp.json()
    except Exception as exc:
        logger.debug("npm metadata fetch failed for %s: %s", package_name, exc)
    return {}


# ── Permissive license check ───────────────────────────────────────────────────

_COPYLEFT_LICENSES = {
    "GPL", "GPL-2.0", "GPL-3.0", "LGPL", "LGPL-2.0", "LGPL-2.1", "LGPL-3.0",
    "AGPL", "AGPL-3.0", "EUPL", "OSL", "CDDL", "MPL-1.1",
}

def _license_ok(license_name: Optional[str]) -> bool:
    """
    Returns True if the license is permissive (safe for commercial use),
    False if it's a copyleft license that may require source disclosure.
    Unknown licenses return False (flag for review).
    """
    if not license_name:
        return False
    upper = license_name.upper()
    return not any(cl.upper() in upper for cl in _COPYLEFT_LICENSES)


# ── Parsers for each ecosystem ─────────────────────────────────────────────────

def _parse_requirements_txt(content: str) -> List[Tuple[str, str, bool]]:
    """
    Parse requirements.txt / requirements-dev.txt.
    Returns list of (name, version, is_dev).
    """
    deps = []
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        # Handle: package==1.2.3, package>=1.0, package~=1.0
        match = re.match(r"^([A-Za-z0-9_\-\.]+)\s*[=<>~!]+\s*([^\s;,#]+)", line)
        if match:
            name = match.group(1)
            version = match.group(2).strip()
            deps.append((name, version, False))
        else:
            # Package with no version pin
            name = re.match(r"^([A-Za-z0-9_\-\.]+)", line)
            if name:
                deps.append((name.group(1), "", False))
    return deps


def _parse_package_json(content: str) -> List[Tuple[str, str, bool]]:
    """
    Parse package.json dependencies and devDependencies.
    Returns list of (name, version, is_dev).
    """
    deps = []
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return deps
    for name, version in data.get("dependencies", {}).items():
        deps.append((name, version.lstrip("^~>=<"), False))
    for name, version in data.get("devDependencies", {}).items():
        deps.append((name, version.lstrip("^~>=<"), True))
    return deps


def _parse_cargo_toml(content: str) -> List[Tuple[str, str, bool]]:
    """
    Parse Cargo.toml [dependencies] and [dev-dependencies].
    Returns list of (name, version, is_dev).
    """
    deps = []
    in_deps = False
    in_dev_deps = False

    for line in content.splitlines():
        stripped = line.strip()
        if stripped == "[dependencies]":
            in_deps, in_dev_deps = True, False
            continue
        if stripped == "[dev-dependencies]":
            in_deps, in_dev_deps = False, True
            continue
        if stripped.startswith("[") and stripped.endswith("]"):
            in_deps, in_dev_deps = False, False
            continue

        if in_deps or in_dev_deps:
            # name = "1.2.3" or name = { version = "1.2.3" }
            match = re.match(r'^(\w[\w\-]*)\s*=\s*"([^"]+)"', stripped)
            if match:
                deps.append((match.group(1), match.group(2), in_dev_deps))
            else:
                match = re.match(r'^(\w[\w\-]*)\s*=\s*\{.*version\s*=\s*"([^"]+)"', stripped)
                if match:
                    deps.append((match.group(1), match.group(2), in_dev_deps))
    return deps


def _parse_go_mod(content: str) -> List[Tuple[str, str, bool]]:
    """
    Parse go.mod require block.
    Returns list of (name, version, is_dev).
    """
    deps = []
    in_require = False

    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("require ("):
            in_require = True
            continue
        if in_require and stripped == ")":
            in_require = False
            continue
        if in_require or stripped.startswith("require "):
            # module/path v1.2.3
            match = re.match(r"([\w./\-]+)\s+v([\d.]+[\w\-\.]*)", stripped)
            if match:
                deps.append((match.group(1), match.group(2), False))
    return deps


# ── Main analyzer ──────────────────────────────────────────────────────────────

def analyze_dependencies(files: List[dict]) -> List[DependencyInfo]:
    """
    Scan repo files for dependency manifests, parse all packages,
    fetch metadata, and check for vulnerabilities.

    Args:
        files: List of {"path": str, "content": str} dicts from github_fetcher.

    Returns:
        List of DependencyInfo, one per unique package found.
    """
    all_raw: List[Tuple[str, str, bool, str]] = []  # (name, version, is_dev, ecosystem)

    for file_info in files:
        path = Path(file_info.get("path", ""))
        content = file_info.get("content", "")
        if not content:
            continue

        name = path.name.lower()

        if name == "requirements.txt" or re.match(r"requirements[-_].*\.txt$", name):
            for n, v, d in _parse_requirements_txt(content):
                all_raw.append((n, v, d, "pip"))

        elif name == "package.json" and '"name"' in content:
            for n, v, d in _parse_package_json(content):
                all_raw.append((n, v, d, "npm"))

        elif name == "cargo.toml":
            for n, v, d in _parse_cargo_toml(content):
                all_raw.append((n, v, d, "cargo"))

        elif name == "go.mod":
            for n, v, d in _parse_go_mod(content):
                all_raw.append((n, v, d, "go"))

    if not all_raw:
        logger.info("No dependency files found in repo")
        return []

    logger.info("Found %d raw dependencies across all manifests", len(all_raw))

    # Deduplicate by (name, ecosystem)
    seen = set()
    unique_raw = []
    for item in all_raw:
        key = (item[0].lower(), item[3])
        if key not in seen:
            seen.add(key)
            unique_raw.append(item)

    results: List[DependencyInfo] = []

    for name, version, is_dev, ecosystem in unique_raw:
        # Fetch latest version + metadata
        latest_version = version
        license_name: Optional[str] = None
        description: Optional[str] = None
        homepage: Optional[str] = None

        if ecosystem == "pip":
            meta = _pypi_metadata(name)
            latest_version = meta.get("version", version)
            license_name = meta.get("license") or (meta.get("classifiers") or [None])[0]
            description = meta.get("summary")
            homepage = meta.get("home_page") or meta.get("project_url")

        elif ecosystem == "npm":
            meta = _npm_metadata(name)
            latest_version = meta.get("version", version)
            license_name = meta.get("license")
            description = meta.get("description")
            homepage = meta.get("homepage")

        # Query OSV for CVEs (only if we have a version)
        cves: List[CVEInfo] = []
        if version:
            cves = _query_osv(name, version, ecosystem)

        results.append(DependencyInfo(
            name=name,
            current_version=version or "unknown",
            latest_version=latest_version or version or "unknown",
            update_status=_update_status(version, latest_version),
            license=license_name,
            license_ok=_license_ok(license_name),
            is_dev=is_dev,
            is_transitive=False,  # direct dep from manifest
            cves=cves,
            description=description,
            homepage=homepage,
            ecosystem=ecosystem,
        ))

    logger.info(
        "Dependency analysis complete: %d packages, %d with CVEs",
        len(results),
        sum(1 for r in results if r.cves),
    )
    return results