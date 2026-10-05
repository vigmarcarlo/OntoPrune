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

    root_markers = {"pyproject.toml", "setup.py", "setup.cfg", ".git", ".hg"}

    while cur != cur.parent:
        if any((cur / marker).exists() for marker in root_markers):
            return cur
        cur = cur.parent

    # Fallback to initial directory
    fallback = Path(start_path).resolve()
    return fallback.parent if fallback.is_file() else fallback


def get_module_name(file_path: str | Path, project_root: str | Path) -> str:
    """
    Computes standard Python dotted module name relative to project root.
    Example: project_root/app/services/order.py -> app.services.order
    """
    path = Path(file_path).resolve()
    root = Path(project_root).resolve()

    try:
        rel = path.relative_to(root)
    except ValueError:
        return path.stem

    parts = list(rel.parts)
    if parts[-1].endswith(".py"):
        parts[-1] = parts[-1][:-3]
    if parts[-1] == "__init__":
        parts.pop()

    return ".".join(parts) or path.stem


class ImportResolver:
    """
    Resolves AST import nodes into concrete project file paths.
    """

    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).resolve()

    def resolve_import(
        self,
        current_file: str | Path,
        module: str | None,
        level: int = 0,
    ) -> Path | None:
        """
        Resolves an import target (e.g. from .models import Order or import app.billing)
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
