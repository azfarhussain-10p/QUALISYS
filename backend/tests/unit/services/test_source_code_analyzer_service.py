"""
Unit tests — Source Code Analyzer Service (Story 2-4)
DoD A6: every test has a one-line comment stating the BEHAVIOUR proved.

Tests use pytest tmp_path fixture (real temp directories — no filesystem mocks needed).
SourceCodeAnalyzerService is pure Python stdlib; no DB, Redis, or network calls.
"""

import json
from pathlib import Path

import pytest

from src.services.source_code_analyzer_service import SourceCodeAnalyzerService


@pytest.fixture
def svc() -> SourceCodeAnalyzerService:
    return SourceCodeAnalyzerService()


# ---------------------------------------------------------------------------
# AC-11a: Framework Detection
# ---------------------------------------------------------------------------

class TestDetectFramework:

    def test_detect_fastapi_framework(self, svc, tmp_path):
        # Proves: *.py file containing FastAPI import → detect_framework returns 'fastapi'.
        (tmp_path / "main.py").write_text(
            "from fastapi import FastAPI\napp = FastAPI()\n"
        )
        assert svc.detect_framework(str(tmp_path)) == "fastapi"

    def test_detect_fastapi_via_instantiation(self, svc, tmp_path):
        # Proves: *.py file containing 'FastAPI()' (without import line) → returns 'fastapi'.
        (tmp_path / "app.py").write_text("app = FastAPI()\n")
        assert svc.detect_framework(str(tmp_path)) == "fastapi"

    def test_detect_express_framework(self, svc, tmp_path):
        # Proves: package.json with 'express' in dependencies → detect_framework returns 'express'.
        pkg = {"dependencies": {"express": "^4.18.2", "cors": "^2.8.5"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg))
        assert svc.detect_framework(str(tmp_path)) == "express"

    def test_detect_express_in_dev_dependencies(self, svc, tmp_path):
        # Proves: 'express' in devDependencies (not dependencies) → still returns 'express'.
        pkg = {"devDependencies": {"express": "^4.18.2"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg))
        assert svc.detect_framework(str(tmp_path)) == "express"

    def test_detect_spring_boot_framework(self, svc, tmp_path):
        # Proves: pom.xml containing 'spring-boot' artifact → detect_framework returns 'spring_boot'.
        (tmp_path / "pom.xml").write_text(
            "<dependency><artifactId>spring-boot-starter-web</artifactId></dependency>"
        )
        assert svc.detect_framework(str(tmp_path)) == "spring_boot"

    def test_detect_spring_boot_via_gradle(self, svc, tmp_path):
        # Proves: build.gradle containing 'spring-boot' plugin → returns 'spring_boot'.
        (tmp_path / "build.gradle").write_text(
            "plugins { id 'org.springframework.boot' version '3.2.0' }\n"
            "dependencies { implementation 'org.springframework.boot:spring-boot-starter' }"
        )
        assert svc.detect_framework(str(tmp_path)) == "spring_boot"

    def test_detect_unknown_framework(self, svc, tmp_path):
        # Proves: empty directory with no recognisable framework files → returns 'unknown'.
        assert svc.detect_framework(str(tmp_path)) == "unknown"

    def test_detect_framework_priority_fastapi_over_express(self, svc, tmp_path):
        # Proves: repo with both *.py FastAPI import AND package.json express → 'fastapi' wins (higher priority).
        (tmp_path / "main.py").write_text("from fastapi import FastAPI\n")
        pkg = {"dependencies": {"express": "^4.18.2"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg))
        assert svc.detect_framework(str(tmp_path)) == "fastapi"


# ---------------------------------------------------------------------------
# AC-11b: Route / Endpoint Extraction
# ---------------------------------------------------------------------------

