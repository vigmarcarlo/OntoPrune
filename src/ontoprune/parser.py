"""
AST to RDF Graph Parser Engine for OntoPrune.

Transforms Python source code into an in-memory RDF knowledge graph
using the software.ttl vocabulary with high performance.
"""

from __future__ import annotations

import ast
from pathlib import Path
from urllib.parse import quote

import rdflib
from rdflib import RDF, RDFS, Namespace, URIRef
from rdflib.term import Literal

SOFT = Namespace("https://w3id.org/ontoprune/software#")
REPO = Namespace("https://w3id.org/ontoprune/repo/")

# Python built-in functions to ignore during invocation mapping
BUILTIN_FUNCTIONS: set[str] = {
    "print",
    "len",
    "range",
    "str",
    "int",
    "float",
    "bool",
    "dict",
    "list",
    "set",
    "tuple",
    "sum",
    "min",
    "max",
    "isinstance",
    "issubclass",
    "hasattr",
    "getattr",
    "setattr",
    "delattr",
    "enumerate",
    "zip",
    "map",
    "filter",
    "any",
    "all",
    "repr",
    "iter",
    "next",
    "super",
    "round",
    "abs",
    "id",
}


def sanitize_id(identifier: str) -> str:
    """Sanitize identifier for URI compatibility."""
    return quote(identifier, safe="")


