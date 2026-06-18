"""
health_scorer.py
----------------
Computes a composite health score (0–100) and letter grade (A+→F)
for a GitHub repository across six weighted categories:

  1. Documentation  (20%) — README, docstrings, inline comments
  2. Commit Activity(20%) — how recently and frequently commits happen
  3. Test Coverage  (20%) — presence and depth of test files
  4. Dependencies   (15%) — freshness and number of outdated packages
  5. Security       (15%) — CVE count and severity
  6. Community      (10%) — stars, open issues, forks

Each category scores 0–100. The overall score is the weighted average.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional

logger = logging.getLogger(__name__)


# ── Data classes ───────────────────────────────────────────────────────────────

@dataclass
class CategoryScore:
    key: str
    label: str
    score: float           # 0–100
    weight: float          # 0.0–1.0 (all weights must sum to 1.0)
    description: str       # human-readable explanation


@dataclass
class HealthResult:
    overall: float                          # 0–100 weighted average
    grade: str                              # A+, A, B+, B, C+, C, D, F
    trend: str                              # "up" | "down" | "stable"
    categories: List[CategoryScore] = field(default_factory=list)
    generated_at: str = ""


# ── Grade table ────────────────────────────────────────────────────────────────

def _score_to_grade(score: float) -> str:
    if score >= 95: return "A+"
    if score >= 88: return "A"
    if score >= 80: return "B+"
    if score >= 72: return "B"
    if score >= 64: return "C+"
    if score >= 55: return "C"
    if score >= 45: return "D"
    return "F"


# ── Individual scorers ─────────────────────────────────────────────────────────

def _score_documentation(files: List[dict], functions: List[dict]) -> CategoryScore:
    """
    Score based on:
    - Has README (30 pts)
    - README length (up to 20 pts — penalise one-liner READMEs)
    - Docstring coverage on functions (up to 30 pts)
    - Inline comment density (up to 20 pts)
    """
    score = 0.0

    file_names = {f.get("path", "").lower() for f in files}
    readme_files = [f for f in files if "readme" in f.get("path", "").lower()]

    # README presence (30 pts)
    if readme_files:
        score += 30
        readme_content = readme_files[0].get("content", "")
        # README length score: 20 pts if > 1000 chars, scaled below
        readme_len = len(readme_content)
        score += min(20, (readme_len / 1000) * 20)

    # Docstring coverage (30 pts)
    if functions:
        documented = sum(1 for f in functions if f.get("docstring"))
        ratio = documented / len(functions)
        score += ratio * 30

    # Comment density (20 pts): count lines with # or // or /* across files
    total_lines = 0
    comment_lines = 0
    for f in files[:50]:  # sample first 50 files
        content = f.get("content", "")
        lines = content.splitlines()
        total_lines += len(lines)
        comment_lines += sum(
            1 for line in lines
            if line.strip().startswith(("#", "//", "/*", "*", "'''", '"""'))
        )

    if total_lines > 0:
        comment_ratio = comment_lines / total_lines
        score += min(20, comment_ratio * 100)

    score = min(100.0, score)
    return CategoryScore(
        key="documentation",
        label="Documentation",
        score=round(score, 1),
        weight=0.20,
        description=f"README {'found' if readme_files else 'missing'}, "
                    f"{sum(1 for f in functions if f.get('docstring'))}/{len(functions)} functions documented",
    )


def _score_commit_activity(commits: List[dict], pushed_at: Optional[str]) -> CategoryScore:
    """
    Score based on:
    - Days since last commit (up to 40 pts)
    - Commit frequency over last 90 days (up to 40 pts)
    - Total commit count (up to 20 pts)
    """
    score = 0.0
    now = datetime.now(timezone.utc)

    # Days since last push (40 pts)
    if pushed_at:
        try:
            last_push = datetime.fromisoformat(pushed_at.replace("Z", "+00:00"))
            days_ago = (now - last_push).days
            if days_ago <= 7:
                score += 40
            elif days_ago <= 30:
                score += 35
            elif days_ago <= 90:
                score += 25
            elif days_ago <= 180:
                score += 15
            elif days_ago <= 365:
                score += 8
            else:
                score += 2
        except Exception:
            pass

    # Commit frequency — recent 90 days (40 pts)
    if commits:
        recent_commits = 0
        for commit in commits:
            commit_date_str = commit.get("date", "")
            if commit_date_str:
                try:
                    commit_date = datetime.fromisoformat(commit_date_str.replace("Z", "+00:00"))
                    if (now - commit_date).days <= 90:
                        recent_commits += 1
                except Exception:
                    pass

        # 10+ commits in 90 days = full marks, scaled below
        score += min(40, (recent_commits / 10) * 40)

        # Total commits (20 pts): 50+ = full marks
        score += min(20, (len(commits) / 50) * 20)

    score = min(100.0, score)
    desc = f"{len(commits)} total commits" if commits else "No commit data"
    if pushed_at:
        try:
            last_push = datetime.fromisoformat(pushed_at.replace("Z", "+00:00"))
            days_ago = (now - last_push).days
            desc += f", last push {days_ago}d ago"
        except Exception:
            pass

    return CategoryScore(
        key="commits",
        label="Commit Activity",
        score=round(score, 1),
        weight=0.20,
        description=desc,
    )


