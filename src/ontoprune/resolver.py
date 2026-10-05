"""
Project Root Finder and Module Path Resolver for OntoPrune.

Translates relative and absolute Python import statements into local project
file paths, filtering out external third-party packages and standard libraries.
"""

from __future__ import annotations

import os
from pathlib import Path


def find_project_root(start_path: str | Path) -> Path:
    """
    Discovers project root by searching upwards for indicators:
    pyproject.toml, setup.py, setup.cfg, .git, or fallback to start directory.
    """
    cur = Path(start_path).resolve()
    if cur.is_file():
        cur = cur.parent

    root_markers = {
        "pyproject.toml",
        "setup.py",
        "setup.cfg",
        "pubspec.yaml",
        "package.json",
        "pom.xml",
        "build.gradle",
        ".git",
        ".hg",
    }

    while cur != cur.parent:
        if any((cur / marker).exists() for marker in root_markers):
            return cur
        cur = cur.parent

    # Fallback to initial directory
    fallback = Path(start_path).resolve()
    return fallback.parent if fallback.is_file() else fallback


def get_module_name(file_path: str | Path, project_root: str | Path) -> str:
    """
    Computes standard dotted module/package name relative to project root.
    Example: project_root/lib/services/order.dart -> lib.services.order
    """
    path = Path(file_path).resolve()
    root = Path(project_root).resolve()

    try:
        rel = path.relative_to(root)
    except ValueError:
        return path.stem

    parts = list(rel.parts)
    # Strip common file extensions
    for ext in (".py", ".dart", ".java", ".ts", ".tsx", ".js", ".jsx"):
        if parts[-1].endswith(ext):
            parts[-1] = parts[-1][: -len(ext)]
            break

    if parts[-1] == "__init__":
        parts.pop()

    return ".".join(parts) or path.stem


class ImportResolver:
    """
    Resolves import statements (Python, Dart, etc.) into concrete project file paths.
    """

    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).resolve()
        self.dart_package_name = self._find_dart_package_name()

    def _find_dart_package_name(self) -> str | None:
        pubspec = self.project_root / "pubspec.yaml"
        if pubspec.exists() and pubspec.is_file():
            import re

            content = pubspec.read_text(encoding="utf-8")
            m = re.search(r"^\s*name:\s*([a-zA-Z0-9_-]+)", content, re.MULTILINE)
            if m:
                return m.group(1).strip()
        return None

    def resolve_dart_import(
        self,
        current_file: str | Path,
        import_uri: str,
    ) -> Path | None:
        """
        Resolves a Dart import URI ('package:...', relative '../...') to a local file.
        Returns None for external SDKs ('dart:...') or external packages.
        """
        uri = import_uri.strip("\"'")
        if uri.startswith("dart:"):
            return None

        if uri.startswith("package:"):
            spec = uri[len("package:") :]
            parts = spec.split("/", 1)
            if len(parts) == 2:
                pkg_name, rel_path = parts
                if self.dart_package_name and pkg_name == self.dart_package_name:
                    cand = (self.project_root / "lib" / rel_path).resolve()
                    if cand.exists() and cand.is_file():
                        return cand
            return None

        # Relative import
        curr = Path(current_file).resolve()
        cand = (curr.parent / uri).resolve()
        if cand.exists() and cand.is_file():
            return cand
        if cand.with_suffix(".dart").exists() and cand.with_suffix(".dart").is_file():
            return cand.with_suffix(".dart")

        return None

    def resolve_java_import(
        self,
        current_file: str | Path,
        import_name: str,
    ) -> list[Path]:
        """
        Resolves a Java dotted class import (e.g. 'com.shop.repository.OrderRepository'
        or wildcard 'com.shop.model.*') to local project file(s).
        Returns empty list for external standard libraries or frameworks.
        """
        name = import_name.strip().rstrip(";")
        if name.startswith("static "):
            name = name[len("static ") :].strip()

        external_prefixes = (
            "java.",
            "javax.",
            "jakarta.",
            "org.springframework.",
            "org.junit.",
            "org.slf4j.",
            "org.apache.",
            "com.google.",
            "org.mockito.",
            "org.hibernate.",
        )
        if any(name.startswith(p) for p in external_prefixes):
            return []

        results: list[Path] = []

        if name.endswith(".*"):
            pkg_path = name[:-2].replace(".", os.sep)
            base_dirs = [
                self.project_root / "src" / "main" / "java" / pkg_path,
                self.project_root / "src" / pkg_path,
                self.project_root / "app" / "src" / "main" / "java" / pkg_path,
                self.project_root / pkg_path,
            ]
            for b in base_dirs:
                if b.exists() and b.is_dir():
                    for f in b.glob("*.java"):
                        if f.is_file():
                            results.append(f.resolve())
            return results

        rel_path = name.replace(".", os.sep) + ".java"
        candidates = [
            self.project_root / "src" / "main" / "java" / rel_path,
            self.project_root / "src" / rel_path,
            self.project_root / "app" / "src" / "main" / "java" / rel_path,
            self.project_root / rel_path,
        ]

        for cand in candidates:
            if cand.exists() and cand.is_file():
                results.append(cand.resolve())
                break

        return results

    def resolve_ts_import(
        self,
        current_file: str | Path,
        import_uri: str,
    ) -> Path | None:
        """
        Resolves a TypeScript/JavaScript relative import ('./...', '../...') to a local file.
        Returns None for external packages ('react', 'express', etc.).
        """
        uri = import_uri.strip("\"'")
        if not uri.startswith("."):
            return None

        curr = Path(current_file).resolve()
        base = (curr.parent / uri).resolve()

        if base.exists() and base.is_file():
            return base

        for ext in (".ts", ".tsx", ".js", ".jsx"):
            cand = base.with_suffix(ext)
            if cand.exists() and cand.is_file():
                return cand

        for idx in ("index.ts", "index.tsx", "index.js", "index.jsx"):
            cand = base / idx
            if cand.exists() and cand.is_file():
                return cand

        return None

    def resolve_import(
        self,
        current_file: str | Path,
        module: str | None,
        level: int = 0,
    ) -> Path | None:
        """
        Resolves a Python import target (e.g. from .models import Order or import app.billing)
        to a local project file if it exists, otherwise returns None (external/third-party).

        Args:
            current_file: Path of the file containing the import statement.
            module: The dotted module string (e.g. 'models.order' or None).
            level: Number of leading dots in relative import (0 for absolute, 1 for ., 2 for ..).
        """
        curr = Path(current_file).resolve()
        curr_dir = curr.parent

        candidate_base: Path

        if level > 0:
            # Relative import: level 1 is curr_dir, level 2 is curr_dir.parent, etc.
            target_dir = curr_dir
            for _ in range(level - 1):
                target_dir = target_dir.parent

            if module:
                module_rel_path = module.replace(".", os.sep)
                candidate_base = target_dir / module_rel_path
            else:
                candidate_base = target_dir
        else:
            # Absolute import relative to project root
            if not module:
                return None
            module_rel_path = module.replace(".", os.sep)
            candidate_base = self.project_root / module_rel_path

        # Check candidate locations:
        # 1. candidate.py
        file_cand = candidate_base.with_suffix(".py")
        if file_cand.exists() and file_cand.is_file():
            return file_cand

        # 2. candidate/__init__.py
        init_cand = candidate_base / "__init__.py"
        if init_cand.exists() and init_cand.is_file():
            return init_cand

        # 3. Search under project_root subpackages if root has a src/ directory
        src_cand = self.project_root / "src" / candidate_base.name
        if src_cand.with_suffix(".py").exists():
            return src_cand.with_suffix(".py")

        return None