class SymbolCollector(ast.NodeVisitor):
    """
    First pass: indexes classes, methods, functions, inheritance,
    and instance attribute types from __init__.
    """

    def __init__(self, module_name: str = "main") -> None:
        self.module_name = module_name
        self.classes: set[str] = set()
        self.functions: set[str] = set()  # Module-level functions
        self.methods: dict[str, set[str]] = {}  # class_name -> set of method_names
        self.inheritance: dict[str, list[str]] = {}  # class_name -> list of base class names
        self.attr_types: dict[str, dict[str, str]] = {}  # class_name -> {attr_name: type_name}
        self.current_class: str | None = None
        self.all_class_methods: dict[
            str, dict[str, str]
        ] = {}  # class -> {method_name: declaring_class}

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        cls_name = node.name
        self.classes.add(cls_name)
        self.methods[cls_name] = set()
        self.inheritance[cls_name] = []
        self.attr_types[cls_name] = {}

        for base in node.bases:
            if isinstance(base, ast.Name):
                self.inheritance[cls_name].append(base.id)
            elif isinstance(base, ast.Subscript) and isinstance(base.value, ast.Name):
                self.inheritance[cls_name].append(base.value.id)

        prev_class = self.current_class
        self.current_class = cls_name
        self.generic_visit(node)
        self.current_class = prev_class

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._record_func(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._record_func(node)

    def _record_func(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        func_name = node.name
        if self.current_class is not None:
            self.methods[self.current_class].add(func_name)
            if func_name == "__init__":
                self._inspect_init_attributes(node)
        else:
            self.functions.add(func_name)
        self.generic_visit(node)

    def _inspect_init_attributes(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        assert self.current_class is not None
        cls_name = self.current_class

        arg_types: dict[str, str] = {}
        for arg in node.args.args:
            if arg.annotation:
                try:
                    arg_types[arg.arg] = ast.unparse(arg.annotation)
                except Exception:
                    pass

        for stmt in node.body:
            if isinstance(stmt, ast.Assign):
                for target in stmt.targets:
                    if (
                        isinstance(target, ast.Attribute)
                        and isinstance(target.value, ast.Name)
                        and target.value.id == "self"
                    ):
                        attr_name = target.attr
                        if isinstance(stmt.value, ast.Name) and stmt.value.id in arg_types:
                            self.attr_types[cls_name][attr_name] = arg_types[stmt.value.id]
            elif isinstance(stmt, ast.AnnAssign):
                if (
                    isinstance(stmt.target, ast.Attribute)
                    and isinstance(stmt.target.value, ast.Name)
                    and stmt.target.value.id == "self"
                ):
                    attr_name = stmt.target.attr
                    try:
                        self.attr_types[cls_name][attr_name] = ast.unparse(stmt.annotation)
                    except Exception:
                        pass

    def finalize(self) -> None:
        """Precompute method-to-declaring-class map for all classes including inheritance."""
        for cls in self.classes:
            mapping: dict[str, str] = {}
            # BFS inheritance
            queue = [cls]
            visited = set()
            while queue:
                c = queue.pop(0)
                if c in visited:
                    continue
                visited.add(c)
                for m in self.methods.get(c, set()):
                    if m not in mapping:
                        mapping[m] = c
                for base in self.inheritance.get(c, []):
                    if base not in visited:
                        queue.append(base)
            self.all_class_methods[cls] = mapping


class OntoVisitor(ast.NodeVisitor):
    """
    Second pass: populates RDF graph with modules, classes, functions,
    parameters, types, docstrings, and resolved invocations.
    """

    def __init__(
        self,
        source_code: str,
        symbols: SymbolCollector,
        module_name: str = "main",
        include_bodies: bool = False,
    ) -> None:
        self.source_code = source_code
        self.symbols = symbols
        self.module_name = module_name
        self.include_bodies = include_bodies
        self.graph = rdflib.Graph()

        # Bind standard prefixes
        self.graph.bind("soft", SOFT)
        self.graph.bind("repo", REPO)
        self.graph.bind("rdfs", RDFS)

        self.module_uri = REPO[f"module_{sanitize_id(module_name)}"]
        self.graph.add((self.module_uri, RDF.type, SOFT.Module))
        self.graph.add((self.module_uri, RDFS.label, Literal(module_name)))

        self.current_class: str | None = None
        self.current_func_uri: URIRef | None = None
        self.current_func_name: str | None = None

    def _get_func_uri(self, class_name: str | None, func_name: str) -> URIRef:
        if class_name:
            qualified = f"{class_name}.{func_name}"
        else:
            qualified = func_name
        return REPO[f"func_{sanitize_id(qualified)}"]

    def _get_param_uri(self, class_name: str | None, func_name: str, param_name: str) -> URIRef:
        if class_name:
            qualified = f"{class_name}.{func_name}_{param_name}"
        else:
            qualified = f"{func_name}_{param_name}"
        return REPO[f"param_{sanitize_id(qualified)}"]

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        cls_name = node.name
        cls_uri = REPO[f"class_{sanitize_id(cls_name)}"]

        self.graph.add((cls_uri, RDF.type, SOFT.Class))
        self.graph.add((cls_uri, RDFS.label, Literal(cls_name)))
        self.graph.add((self.module_uri, SOFT.containsClass, cls_uri))

        docstring = ast.get_docstring(node)
        if docstring:
            self.graph.add((cls_uri, RDFS.comment, Literal(docstring)))

        for base in node.bases:
            base_name = None
            if isinstance(base, ast.Name):
                base_name = base.id
            elif isinstance(base, ast.Subscript) and isinstance(base.value, ast.Name):
                base_name = base.value.id

            if base_name and base_name in self.symbols.classes:
                base_uri = REPO[f"class_{sanitize_id(base_name)}"]
                self.graph.add((cls_uri, SOFT.inheritsFrom, base_uri))

        prev_class = self.current_class
        self.current_class = cls_name
        self.generic_visit(node)
        self.current_class = prev_class

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._process_func(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._process_func(node)

    def _process_func(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        func_name = node.name
        cls_name = self.current_class
        func_uri = self._get_func_uri(cls_name, func_name)

        self.graph.add((func_uri, RDF.type, SOFT.Function))
        label = f"{cls_name}.{func_name}" if cls_name else func_name
        self.graph.add((func_uri, RDFS.label, Literal(label)))

        if cls_name:
            cls_uri = REPO[f"class_{sanitize_id(cls_name)}"]
            self.graph.add((cls_uri, SOFT.hasMethod, func_uri))
            self.graph.add((func_uri, SOFT.belongsToClass, Literal(cls_name)))
        else:
            self.graph.add((self.module_uri, SOFT.containsFunction, func_uri))

        docstring = ast.get_docstring(node)
        if docstring:
            self.graph.add((func_uri, RDFS.comment, Literal(docstring)))

        # Return type
        if node.returns:
            try:
                ret_str = ast.unparse(node.returns)
                self.graph.add((func_uri, SOFT.returnsType, Literal(ret_str)))
            except Exception:
                pass

        # Decorators
        for dec in node.decorator_list:
            try:
                dec_str = ast.unparse(dec)
                self.graph.add((func_uri, SOFT.decoratedWith, Literal(dec_str)))
            except Exception:
                pass

        # Optional source code of function body
        if self.include_bodies:
            try:
                func_source = ast.get_source_segment(self.source_code, node)
                if func_source:
                    self.graph.add((func_uri, SOFT.sourceBody, Literal(func_source)))
            except Exception:
                pass

        # Parameters
        all_args: list[tuple[ast.arg, ast.expr | None]] = []
        defaults = [None] * (len(node.args.args) - len(node.args.defaults)) + list(
            node.args.defaults
        )
        for arg, default in zip(node.args.args, defaults):
            all_args.append((arg, default))

        if node.args.vararg:
            all_args.append((node.args.vararg, None))

        kw_defaults = list(node.args.kw_defaults)
        for arg, default in zip(node.args.kwonlyargs, kw_defaults):
            all_args.append((arg, default))

        if node.args.kwarg:
            all_args.append((node.args.kwarg, None))

        for arg, default_node in all_args:
            param_name = arg.arg
            if cls_name and param_name == "self":
                continue

            param_uri = self._get_param_uri(cls_name, func_name, param_name)
            self.graph.add((param_uri, RDF.type, SOFT.Parameter))
            self.graph.add((param_uri, RDFS.label, Literal(param_name)))
            self.graph.add((func_uri, SOFT.hasParameter, param_uri))

            if arg.annotation:
                try:
                    type_str = ast.unparse(arg.annotation)
                    self.graph.add((param_uri, SOFT.hasType, Literal(type_str)))
                except Exception:
                    pass

            if default_node:
                try:
                    default_str = ast.unparse(default_node)
                    self.graph.add((param_uri, SOFT.hasDefault, Literal(default_str)))
                except Exception:
                    pass

        prev_func_uri = self.current_func_uri
        prev_func_name = self.current_func_name
        self.current_func_uri = func_uri
        self.current_func_name = func_name

        self.generic_visit(node)

        self.current_func_uri = prev_func_uri
        self.current_func_name = prev_func_name

    def visit_Call(self, node: ast.Call) -> None:
        if self.current_func_uri is not None:
            callee_uri = self._resolve_callee(node)
            if callee_uri:
                self.graph.add((self.current_func_uri, SOFT.invokes, callee_uri))
        self.generic_visit(node)

    def _resolve_callee(self, call_node: ast.Call) -> URIRef | None:
        func_expr = call_node.func

        # Case 1: direct name call: foo()
        if isinstance(func_expr, ast.Name):
            callee_name = func_expr.id
            if callee_name in BUILTIN_FUNCTIONS:
                return None
            if callee_name in self.symbols.functions:
                return self._get_func_uri(None, callee_name)
            if callee_name in self.symbols.classes:
                return self._get_func_uri(callee_name, "__init__")

        # Case 2: attribute call: self.method() or self.repo.save() or obj.method()
        elif isinstance(func_expr, ast.Attribute):
            method_name = func_expr.attr
            if (
                method_name.startswith("__")
                and method_name.endswith("__")
                and method_name != "__init__"
            ):
                return None

            value = func_expr.value

            # self.method(...)
            if isinstance(value, ast.Name) and value.id == "self":
                if self.current_class:
                    target_cls = self.symbols.all_class_methods.get(self.current_class, {}).get(
                        method_name
                    )
                    return self._get_func_uri(target_cls or self.current_class, method_name)

            # self.service.method(...)
            elif (
                isinstance(value, ast.Attribute)
                and isinstance(value.value, ast.Name)
                and value.value.id == "self"
            ):
                attr_name = value.attr
                if self.current_class:
                    attr_type = self.symbols.attr_types.get(self.current_class, {}).get(attr_name)
                    if attr_type and attr_type in self.symbols.classes:
                        target_cls = self.symbols.all_class_methods.get(attr_type, {}).get(
                            method_name
                        )
                        return self._get_func_uri(target_cls or attr_type, method_name)

            # Ambiguous or generic object call: check if unique method across all classes
            matching_classes = [c for c, m in self.symbols.methods.items() if method_name in m]
            if len(matching_classes) == 1:
                return self._get_func_uri(matching_classes[0], method_name)

        return None


def parse_source(
    source_code: str,
    module_name: str = "main",
    include_bodies: bool = False,
) -> rdflib.Graph:
    """Parse Python source code into an RDF graph."""
    tree = ast.parse(source_code)
    collector = SymbolCollector(module_name=module_name)
    collector.visit(tree)
    collector.finalize()

    visitor = OntoVisitor(
        source_code=source_code,
        symbols=collector,
        module_name=module_name,
        include_bodies=include_bodies,
    )
    visitor.visit(tree)
    return visitor.graph


def parse_file(
    file_path: str | Path,
    module_name: str | None = None,
    include_bodies: bool = False,
) -> rdflib.Graph:
    """Read a Python file and parse it into an RDF graph."""
    path = Path(file_path)
    if module_name is None:
        module_name = path.stem
    source_code = path.read_text(encoding="utf-8")
    return parse_source(source_code, module_name=module_name, include_bodies=include_bodies)