def _score_tests(files: List[dict]) -> CategoryScore:
    """
    Score based on:
    - Presence of a test directory (30 pts)
    - Number of test files relative to source files (up to 50 pts)
    - Presence of CI config file (20 pts)
    """
    score = 0.0

    file_paths = [f.get("path", "").lower() for f in files]

    # Test directory
    has_test_dir = any(
        "test" in p or "spec" in p or "__tests__" in p
        for p in file_paths
    )
    if has_test_dir:
        score += 30

    # Count test files
    test_files = [
        p for p in file_paths
        if any(kw in p for kw in ("test_", "_test.", ".test.", ".spec.", "_spec."))
        or p.startswith("test/") or "/test/" in p or "/tests/" in p
    ]
    source_files = [
        p for p in file_paths
        if not any(kw in p for kw in ("test", "spec", "node_modules", ".git", "vendor"))
        and any(p.endswith(ext) for ext in (".py", ".ts", ".js", ".go", ".rs", ".java"))
    ]

    if source_files:
        ratio = len(test_files) / len(source_files)
        score += min(50, ratio * 100)

    # CI configuration
    ci_files = {".github/workflows", ".travis.yml", "circle.yml", ".circleci",
                "Jenkinsfile", ".gitlab-ci.yml", "azure-pipelines.yml"}
    has_ci = any(any(ci in p for ci in ci_files) for p in file_paths)
    if has_ci:
        score += 20

    score = min(100.0, score)
    return CategoryScore(
        key="tests",
        label="Test Coverage",
        score=round(score, 1),
        weight=0.20,
        description=f"{len(test_files)} test files, CI {'configured' if has_ci else 'not found'}",
    )


def _score_dependencies(dependencies: List[dict]) -> CategoryScore:
    """
    Score based on:
    - Ratio of up-to-date packages (up to 70 pts)
    - No deprecated packages (20 pts bonus)
    - Reasonable total dependency count (10 pts)
    """
    if not dependencies:
        return CategoryScore(
            key="dependencies", label="Dependencies",
            score=70.0, weight=0.15,
            description="No dependency files found",
        )

    total = len(dependencies)
    up_to_date = sum(1 for d in dependencies if d.get("update_status") == "up-to-date")
    deprecated = sum(1 for d in dependencies if d.get("update_status") == "deprecated")
    major_outdated = sum(1 for d in dependencies if d.get("update_status") == "major")

    score = (up_to_date / total) * 70
    if deprecated == 0:
        score += 20
    elif deprecated <= 2:
        score += 10

    # Penalise excessive dependencies (>100 suggests poor hygiene)
    if total <= 30:
        score += 10
    elif total <= 60:
        score += 5

    score = min(100.0, score)
    outdated = total - up_to_date
    return CategoryScore(
        key="dependencies", label="Dependencies",
        score=round(score, 1),
        weight=0.15,
        description=f"{up_to_date}/{total} up-to-date, {deprecated} deprecated, {major_outdated} major updates available",
    )


