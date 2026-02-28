"""
QUALISYS — Source Code Analyzer Service
Story: 2-4-source-code-analysis
AC: #11a — detect backend framework (FastAPI, Express.js, Spring Boot, unknown)
AC: #11b — extract routes/endpoints {method, path, file}
AC: #11c — extract React components {name, file}
AC: #11d — build analysis_summary JSON for github_connections
AC: #11e — exceptions bubble up so caller can set status='failed'

Security (C1):
  - Pure filesystem operations only — no SQL, no network calls
  - All paths stored as relative to clone_path (no absolute filesystem paths exposed)
  - No user data interpolated into regex or file operations

Constraint (C3): stdlib only — os, re, json, pathlib. No new pip packages.
Constraint (C4): unknown framework is NOT a failure — returns 'unknown', status still set to 'analyzed'.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Compiled regex patterns
# ---------------------------------------------------------------------------

# AC-11a: FastAPI detection
_FASTAPI_IMPORT_RE = re.compile(r'from fastapi import|FastAPI\(\)')

# AC-11a: Spring Boot detection in pom.xml / build.gradle
_SPRING_BOOT_RE = re.compile(r'spring-boot')

# AC-11b: FastAPI route decorators
# Matches: @app.get("/path") or @router.post("/path") etc.
# Groups: (1) http_method, (2) path
_FASTAPI_ROUTE_RE = re.compile(
    r'@(?:app|router)\.(get|post|put|patch|delete)\(["\']([^"\']+)["\']',
    re.IGNORECASE,
)

# AC-11b: Express.js route definitions
# Matches: router.get("/path") or router.post("/path") etc.
# Groups: (1) http_method, (2) path
_EXPRESS_ROUTE_RE = re.compile(
    r'router\.(get|post|put|patch|delete)\(["\']([^"\']+)["\']',
    re.IGNORECASE,
)

# AC-11b: Spring Boot mapping annotations
# Matches: @GetMapping("/path") or @PostMapping("/path") etc.
# Groups: (1) annotation_name, (2) path
_SPRING_ROUTE_RE = re.compile(
    r'@(GetMapping|PostMapping|PutMapping|DeleteMapping|RequestMapping)'
    r'\(["\']?([^"\')\s]+)["\']?\)',
)

# Maps Spring annotation name → HTTP method
_SPRING_METHOD_MAP: dict[str, str] = {
    "getmapping":     "GET",
    "postmapping":    "POST",
    "putmapping":     "PUT",
    "deletemapping":  "DELETE",
    "requestmapping": "GET",  # RequestMapping defaults to GET for MVP
}

# AC-11c: React component — export default function/class ComponentName
_REACT_COMPONENT_RE = re.compile(
    r'export\s+default\s+(?:function|class)\s+([A-Z][A-Za-z0-9_]*)'
)


# ---------------------------------------------------------------------------
# SourceCodeAnalyzerService
# ---------------------------------------------------------------------------

class SourceCodeAnalyzerService:
    """
    Analyses a cloned GitHub repository to extract framework, routes,
    and React component structure.

    Operates entirely on the local filesystem — no network or DB calls.
    All methods are synchronous (pure CPU/IO); designed to be called from
    clone_repo_task which runs analysis inside a BackgroundTask.
    """

    # ------------------------------------------------------------------
    # AC-11a: Framework detection
    # ------------------------------------------------------------------

    def detect_framework(self, clone_path: str) -> str:
        """
        Detect the backend framework used in the cloned repository.

        Priority order: FastAPI → Express.js → Spring Boot → 'unknown'.
        Returns lowercase string: 'fastapi' | 'express' | 'spring_boot' | 'unknown'.
        Unknown framework is NOT a failure (C4).
        """
        root = Path(clone_path)

        # 1. FastAPI: walk *.py files for FastAPI import or instantiation
        for dirpath, _dirs, files in os.walk(root):
            for fname in files:
                if not fname.endswith('.py'):
                    continue
                try:
                    content = Path(dirpath, fname).read_text(
                        encoding='utf-8', errors='ignore'
                    )
                    if _FASTAPI_IMPORT_RE.search(content):
                        return 'fastapi'
                except OSError:
                    continue

        # 2. Express.js: package.json in repo root with 'express' in deps
        pkg_json = root / 'package.json'
        if pkg_json.exists():
            try:
                pkg = json.loads(
                    pkg_json.read_text(encoding='utf-8', errors='ignore')
                )
                all_deps = {
                    **pkg.get('dependencies', {}),
                    **pkg.get('devDependencies', {}),
                }
                if 'express' in all_deps:
                    return 'express'
            except (OSError, json.JSONDecodeError):
                pass

        # 3. Spring Boot: pom.xml or build.gradle containing 'spring-boot'
        for spring_file in ('pom.xml', 'build.gradle', 'build.gradle.kts'):
            spring_path = root / spring_file
            if spring_path.exists():
                try:
                    content = spring_path.read_text(
                        encoding='utf-8', errors='ignore'
                    )
                    if _SPRING_BOOT_RE.search(content):
                        return 'spring_boot'
                except OSError:
                    pass

        return 'unknown'

    # ------------------------------------------------------------------
    # AC-11b: Route / endpoint extraction
    # ------------------------------------------------------------------

    def extract_routes(
        self, clone_path: str, framework: str
    ) -> list[dict[str, str]]:
        """
        Extract route definitions from source files using regex scan.

        Returns list of {method, path, file} dicts.
        'file' is relative to clone_path (C7).
        Returns [] for unknown framework (C4).
        """
        root = Path(clone_path)
        routes: list[dict[str, str]] = []

        if framework == 'fastapi':
            for dirpath, _dirs, files in os.walk(root):
                for fname in files:
                    if not fname.endswith('.py'):
                        continue
                    fpath = Path(dirpath, fname)
                    try:
                        content = fpath.read_text(
                            encoding='utf-8', errors='ignore'
                        )
                    except OSError:
                        continue
                    rel_file = str(fpath.relative_to(root))
                    for match in _FASTAPI_ROUTE_RE.finditer(content):
                        routes.append({
                            'method': match.group(1).upper(),
                            'path':   match.group(2),
                            'file':   rel_file,
                        })

        elif framework == 'express':
            for dirpath, _dirs, files in os.walk(root):
                for fname in files:
                    if not (fname.endswith('.js') or fname.endswith('.ts')):
                        continue
                    fpath = Path(dirpath, fname)
                    try:
                        content = fpath.read_text(
                            encoding='utf-8', errors='ignore'
                        )
                    except OSError:
                        continue
                    rel_file = str(fpath.relative_to(root))
                    for match in _EXPRESS_ROUTE_RE.finditer(content):
                        routes.append({
                            'method': match.group(1).upper(),
                            'path':   match.group(2),
                            'file':   rel_file,
                        })

        elif framework == 'spring_boot':
            for dirpath, _dirs, files in os.walk(root):
                for fname in files:
                    if not fname.endswith('.java'):
                        continue
                    fpath = Path(dirpath, fname)
                    try:
                        content = fpath.read_text(
                            encoding='utf-8', errors='ignore'
                        )
                    except OSError:
                        continue
                    rel_file = str(fpath.relative_to(root))
                    for match in _SPRING_ROUTE_RE.finditer(content):
                        annotation = match.group(1).lower()
                        method = _SPRING_METHOD_MAP.get(annotation, 'GET')
                        routes.append({
                            'method': method,
                            'path':   match.group(2),
                            'file':   rel_file,
                        })

        # framework == 'unknown': returns []
        return routes

    # ------------------------------------------------------------------
    # AC-11c: React component extraction
    # ------------------------------------------------------------------

    def extract_components(self, clone_path: str) -> list[dict[str, str]]:
        """
        Scan all *.tsx and *.jsx files for React components.

        Returns list of {name, file} dicts; file is relative to clone_path (C7).
        A file qualifies if:
          - filename stem starts with an uppercase letter (primary heuristic), OR
          - file contains 'export default function/class ComponentName' (fallback).
        """
        root = Path(clone_path)
        components: list[dict[str, str]] = []

        for dirpath, _dirs, files in os.walk(root):
            for fname in files:
                if not (fname.endswith('.tsx') or fname.endswith('.jsx')):
                    continue
                fpath = Path(dirpath, fname)
                stem = fpath.stem
                rel_file = str(fpath.relative_to(root))

                # Primary: capitalised filename stem → component name = stem
                if stem and stem[0].isupper():
                    components.append({'name': stem, 'file': rel_file})
                    continue

                # Fallback: explicit export default function/class with capital name
                try:
                    content = fpath.read_text(
                        encoding='utf-8', errors='ignore'
                    )
                except OSError:
                    continue
                match = _REACT_COMPONENT_RE.search(content)
                if match:
                    components.append({'name': match.group(1), 'file': rel_file})

        return components

    # ------------------------------------------------------------------
    # AC-11d/e: Orchestrate
    # ------------------------------------------------------------------

    def analyze(self, clone_path: str) -> dict[str, Any]:
        """
        Orchestrate: detect_framework → extract_routes → extract_components.

        Returns {framework, routes, components, endpoints}.
        endpoints == routes in MVP (same extraction, different label for agents).
        Exceptions are NOT caught here — they bubble up to clone_repo_task
        which sets status='failed' (AC-11e).
        """
        framework = self.detect_framework(clone_path)
        routes = self.extract_routes(clone_path, framework)
        components = self.extract_components(clone_path)

        return {
            'framework':  framework,
            'routes':     routes,
            'components': components,
            'endpoints':  routes,  # MVP: endpoints and routes are the same list
        }


# Module-level singleton — imported by clone_repo_task (github_connector_service.py)
source_code_analyzer_service = SourceCodeAnalyzerService()