class TestExtractRoutes:

    def test_extract_fastapi_routes(self, svc, tmp_path):
        # Proves: *.py with @app.get and @router.post decorators → 2 route dicts with correct method/path/file.
        py_file = tmp_path / "router.py"
        py_file.write_text(
            '@app.get("/api/users")\n'
            'async def list_users(): pass\n\n'
            '@router.post("/api/items")\n'
            'async def create_item(): pass\n'
        )
        routes = svc.extract_routes(str(tmp_path), "fastapi")
        assert len(routes) == 2
        methods = {r["method"] for r in routes}
        paths   = {r["path"] for r in routes}
        assert methods == {"GET", "POST"}
        assert "/api/users" in paths
        assert "/api/items" in paths
        # File is relative path
        assert all("router.py" in r["file"] for r in routes)

    def test_extract_fastapi_routes_all_methods(self, svc, tmp_path):
        # Proves: put/patch/delete decorators are extracted with correct uppercase method names.
        py_file = tmp_path / "api.py"
        py_file.write_text(
            '@router.put("/api/users/{id}")\n'
            'async def update_user(): pass\n'
            '@router.patch("/api/users/{id}/partial")\n'
            'async def patch_user(): pass\n'
            '@router.delete("/api/users/{id}")\n'
            'async def delete_user(): pass\n'
        )
        routes = svc.extract_routes(str(tmp_path), "fastapi")
        assert len(routes) == 3
        methods = {r["method"] for r in routes}
        assert methods == {"PUT", "PATCH", "DELETE"}

    def test_extract_express_routes(self, svc, tmp_path):
        # Proves: *.js with router.get and router.post calls → route dicts extracted with correct method.
        js_file = tmp_path / "routes.js"
        js_file.write_text(
            'router.get("/api/users", async (req, res) => {});\n'
            'router.post("/api/items", async (req, res) => {});\n'
        )
        routes = svc.extract_routes(str(tmp_path), "express")
        assert len(routes) == 2
        methods = {r["method"] for r in routes}
        assert methods == {"GET", "POST"}
        assert any(r["path"] == "/api/users" for r in routes)

    def test_extract_express_routes_from_ts(self, svc, tmp_path):
        # Proves: *.ts Express file → routes extracted (TypeScript files also scanned).
        ts_file = tmp_path / "routes.ts"
        ts_file.write_text('router.delete("/api/users/:id", handler);\n')
        routes = svc.extract_routes(str(tmp_path), "express")
        assert len(routes) == 1
        assert routes[0]["method"] == "DELETE"
        assert routes[0]["path"] == "/api/users/:id"

    def test_extract_spring_boot_routes(self, svc, tmp_path):
        # Proves: *.java with @GetMapping and @PostMapping → route dicts with correct methods.
        java_file = tmp_path / "UserController.java"
        java_file.write_text(
            '@GetMapping("/api/users")\n'
            'public List<User> listUsers() { return userService.findAll(); }\n\n'
            '@PostMapping("/api/users")\n'
            'public User createUser(@RequestBody UserDto dto) { return userService.create(dto); }\n'
        )
        routes = svc.extract_routes(str(tmp_path), "spring_boot")
        assert len(routes) == 2
        methods = {r["method"] for r in routes}
        assert "GET" in methods
        assert "POST" in methods

    def test_extract_routes_unknown_returns_empty(self, svc, tmp_path):
        # Proves: framework='unknown' → extract_routes returns empty list (C4).
        (tmp_path / "main.py").write_text("print('hello')\n")
        routes = svc.extract_routes(str(tmp_path), "unknown")
        assert routes == []


# ---------------------------------------------------------------------------
# AC-11c: Component Extraction
# ---------------------------------------------------------------------------