def _score_security(dependencies: List[dict]) -> CategoryScore:
    """
    Score based on CVE presence in dependencies.
    - 0 CVEs = 100
    - Each critical CVE: -25 pts
    - Each high CVE: -15 pts
    - Each medium CVE: -8 pts
    - Each low CVE: -3 pts
    """
    score = 100.0

    severity_penalty = {
        "critical": 25,
        "high": 15,
        "medium": 8,
        "low": 3,
    }

    total_cves = 0
    for dep in dependencies:
        for cve in dep.get("cves", []):
            sev = cve.get("severity", "low")
            score -= severity_penalty.get(sev, 3)
            total_cves += 1

    score = max(0.0, score)

    vuln_pkgs = sum(1 for d in dependencies if d.get("cves"))
    critical = sum(
        1 for d in dependencies
        for c in d.get("cves", [])
        if c.get("severity") == "critical"
    )

    desc = (
        "No known vulnerabilities" if total_cves == 0
        else f"{total_cves} CVEs across {vuln_pkgs} packages"
             + (f", {critical} critical" if critical else "")
    )

    return CategoryScore(
        key="security", label="Security",
        score=round(score, 1),
        weight=0.15,
        description=desc,
    )


def _score_community(
    stars: int,
    forks: int,
    open_issues: int,
    watchers: int,
) -> CategoryScore:
    """
    Score based on community engagement signals.
    Uses logarithmic scaling so a repo with 10 stars doesn't score 0.
    """
    # Stars (50 pts): log scale, 1000 stars = ~50 pts
    star_score = min(50, math.log1p(stars) / math.log1p(1000) * 50)

    # Forks (25 pts): log scale
    fork_score = min(25, math.log1p(forks) / math.log1p(200) * 25)

    # Issues aren't negative — having issues means people use it (15 pts)
    issue_score = min(15, math.log1p(open_issues) / math.log1p(50) * 15)

    # Watchers (10 pts)
    watcher_score = min(10, math.log1p(watchers) / math.log1p(100) * 10)

    score = star_score + fork_score + issue_score + watcher_score
    score = min(100.0, score)

    return CategoryScore(
        key="activity",
        label="Community Activity",
        score=round(score, 1),
        weight=0.10,
        description=f"{stars:,} stars, {forks:,} forks, {open_issues:,} open issues",
    )


# ── Trend detection ────────────────────────────────────────────────────────────

def _detect_trend(commits: List[dict]) -> str:
    """
    Compare commit frequency in the last 30 days vs the prior 30 days.
    Returns "up", "down", or "stable".
    """
    if not commits:
        return "stable"

    now = datetime.now(timezone.utc)
    last_30 = 0
    prior_30 = 0

    for commit in commits:
        date_str = commit.get("date", "")
        if not date_str:
            continue
        try:
            commit_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            days_ago = (now - commit_date).days
            if days_ago <= 30:
                last_30 += 1
            elif days_ago <= 60:
                prior_30 += 1
        except Exception:
            continue

    if prior_30 == 0:
        return "stable" if last_30 == 0 else "up"

    ratio = last_30 / prior_30
    if ratio >= 1.2:
        return "up"
    if ratio <= 0.8:
        return "down"
    return "stable"


# ── Main entry point ───────────────────────────────────────────────────────────

def compute_health_score(
    files: List[dict],
    functions: List[dict],
    commits: List[dict],
    dependencies: List[dict],
    stars: int = 0,
    forks: int = 0,
    open_issues: int = 0,
    watchers: int = 0,
    pushed_at: Optional[str] = None,
) -> HealthResult:
    """
    Compute the full health score for a repository.

    Args:
        files:        List of {"path", "content", "language"} dicts.
        functions:    List of extracted function dicts from ast_parser.
        commits:      List of {"date", "message", "author"} dicts.
        dependencies: List of DependencyInfo dicts (serialised).
        stars:        GitHub star count.
        forks:        GitHub fork count.
        open_issues:  GitHub open issue count.
        watchers:     GitHub watcher count.
        pushed_at:    ISO datetime of the last push.

    Returns:
        HealthResult with overall score, grade, trend, and per-category breakdown.
    """
    categories = [
        _score_documentation(files, functions),
        _score_commit_activity(commits, pushed_at),
        _score_tests(files),
        _score_dependencies(dependencies),
        _score_security(dependencies),
        _score_community(stars, forks, open_issues, watchers),
    ]

    # Weighted average
    overall = sum(cat.score * cat.weight for cat in categories)
    overall = round(min(100.0, max(0.0, overall)), 1)

    trend = _detect_trend(commits)
    grade = _score_to_grade(overall)

    logger.info(
        "Health score computed: overall=%.1f grade=%s trend=%s",
        overall, grade, trend
    )
    for cat in categories:
        logger.debug("  %s: %.1f (weight=%.0f%%)", cat.label, cat.score, cat.weight * 100)

    return HealthResult(
        overall=overall,
        grade=grade,
        trend=trend,
        categories=categories,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )