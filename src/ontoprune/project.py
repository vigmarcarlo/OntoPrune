"""
Recursive Multi-Module AST Parser and Ontological Project Graph.

Traverses Python projects on-demand starting from an initial target file,
following internal imports to build an interconnected code graph.
"""

from __future__ import annotations

import ast
from pathlib import Path

import rdflib

from ontoprune.parser import OntoVisitor, SymbolCollector
from ontoprune.resolver import ImportResolver, find_project_root, get_module_name


class ImportFinder(ast.NodeVisitor):
    """Collects all internal project dependencies imported in an AST."""

    def __init__(self, current_file: Path, resolver: ImportResolver) -> None:
        self.current_file = current_file
        self.resolver = resolver
        self.resolved_files: set[Path] = set()
        self.imported_symbols: dict[
            str, tuple[Path, str]
        ] = {}  # local_alias -> (source_file, original_name)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            resolved = self.resolver.resolve_import(
                current_file=self.current_file,
                module=alias.name,
                level=0,
            )
            if resolved:
                self.resolved_files.add(resolved)
                self.imported_symbols[alias.asname or alias.name] = (resolved, alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        resolved = self.resolver.resolve_import(
            current_file=self.current_file,
            module=node.module,
            level=node.level,
        )
        if resolved:
            self.resolved_files.add(resolved)
            for alias in node.names:
                local_name = alias.asname or alias.name
                self.imported_symbols[local_name] = (resolved, alias.name)

        self.generic_visit(node)


class ProjectGraph:
    """
    Builds and manages an interconnected RDF graph across multiple files in a project.
    """

    def __init__(self, project_root: str | Path | None = None) -> None:
        self.project_root: Path | None = Path(project_root).resolve() if project_root else None
        self.graph = rdflib.Graph()
        self.visited_files: set[Path] = set()
        self.symbols_by_file: dict[Path, SymbolCollector] = {}

    def parse_project_for_file(
        self,
        entry_file: str | Path,
        max_depth: int = 3,
    ) -> rdflib.Graph:
        """
        Recursively parses entry_file and its imported internal dependencies up to max_depth.
        """
        entry_path = Path(entry_file).resolve()
        if not self.project_root:
            self.project_root = find_project_root(entry_path)

        resolver = ImportResolver(self.project_root)

        # Queue of files to parse: (file_path, current_depth)
        queue: list[tuple[Path, int]] = [(entry_path, 0)]
        collected_trees: dict[Path, tuple[ast.AST, str, SymbolCollector]] = {}

        # Pass 1: Discover and collect symbols across connected project files
        while queue:
            file_path, depth = queue.pop(0)
            if file_path in self.visited_files:
                continue
            if not file_path.exists() or not file_path.is_file():
                continue

            self.visited_files.add(file_path)

            source_code = file_path.read_text(encoding="utf-8")
            try:
                tree = ast.parse(source_code)
            except SyntaxError:
                continue

            mod_name = get_module_name(file_path, self.project_root)
            collector = SymbolCollector(module_name=mod_name)
            collector.visit(tree)
            collector.finalize()

            collected_trees[file_path] = (tree, source_code, collector)
            self.symbols_by_file[file_path] = collector

            if depth < max_depth:
                finder = ImportFinder(file_path, resolver)
                finder.visit(tree)
                for dep in finder.resolved_files:
                    if dep not in self.visited_files:
                        queue.append((dep, depth + 1))

        # Pass 2: Merge symbols across all modules to resolve cross-module calls
        global_classes: set[str] = set()
        global_functions: set[str] = set()
        global_methods: dict[str, dict[str, str]] = {}
        global_attr_types: dict[str, dict[str, str]] = {}
        for _, _, col in collected_trees.values():
            global_classes.update(col.classes)
            global_functions.update(col.functions)
            global_methods.update(col.all_class_methods)
            global_attr_types.update(col.attr_types)

        # Pass 3: Populate shared RDF graph with cross-module awareness
        for file_path, (tree, src, collector) in collected_trees.items():
            collector.classes.update(global_classes)
            collector.functions.update(global_functions)
            collector.all_class_methods = global_methods
            collector.attr_types.update(global_attr_types)

            mod_name = get_module_name(file_path, self.project_root)
            visitor = OntoVisitor(
                source_code=src,
                symbols=collector,
                module_name=mod_name,
                include_bodies=False,
            )
            visitor.visit(tree)

            # Merge into master graph
            for triple in visitor.graph:
                self.graph.add(triple)

        return self.graph


def parse_project_file(
    file_path: str | Path,
    project_root: str | Path | None = None,
) -> rdflib.Graph:
    """Convenience function to parse a file and its project dependencies into an RDF graph."""
    project = ProjectGraph(project_root=project_root)
    return project.parse_project_for_file(file_path)
