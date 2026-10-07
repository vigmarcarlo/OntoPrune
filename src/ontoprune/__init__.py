"""
OntoPrune: Neuro-Symbolic Context Pruning Middleware for Local SLMs.
"""

from __future__ import annotations

from pathlib import Path

from ontoprune.check import check
from ontoprune.parser import parse_file, parse_source
from ontoprune.project import parse_project_file
from ontoprune.pruner import find_symbol_uri, prune_subgraph
from ontoprune.render import RENDERERS, render_contract

__version__ = "0.3.0"
__all__ = [
    "RENDERERS",
    "check",
    "find_symbol_uri",
    "parse_file",
    "parse_project_file",
    "parse_source",
    "prune_subgraph",
    "render_contract",
    "translate",
]


def translate(
    source_or_file: str | Path,
    target: str,
    fmt: str = "stubs",
    include_body: bool = False,
    multi_module: bool = True,
    project_root: str | Path | None = None,
) -> str:
    """
    Translates source code and a target symbol into a pruned, minimal context.
    Automatically resolves multi-module imports if source_or_file is a file path.

    Args:
        source_or_file: Path to source file or source code string.
        target: Target function or method identifier.
        fmt: Output format ('stubs', 'turtle', 'json', 'nl').
        include_body: Whether to include the target function's source code body.
        multi_module: Whether to recursively resolve project imports (default: True).
        project_root: Optional root directory of the project (auto-detected if None).

    Returns:
        Rendered string representation of the pruned contract.
    """
    path_obj = Path(source_or_file) if isinstance(source_or_file, (str, Path)) else None
    if path_obj and path_obj.exists() and path_obj.is_file():
        supported_multi = {".py", ".dart", ".java", ".ts", ".tsx"}
        if multi_module and path_obj.suffix.lower() in supported_multi:
            graph = parse_project_file(path_obj, project_root=project_root, include_bodies=include_body)
        else:
            graph = parse_file(path_obj, include_bodies=include_body)
    else:
        graph = parse_source(str(source_or_file))

    subgraph, target_uri = prune_subgraph(graph, target_symbol=target, include_body=include_body)
    return render_contract(subgraph, target_uri=target_uri, fmt=fmt)