class TestExtractComponents:

    def test_extract_react_components_tsx(self, svc, tmp_path):
        # Proves: UserCard.tsx with capitalised filename stem → {name: 'UserCard', file: ...} returned.
        (tmp_path / "UserCard.tsx").write_text(
            "export default function UserCard({ user }) {\n  return <div>{user.name}</div>;\n}\n"
        )
        components = svc.extract_components(str(tmp_path))
        assert len(components) == 1
        assert components[0]["name"] == "UserCard"
        assert "UserCard.tsx" in components[0]["file"]

    def test_extract_react_components_jsx(self, svc, tmp_path):
        # Proves: Button.jsx with capitalised filename → included in component list.
        (tmp_path / "Button.jsx").write_text(
            "export default function Button({ label }) {\n  return <button>{label}</button>;\n}\n"
        )
        components = svc.extract_components(str(tmp_path))
        assert len(components) == 1
        assert components[0]["name"] == "Button"

    def test_extract_react_component_via_export_default(self, svc, tmp_path):
        # Proves: lowercase-named tsx file with 'export default function ComponentName' → included via fallback regex.
        tsx_file = tmp_path / "index.tsx"
        tsx_file.write_text(
            "export default function ProjectList() {\n  return <ul />;\n}\n"
        )
        components = svc.extract_components(str(tmp_path))
        assert len(components) == 1
        assert components[0]["name"] == "ProjectList"

    def test_extract_skips_lowercase_files_without_export(self, svc, tmp_path):
        # Proves: lowercase-named *.tsx file with no export default component → NOT included.
        (tmp_path / "utils.tsx").write_text("export const helper = () => null;\n")
        components = svc.extract_components(str(tmp_path))
        assert components == []

    def test_extract_ignores_non_tsx_jsx_files(self, svc, tmp_path):
        # Proves: *.ts files (not .tsx/.jsx) are NOT scanned for components.
        (tmp_path / "types.ts").write_text("export interface User { name: string; }\n")
        components = svc.extract_components(str(tmp_path))
        assert components == []

    def test_extract_components_multiple_files(self, svc, tmp_path):
        # Proves: multiple capitalised .tsx files → all included in component list.
        (tmp_path / "Header.tsx").write_text("export default function Header() { return <header />; }\n")
        (tmp_path / "Footer.tsx").write_text("export default function Footer() { return <footer />; }\n")
        (tmp_path / "utils.tsx").write_text("export const noop = () => {};\n")
        components = svc.extract_components(str(tmp_path))
        names = {c["name"] for c in components}
        assert "Header" in names
        assert "Footer" in names
        assert len(components) == 2  # utils.tsx excluded


# ---------------------------------------------------------------------------
# AC-11d: Full analysis summary
# ---------------------------------------------------------------------------

class TestAnalyze:

    def test_analyze_returns_complete_summary(self, svc, tmp_path):
        # Proves: tmp_path with FastAPI *.py + UserCard.tsx → summary dict has all required keys with correct types.
        (tmp_path / "main.py").write_text(
            "from fastapi import FastAPI\n"
            "app = FastAPI()\n\n"
            '@app.get("/api/v1/users")\n'
            "async def list_users(): pass\n"
        )
        (tmp_path / "UserCard.tsx").write_text(
            "export default function UserCard() { return <div />; }\n"
        )
        summary = svc.analyze(str(tmp_path))

        assert set(summary.keys()) == {"framework", "routes", "components", "endpoints"}
        assert summary["framework"] == "fastapi"
        assert isinstance(summary["routes"], list)
        assert isinstance(summary["components"], list)
        assert isinstance(summary["endpoints"], list)
        assert len(summary["routes"]) == 1
        assert summary["routes"][0]["method"] == "GET"
        assert summary["routes"][0]["path"] == "/api/v1/users"
        assert len(summary["components"]) == 1
        assert summary["components"][0]["name"] == "UserCard"
        # endpoints == routes in MVP
        assert summary["endpoints"] == summary["routes"]

    def test_analyze_unknown_framework_returns_empty_routes(self, svc, tmp_path):
        # Proves: empty tmp_path → framework='unknown', routes=[], components=[], endpoints=[] (C4 — not a failure).
        summary = svc.analyze(str(tmp_path))
        assert summary["framework"] == "unknown"
        assert summary["routes"] == []
        assert summary["components"] == []
        assert summary["endpoints"] == []

    def test_analyze_endpoints_equal_routes_in_mvp(self, svc, tmp_path):
        # Proves: endpoints list is the same content as routes list (MVP unification).
        (tmp_path / "main.py").write_text(
            "from fastapi import FastAPI\n"
            '@app.get("/ping")\n'
            "async def ping(): pass\n"
        )
        summary = svc.analyze(str(tmp_path))
        assert summary["endpoints"] == summary["routes"]
