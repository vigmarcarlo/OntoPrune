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

        if entry_path.suffix.lower() == ".dart":
            return self._parse_dart_project_for_file(entry_path, max_depth)
        elif entry_path.suffix.lower() == ".java":
            return self._parse_java_project_for_file(entry_path, max_depth)
        elif entry_path.suffix.lower() in (".ts", ".tsx", ".js", ".jsx"):
            return self._parse_ts_project_for_file(entry_path, max_depth)

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

    def _parse_dart_project_for_file(
        self,
        entry_path: Path,
        max_depth: int = 3,
    ) -> rdflib.Graph:
        """Recursively parses Dart/Flutter project dependencies using Tree-Sitter."""
        from ontoprune.treesitter_parser import DartParser

        parser = DartParser()
        resolver = ImportResolver(self.project_root)

        queue: list[tuple[Path, int]] = [(entry_path, 0)]
        collected_sources: dict[Path, str] = {}
        all_classes: set[str] = set()
        all_methods: dict[str, set[str]] = {}
        all_fields: dict[str, dict[str, str]] = {}

        # Pass 1: Discover connected Dart files and collect symbols
        while queue:
            file_path, depth = queue.pop(0)
            if file_path in self.visited_files:
                continue
            if not file_path.exists() or not file_path.is_file():
                continue

            self.visited_files.add(file_path)
            source_code = file_path.read_text(encoding="utf-8")
            collected_sources[file_path] = source_code

            # Collect symbols
            cls_set, m_dict, f_dict = parser.collect_symbols(source_code)
            all_classes.update(cls_set)
            for c, m in m_dict.items():
                all_methods.setdefault(c, set()).update(m)
            for c, f in f_dict.items():
                all_fields.setdefault(c, {}).update(f)

            if depth < max_depth:
                imports = parser.extract_imports(source_code)
                for imp_uri in imports:
                    resolved = resolver.resolve_dart_import(file_path, imp_uri)
                    if resolved and resolved not in self.visited_files:
                        queue.append((resolved, depth + 1))

        # Pass 2: Parse each Dart file with full cross-file symbol knowledge
        for file_path, src in collected_sources.items():
            mod_name = get_module_name(file_path, self.project_root)
            file_graph = parser.parse(
                source_code=src,
                module_name=mod_name,
                include_bodies=False,
                global_classes=all_classes,
                global_class_methods=all_methods,
                global_class_fields=all_fields,
            )
            for triple in file_graph:
                self.graph.add(triple)

        return self.graph

    def _parse_java_project_for_file(
        self,
        entry_path: Path,
        max_depth: int = 3,
    ) -> rdflib.Graph:
        """Recursively parses Java project dependencies using Tree-Sitter."""
        from ontoprune.treesitter_parser import JavaParser

        parser = JavaParser()
        resolver = ImportResolver(self.project_root)

        queue: list[tuple[Path, int]] = [(entry_path, 0)]
        collected_sources: dict[Path, str] = {}
        all_classes: set[str] = set()
        all_methods: dict[str, set[str]] = {}
        all_fields: dict[str, dict[str, str]] = {}

        # Pass 1: Discover connected Java files and collect symbols
        while queue:
            file_path, depth = queue.pop(0)
            if file_path in self.visited_files:
                continue
            if not file_path.exists() or not file_path.is_file():
                continue

            self.visited_files.add(file_path)
            source_code = file_path.read_text(encoding="utf-8")
            collected_sources[file_path] = source_code

            # Collect symbols
            cls_set, m_dict, f_dict = parser.collect_symbols(source_code)
            all_classes.update(cls_set)
            for c, m in m_dict.items():
                all_methods.setdefault(c, set()).update(m)
            for c, f in f_dict.items():
                all_fields.setdefault(c, {}).update(f)

            if depth < max_depth:
                imports = parser.extract_imports(source_code)
                for imp_name in imports:
                    resolved_list = resolver.resolve_java_import(file_path, imp_name)
                    for resolved in resolved_list:
                        if resolved not in self.visited_files:
                            queue.append((resolved, depth + 1))

                # Also inspect package siblings in same directory
                for sibling in file_path.parent.glob("*.java"):
                    if sibling not in self.visited_files and sibling.is_file():
                        queue.append((sibling, depth + 1))

        # Pass 2: Parse each Java file with full cross-file symbol knowledge
        for file_path, src in collected_sources.items():
            mod_name = get_module_name(file_path, self.project_root)
            file_graph = parser.parse(
                source_code=src,
                module_name=mod_name,
                include_bodies=False,
                global_classes=all_classes,
                global_class_methods=all_methods,
                global_class_fields=all_fields,
            )
            for triple in file_graph:
                self.graph.add(triple)

        return self.graph

    def _parse_ts_project_for_file(
        self,
        entry_path: Path,
        max_depth: int = 3,
    ) -> rdflib.Graph:
        """Recursively parses TypeScript/JavaScript project dependencies using Tree-Sitter."""
        from ontoprune.treesitter_parser import TypeScriptParser

        resolver = ImportResolver(self.project_root)

        queue: list[tuple[Path, int]] = [(entry_path, 0)]
        collected_sources: dict[Path, tuple[str, bool]] = {}
        all_classes: set[str] = set()
        all_methods: dict[str, set[str]] = {}
        all_fields: dict[str, dict[str, str]] = {}

        # Pass 1: Discover connected TypeScript/JavaScript files and collect symbols
        while queue:
            file_path, depth = queue.pop(0)
            if file_path in self.visited_files:
                continue
            if not file_path.exists() or not file_path.is_file():
                continue

            self.visited_files.add(file_path)
            source_code = file_path.read_text(encoding="utf-8")
            is_tsx = file_path.suffix.lower() in (".tsx", ".jsx")
            collected_sources[file_path] = (source_code, is_tsx)

            parser = TypeScriptParser(is_tsx=is_tsx)
            cls_set, m_dict, f_dict = parser.collect_symbols(source_code)
            all_classes.update(cls_set)
            for c, m in m_dict.items():
                all_methods.setdefault(c, set()).update(m)
            for c, f in f_dict.items():
                all_fields.setdefault(c, {}).update(f)

            if depth < max_depth:
                imports = parser.extract_imports(source_code)
                for imp_uri in imports:
                    resolved = resolver.resolve_ts_import(file_path, imp_uri)
                    if resolved and resolved not in self.visited_files:
                        queue.append((resolved, depth + 1))

        # Pass 2: Parse each file with full cross-file symbol knowledge
        for file_path, (src, is_tsx) in collected_sources.items():
            mod_name = get_module_name(file_path, self.project_root)
            parser = TypeScriptParser(is_tsx=is_tsx)
            file_graph = parser.parse(
                source_code=src,
                module_name=mod_name,
                include_bodies=False,
                global_classes=all_classes,
                global_class_methods=all_methods,
                global_class_fields=all_fields,
            )
            for triple in file_graph:
                self.graph.add(triple)

        return self.graph


def parse_project_file(
    file_path: str | Path,
    project_root: str | Path | None = None,
) -> rdflib.Graph:
    """Convenience function to parse a file and its project dependencies into an RDF graph."""
    project = ProjectGraph(project_root=project_root)
    return project.parse_project_for_file(file_path)
