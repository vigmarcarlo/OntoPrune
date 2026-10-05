"""
Tree-Sitter Based AST to RDF Graph Parser for OntoPrune.

Supports Dart/Flutter, Java, and TypeScript/JavaScript using high-speed
tree-sitter native grammars, emitting software.ttl RDF knowledge graphs.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

import rdflib
from rdflib import RDF, RDFS, Namespace
from rdflib.term import Literal

SOFT = Namespace("https://w3id.org/ontoprune/software#")
REPO = Namespace("https://w3id.org/ontoprune/repo/")


def sanitize_id(identifier: str) -> str:
    """Sanitize identifier for URI compatibility."""
    return quote(identifier, safe="")


class TreeSitterParserEngine:
    """Base parser engine leveraging Tree-Sitter grammars."""

    def __init__(self, language_name: str) -> None:
        self.language_name = language_name
        self._init_language()

    def _init_language(self) -> None:
        try:
            import tree_sitter
        except ImportError as exc:
            raise ImportError(
                "tree-sitter is required for multi-language support. "
                "Install it with: pip install 'ontoprune[languages]'"
            ) from exc

        if self.language_name == "dart":
            import tree_sitter_dart

            self.language = tree_sitter.Language(tree_sitter_dart.language())
        elif self.language_name == "java":
            import tree_sitter_java

            self.language = tree_sitter.Language(tree_sitter_java.language())
        elif self.language_name in ("typescript", "ts", "javascript", "js"):
            import tree_sitter_typescript

            self.language = tree_sitter.Language(tree_sitter_typescript.language_typescript())
        elif self.language_name == "tsx":
            import tree_sitter_typescript

            self.language = tree_sitter.Language(tree_sitter_typescript.language_tsx())
        else:
            raise ValueError(f"Unsupported language: {self.language_name}")

        self.parser = tree_sitter.Parser(self.language)


# ---------------------------------------------------------------------------
# Dart / Flutter Parser
# ---------------------------------------------------------------------------


class DartParser(TreeSitterParserEngine):
    """Parser for Dart and Flutter codebases."""

    def __init__(self) -> None:
        super().__init__("dart")

    def extract_imports(self, source_code: str) -> list[str]:
        """Extract import URIs from Dart source code."""
        code_bytes = source_code.encode("utf-8")
        tree = self.parser.parse(code_bytes)
        uris: list[str] = []
        for node in tree.root_node.children:
            if node.type == "import_or_export":
                for c in node.children:
                    if c.type == "library_import":
                        for spec in c.children:
                            if spec.type == "import_specification":
                                for curi in spec.children:
                                    if curi.type == "configurable_uri":
                                        raw = curi.text.decode("utf-8").strip("\"'")
                                        uris.append(raw)
        return uris

    def collect_symbols(
        self, source_code: str
    ) -> tuple[set[str], dict[str, set[str]], dict[str, dict[str, str]]]:
        """Collect classes, methods, and field types from Dart source code."""
        code_bytes = source_code.encode("utf-8")
        tree = self.parser.parse(code_bytes)
        classes: set[str] = set()
        class_methods: dict[str, set[str]] = {}
        class_fields: dict[str, dict[str, str]] = {}

        for node in tree.root_node.children:
            if node.type == "class_definition":
                cls_name = None
                for child in node.children:
                    if child.type == "identifier":
                        cls_name = child.text.decode("utf-8")
                        break
                if not cls_name:
                    continue

                classes.add(cls_name)
                class_methods[cls_name] = set()
                class_fields[cls_name] = {}

                body = None
                for child in node.children:
                    if child.type == "class_body":
                        body = child
                        break
                if not body:
                    continue

                for member in body.children:
                    if member.type == "declaration":
                        type_str = None
                        field_name = None
                        for c in member.children:
                            if c.type in ("type_identifier", "identifier"):
                                if type_str is None and c.text.decode("utf-8") not in (
                                    "final",
                                    "var",
                                    "const",
                                ):
                                    type_str = c.text.decode("utf-8")
                            elif c.type == "initialized_identifier_list":
                                for id_node in c.children:
                                    if id_node.type in ("initialized_identifier", "identifier"):
                                        field_name = (
                                            id_node.text.decode("utf-8").split("=")[0].strip()
                                        )
                            elif c.type == "function_signature":
                                for fc in c.children:
                                    if fc.type == "identifier":
                                        class_methods[cls_name].add(fc.text.decode("utf-8"))
                        if field_name and type_str:
                            class_fields[cls_name][field_name] = type_str

                    elif member.type == "method_signature":
                        for sig_child in member.children:
                            if sig_child.type in ("function_signature", "getter_signature"):
                                for fc in sig_child.children:
                                    if fc.type == "identifier":
                                        class_methods[cls_name].add(fc.text.decode("utf-8"))

        return classes, class_methods, class_fields

    def parse(
        self,
        source_code: str,
        module_name: str = "main",
        include_bodies: bool = False,
        global_classes: set[str] | None = None,
        global_class_methods: dict[str, set[str]] | None = None,
        global_class_fields: dict[str, dict[str, str]] | None = None,
    ) -> rdflib.Graph:
        code_bytes = source_code.encode("utf-8")
        tree = self.parser.parse(code_bytes)

        graph = rdflib.Graph()
        graph.bind("soft", SOFT)
        graph.bind("repo", REPO)
        graph.bind("rdfs", RDFS)

        mod_uri = REPO[f"mod_{sanitize_id(module_name)}"]
        graph.add((mod_uri, RDF.type, SOFT.Module))
        graph.add((mod_uri, RDFS.label, Literal(module_name)))
        graph.add((mod_uri, SOFT.language, Literal("dart")))

        # Symbol Tables
        classes: set[str] = set()
        class_methods: dict[str, set[str]] = {}
        class_fields: dict[str, dict[str, str]] = {}  # cls -> {field: type}
        methods_meta: list[dict[str, Any]] = []

        # Pass 1: Collect classes and fields
        for node in tree.root_node.children:
            if node.type == "class_definition":
                cls_name = None
                for child in node.children:
                    if child.type == "identifier":
                        cls_name = child.text.decode("utf-8")
                        break

                if not cls_name:
                    continue

                classes.add(cls_name)
                class_methods[cls_name] = set()
                class_fields[cls_name] = {}

                # Inspect class_body
                body = None
                for child in node.children:
                    if child.type == "class_body":
                        body = child
                        break
                if not body:
                    continue

                for member in body.children:
                    # Field declaration: final Type field;
                    if member.type == "declaration":
                        type_str = None
                        field_name = None
                        for c in member.children:
                            if c.type in ("type_identifier", "identifier"):
                                if type_str is None and c.text.decode("utf-8") not in (
                                    "final",
                                    "var",
                                    "const",
                                ):
                                    type_str = c.text.decode("utf-8")
                            elif c.type == "initialized_identifier_list":
                                for id_node in c.children:
                                    if id_node.type in ("initialized_identifier", "identifier"):
                                        field_name = (
                                            id_node.text.decode("utf-8").split("=")[0].strip()
                                        )

                        if field_name and type_str:
                            class_fields[cls_name][field_name] = type_str

        # Pass 2: Collect methods and invocations
        for node in tree.root_node.children:
            if node.type == "class_definition":
                cls_name = None
                for child in node.children:
                    if child.type == "identifier":
                        cls_name = child.text.decode("utf-8")
                        break
                if not cls_name:
                    continue

                cls_uri = REPO[f"cls_{sanitize_id(cls_name)}"]
                graph.add((cls_uri, RDF.type, SOFT.Class))
                graph.add((cls_uri, RDFS.label, Literal(cls_name)))
                graph.add((cls_uri, SOFT.belongsToModule, mod_uri))

                body = None
                for child in node.children:
                    if child.type == "class_body":
                        body = child
                        break
                if not body:
                    continue

                # Find methods: method_signature followed by function_body
                idx = 0
                while idx < len(body.children):
                    member = body.children[idx]
                    method_name = None
                    ret_type = "void"
                    params: list[tuple[str, str | None]] = []
                    body_node = None

                    def _extract_param(p_node: Any) -> tuple[str | None, str | None]:
                        pt = None
                        pn = None
                        for pc in p_node.children:
                            if pc.type in ("type_identifier", "identifier"):
                                if pt is None:
                                    pt = pc.text.decode("utf-8")
                                else:
                                    pn = pc.text.decode("utf-8")
                        if pn is None and pt:
                            pn = pt
                            pt = None
                        return pt, pn

                    def _extract_sig(
                        sig_node: Any,
                    ) -> tuple[str | None, str, list[tuple[str, str | None]]]:
                        m_name = None
                        r_type = "void"
                        p_list: list[tuple[str, str | None]] = []
                        for fc in sig_node.children:
                            if fc.type == "type_identifier":
                                r_type = fc.text.decode("utf-8")
                            elif fc.type == "type_arguments":
                                r_type += fc.text.decode("utf-8")
                            elif fc.type == "identifier":
                                m_name = fc.text.decode("utf-8")
                            elif fc.type == "getter_signature":
                                for gc in fc.children:
                                    if gc.type == "type_identifier":
                                        r_type = gc.text.decode("utf-8")
                                    elif gc.type == "identifier":
                                        m_name = gc.text.decode("utf-8")
                            elif fc.type == "formal_parameter_list":
                                for p in fc.children:
                                    if p.type == "formal_parameter":
                                        pt, pn = _extract_param(p)
                                        if pn:
                                            p_list.append((pn, pt))
                                    elif p.type == "optional_formal_parameters":
                                        for op in p.children:
                                            if op.type == "formal_parameter":
                                                pt, pn = _extract_param(op)
                                                if pn:
                                                    p_list.append((pn, pt))
                        return m_name, r_type, p_list

                    if member.type == "method_signature":
                        for sig_child in member.children:
                            if sig_child.type in ("function_signature", "getter_signature"):
                                method_name, ret_type, params = _extract_sig(
                                    sig_child if sig_child.type == "function_signature" else member
                                )

                        if (
                            idx + 1 < len(body.children)
                            and body.children[idx + 1].type == "function_body"
                        ):
                            body_node = body.children[idx + 1]

                    elif member.type == "declaration":
                        for sig_child in member.children:
                            if sig_child.type == "function_signature":
                                method_name, ret_type, params = _extract_sig(sig_child)

                    if method_name:
                        class_methods[cls_name].add(method_name)
                        methods_meta.append(
                            {
                                "class": cls_name,
                                "name": method_name,
                                "return_type": ret_type,
                                "params": params,
                                "body_node": body_node,
                                "source_code": body_node.text.decode("utf-8") if body_node else "",
                            }
                        )

                    idx += 1

        # Build RDF Graph for all methods and resolve invocations
        for meta in methods_meta:
            cls_name = meta["class"]
            method_name = meta["name"]
            func_uri = REPO[f"func_{sanitize_id(cls_name)}.{sanitize_id(method_name)}"]
            cls_uri = REPO[f"cls_{sanitize_id(cls_name)}"]

            graph.add((func_uri, RDF.type, SOFT.Function))
            graph.add((func_uri, RDFS.label, Literal(method_name)))
            graph.add((func_uri, SOFT.belongsToClass, Literal(cls_name)))
            graph.add((func_uri, SOFT.definedInClass, cls_uri))
            graph.add((func_uri, SOFT.belongsToModule, mod_uri))
            graph.add((func_uri, SOFT.returnsType, Literal(meta["return_type"])))
            graph.add((func_uri, SOFT.language, Literal("dart")))

            if include_bodies and meta["source_code"]:
                graph.add((func_uri, SOFT.sourceBody, Literal(meta["source_code"])))

            # Parameters
            for p_name, p_type in meta["params"]:
                p_uri = REPO[
                    f"param_{sanitize_id(cls_name)}_{sanitize_id(method_name)}_{sanitize_id(p_name)}"
                ]
                graph.add((p_uri, RDF.type, SOFT.Parameter))
                graph.add((p_uri, RDFS.label, Literal(p_name)))
                if p_type:
                    graph.add((p_uri, SOFT.hasType, Literal(p_type)))
                graph.add((func_uri, SOFT.hasParameter, p_uri))

            # Invocations inside body
            body_node = meta["body_node"]
            if body_node:
                eff_fields = dict(class_fields)
                if global_class_fields:
                    for gc, gf in global_class_fields.items():
                        eff_fields.setdefault(gc, {}).update(gf)

                eff_methods = dict(class_methods)
                if global_class_methods:
                    for gc, gm in global_class_methods.items():
                        eff_methods.setdefault(gc, set()).update(gm)

                invocations = self._extract_dart_calls(body_node, cls_name, eff_fields, eff_methods)
                for invoked_cls, invoked_method in invocations:
                    target_func_uri = REPO[
                        f"func_{sanitize_id(invoked_cls)}.{sanitize_id(invoked_method)}"
                    ]
                    graph.add((func_uri, SOFT.invokes, target_func_uri))

        return graph

    def _extract_dart_calls(
        self,
        node: Any,
        current_cls: str,
        class_fields: dict[str, dict[str, str]],
        class_methods: dict[str, set[str]],
    ) -> set[tuple[str, str]]:
        """Extract method invocations from Dart AST node."""
        calls: set[tuple[str, str]] = set()

        def visit(n: Any) -> None:
            # Check for selector chained with argument_part
            # e.g.: inventory.reservarStock(items)
            for i, child in enumerate(n.children):
                if child.type == "selector":
                    # Check if next child is argument_part selector
                    method_name = None
                    for sc in child.children:
                        if sc.type == "unconditional_assignable_selector":
                            for id_c in sc.children:
                                if id_c.type == "identifier":
                                    method_name = id_c.text.decode("utf-8")

                    if method_name:
                        # Find object identifier preceding this selector
                        obj_name = None
                        if i > 0:
                            prev = n.children[i - 1]
                            if prev.type == "identifier":
                                obj_name = prev.text.decode("utf-8")

                        # Resolve target class
                        target_cls = None
                        if obj_name:
                            target_cls = class_fields.get(current_cls, {}).get(obj_name)
                            if not target_cls and obj_name in class_methods:
                                target_cls = obj_name

                        if not target_cls:
                            # Check if unique method across all classes
                            matching = [c for c, m in class_methods.items() if method_name in m]
                            if len(matching) == 1:
                                target_cls = matching[0]

                        if target_cls:
                            calls.add((target_cls, method_name))

            for child in n.children:
                visit(child)

        visit(node)
        return calls


# ---------------------------------------------------------------------------
# Java Parser
# ---------------------------------------------------------------------------


class JavaParser(TreeSitterParserEngine):
    """Parser for Java (Spring Boot, Android, Enterprise) codebases."""

    def __init__(self) -> None:
        super().__init__("java")

    def extract_imports(self, source_code: str) -> list[str]:
        """Extract import paths from Java source code."""
        code_bytes = source_code.encode("utf-8")
        tree = self.parser.parse(code_bytes)
        imports: list[str] = []
        for node in tree.root_node.children:
            if node.type == "import_declaration":
                imp_str = ""
                for c in node.children:
                    if c.type in ("scoped_identifier", "identifier"):
                        imp_str = c.text.decode("utf-8")
                    elif c.type == "asterisk":
                        imp_str += ".*"
                if imp_str:
                    imports.append(imp_str)
        return imports

    def collect_symbols(
        self, source_code: str
    ) -> tuple[set[str], dict[str, set[str]], dict[str, dict[str, str]]]:
        """Collect classes, methods, and field types from Java source code."""
        code_bytes = source_code.encode("utf-8")
        tree = self.parser.parse(code_bytes)
        classes: set[str] = set()
        class_methods: dict[str, set[str]] = {}
        class_fields: dict[str, dict[str, str]] = {}

        for node in tree.root_node.children:
            if node.type in ("class_declaration", "interface_declaration", "record_declaration"):
                cls_name = None
                for child in node.children:
                    if child.type == "identifier":
                        cls_name = child.text.decode("utf-8")
                        break
                if not cls_name:
                    continue

                classes.add(cls_name)
                class_methods[cls_name] = set()
                class_fields[cls_name] = {}

                body = None
                for child in node.children:
                    if child.type in ("class_body", "interface_body"):
                        body = child
                        break
                if not body:
                    continue

                for member in body.children:
                    if member.type == "field_declaration":
                        type_str = None
                        field_name = None
                        for c in member.children:
                            if c.type in ("type_identifier", "generic_type"):
                                type_str = c.text.decode("utf-8")
                            elif c.type == "variable_declarator":
                                for vc in c.children:
                                    if vc.type == "identifier":
                                        field_name = vc.text.decode("utf-8")
                        if field_name and type_str:
                            class_fields[cls_name][field_name] = type_str
                    elif member.type == "method_declaration":
                        for c in member.children:
                            if c.type == "identifier":
                                class_methods[cls_name].add(c.text.decode("utf-8"))

        return classes, class_methods, class_fields

    def parse(
        self,
        source_code: str,
        module_name: str = "main",
        include_bodies: bool = False,
        global_classes: set[str] | None = None,
        global_class_methods: dict[str, set[str]] | None = None,
        global_class_fields: dict[str, dict[str, str]] | None = None,
    ) -> rdflib.Graph:
        code_bytes = source_code.encode("utf-8")
        tree = self.parser.parse(code_bytes)

        graph = rdflib.Graph()
        graph.bind("soft", SOFT)
        graph.bind("repo", REPO)
        graph.bind("rdfs", RDFS)

        mod_uri = REPO[f"mod_{sanitize_id(module_name)}"]
        graph.add((mod_uri, RDF.type, SOFT.Module))
        graph.add((mod_uri, RDFS.label, Literal(module_name)))
        graph.add((mod_uri, SOFT.language, Literal("java")))

        classes: set[str] = set()
        class_methods: dict[str, set[str]] = {}
        class_fields: dict[str, dict[str, str]] = {}
        methods_meta: list[dict[str, Any]] = []

        # Pass 1: Collect classes and fields
        for node in tree.root_node.children:
            if node.type in ("class_declaration", "interface_declaration"):
                cls_name = None
                for child in node.children:
                    if child.type == "identifier":
                        cls_name = child.text.decode("utf-8")
                        break
                if not cls_name:
                    continue

                classes.add(cls_name)
                class_methods[cls_name] = set()
                class_fields[cls_name] = {}

                body = None
                for child in node.children:
                    if child.type in ("class_body", "interface_body"):
                        body = child
                        break
                if not body:
                    continue

                for member in body.children:
                    if member.type == "field_declaration":
                        type_str = None
                        field_name = None
                        for c in member.children:
                            if c.type in ("type_identifier", "generic_type"):
                                type_str = c.text.decode("utf-8")
                            elif c.type == "variable_declarator":
                                for vc in c.children:
                                    if vc.type == "identifier":
                                        field_name = vc.text.decode("utf-8")
                        if field_name and type_str:
                            class_fields[cls_name][field_name] = type_str

        # Pass 2: Collect methods
        for node in tree.root_node.children:
            if node.type in ("class_declaration", "interface_declaration"):
                cls_name = None
                for child in node.children:
                    if child.type == "identifier":
                        cls_name = child.text.decode("utf-8")
                        break
                if not cls_name:
                    continue

                cls_uri = REPO[f"cls_{sanitize_id(cls_name)}"]
                graph.add((cls_uri, RDF.type, SOFT.Class))
                graph.add((cls_uri, RDFS.label, Literal(cls_name)))
                graph.add((cls_uri, SOFT.belongsToModule, mod_uri))

                body = None
                for child in node.children:
                    if child.type in ("class_body", "interface_body"):
                        body = child
                        break
                if not body:
                    continue

                for member in body.children:
                    if member.type == "method_declaration":
                        method_name = None
                        ret_type = "void"
                        params: list[tuple[str, str | None]] = []
                        body_node = None

                        for c in member.children:
                            if c.type in (
                                "type_identifier",
                                "generic_type",
                                "boolean_type",
                                "integral_type",
                                "floating_point_type",
                                "void_type",
                            ):
                                ret_type = c.text.decode("utf-8")
                            elif c.type == "identifier":
                                method_name = c.text.decode("utf-8")
                            elif c.type == "formal_parameters":
                                for p in c.children:
                                    if p.type == "formal_parameter":
                                        p_type = None
                                        p_name = None
                                        for pc in p.children:
                                            if pc.type in (
                                                "type_identifier",
                                                "generic_type",
                                                "boolean_type",
                                            ):
                                                p_type = pc.text.decode("utf-8")
                                            elif pc.type == "identifier":
                                                p_name = pc.text.decode("utf-8")
                                        if p_name:
                                            params.append((p_name, p_type))
                            elif c.type == "block":
                                body_node = c

                        if method_name:
                            class_methods[cls_name].add(method_name)
                            methods_meta.append(
                                {
                                    "class": cls_name,
                                    "name": method_name,
                                    "return_type": ret_type,
                                    "params": params,
                                    "body_node": body_node,
                                    "source_code": member.text.decode("utf-8"),
                                }
                            )

        # Build RDF Graph for all methods and resolve invocations
        for meta in methods_meta:
            cls_name = meta["class"]
            method_name = meta["name"]
            func_uri = REPO[f"func_{sanitize_id(cls_name)}.{sanitize_id(method_name)}"]
            cls_uri = REPO[f"cls_{sanitize_id(cls_name)}"]

            graph.add((func_uri, RDF.type, SOFT.Function))
            graph.add((func_uri, RDFS.label, Literal(method_name)))
            graph.add((func_uri, SOFT.belongsToClass, Literal(cls_name)))
            graph.add((func_uri, SOFT.definedInClass, cls_uri))
            graph.add((func_uri, SOFT.belongsToModule, mod_uri))
            graph.add((func_uri, SOFT.returnsType, Literal(meta["return_type"])))
            graph.add((func_uri, SOFT.language, Literal("java")))

            if include_bodies and meta["source_code"]:
                graph.add((func_uri, SOFT.sourceBody, Literal(meta["source_code"])))

            for p_name, p_type in meta["params"]:
                p_uri = REPO[
                    f"param_{sanitize_id(cls_name)}_{sanitize_id(method_name)}_{sanitize_id(p_name)}"
                ]
                graph.add((p_uri, RDF.type, SOFT.Parameter))
                graph.add((p_uri, RDFS.label, Literal(p_name)))
                if p_type:
                    graph.add((p_uri, SOFT.hasType, Literal(p_type)))
                graph.add((func_uri, SOFT.hasParameter, p_uri))

            body_node = meta["body_node"]
            if body_node:
                eff_fields = dict(class_fields)
                if global_class_fields:
                    for gc, gf in global_class_fields.items():
                        eff_fields.setdefault(gc, {}).update(gf)

                eff_methods = dict(class_methods)
                if global_class_methods:
                    for gc, gm in global_class_methods.items():
                        eff_methods.setdefault(gc, set()).update(gm)

                invocations = self._extract_java_calls(body_node, cls_name, eff_fields, eff_methods)
                for invoked_cls, invoked_method in invocations:
                    target_func_uri = REPO[
                        f"func_{sanitize_id(invoked_cls)}.{sanitize_id(invoked_method)}"
                    ]
                    graph.add((func_uri, SOFT.invokes, target_func_uri))

        return graph

    def _extract_java_calls(
        self,
        node: Any,
        current_cls: str,
        class_fields: dict[str, dict[str, str]],
        class_methods: dict[str, set[str]],
    ) -> set[tuple[str, str]]:
        """Extract method invocations from Java AST node."""
        calls: set[tuple[str, str]] = set()

        def visit(n: Any) -> None:
            if n.type == "method_invocation":
                obj_name = None
                method_name = None
                has_this = False

                for c in n.children:
                    if c.type == "this":
                        has_this = True
                    elif c.type == "identifier":
                        if obj_name is None:
                            obj_name = c.text.decode("utf-8")
                        else:
                            method_name = c.text.decode("utf-8")

                if has_this and obj_name:
                    # this.method()
                    calls.add((current_cls, obj_name))
                elif obj_name and method_name:
                    # obj.method()
                    target_cls = class_fields.get(current_cls, {}).get(obj_name)
                    if not target_cls:
                        if obj_name in class_methods:
                            target_cls = obj_name
                        else:
                            matching = [c for c, m in class_methods.items() if method_name in m]
                            if len(matching) == 1:
                                target_cls = matching[0]

                    if target_cls:
                        calls.add((target_cls, method_name))
                elif obj_name and not method_name:
                    # direct method() call
                    target_cls = (
                        current_cls if obj_name in class_methods.get(current_cls, set()) else None
                    )
                    if not target_cls:
                        matching = [c for c, m in class_methods.items() if obj_name in m]
                        if len(matching) == 1:
                            target_cls = matching[0]
                    if target_cls:
                        calls.add((target_cls, obj_name))

            for child in n.children:
                visit(child)

        visit(node)
        return calls


# ---------------------------------------------------------------------------
# TypeScript / JavaScript Parser
# ---------------------------------------------------------------------------


class TypeScriptParser(TreeSitterParserEngine):
    """Parser for TypeScript and JavaScript codebases."""

    def __init__(self, is_tsx: bool = False) -> None:
        super().__init__("tsx" if is_tsx else "typescript")

    def extract_imports(self, source_code: str) -> list[str]:
        """Extract import URIs from TypeScript/JavaScript source code."""
        code_bytes = source_code.encode("utf-8")
        tree = self.parser.parse(code_bytes)
        uris: list[str] = []
        for node in tree.root_node.children:
            if node.type == "import_statement":
                for c in node.children:
                    if c.type == "string":
                        raw = c.text.decode("utf-8").strip("\"'")
                        uris.append(raw)
        return uris

    def collect_symbols(
        self, source_code: str
    ) -> tuple[set[str], dict[str, set[str]], dict[str, dict[str, str]]]:
        """Collect classes, interfaces, methods, and field types from TypeScript/JavaScript source code."""
        code_bytes = source_code.encode("utf-8")
        tree = self.parser.parse(code_bytes)
        classes: set[str] = set()
        class_methods: dict[str, set[str]] = {}
        class_fields: dict[str, dict[str, str]] = {}

        def find_symbols(node: Any) -> None:
            for child in node.children:
                if child.type in ("class_declaration", "interface_declaration"):
                    name = None
                    for c in child.children:
                        if c.type in ("type_identifier", "identifier"):
                            name = c.text.decode("utf-8")
                            break
                    if name:
                        classes.add(name)
                        class_methods[name] = set()
                        class_fields[name] = {}
                        body = child.child_by_field_name("body")
                        if body:
                            for member in body.children:
                                if member.type == "method_signature":
                                    for mc in member.children:
                                        if mc.type == "property_identifier":
                                            class_methods[name].add(mc.text.decode("utf-8"))
                                elif member.type == "method_definition":
                                    m_name = None
                                    for mc in member.children:
                                        if mc.type == "property_identifier":
                                            m_name = mc.text.decode("utf-8")
                                            if m_name != "constructor":
                                                class_methods[name].add(m_name)
                                        elif (
                                            mc.type == "formal_parameters"
                                            and m_name == "constructor"
                                        ):
                                            for p in mc.children:
                                                if p.type in (
                                                    "required_parameter",
                                                    "optional_parameter",
                                                ):
                                                    f_name, f_type, has_mod = None, None, False
                                                    for pc in p.children:
                                                        if pc.type == "accessibility_modifier":
                                                            has_mod = True
                                                        elif pc.type == "identifier":
                                                            f_name = pc.text.decode("utf-8")
                                                        elif pc.type == "type_annotation":
                                                            f_type = (
                                                                pc.text.decode("utf-8")
                                                                .lstrip(":")
                                                                .strip()
                                                            )
                                                    if f_name and f_type and has_mod:
                                                        class_fields[name][f_name] = f_type
                                elif member.type in (
                                    "public_field_definition",
                                    "property_definition",
                                    "field_definition",
                                ):
                                    f_name = None
                                    f_type = None
                                    for mc in member.children:
                                        if mc.type == "property_identifier":
                                            f_name = mc.text.decode("utf-8")
                                        elif mc.type == "type_annotation":
                                            f_type = mc.text.decode("utf-8").lstrip(":").strip()
                                    if f_name and f_type:
                                        class_fields[name][f_name] = f_type
                elif child.type == "export_statement":
                    find_symbols(child)

        find_symbols(tree.root_node)
        return classes, class_methods, class_fields

    def parse(
        self,
        source_code: str,
        module_name: str = "main",
        include_bodies: bool = False,
        global_classes: set[str] | None = None,
        global_class_methods: dict[str, set[str]] | None = None,
        global_class_fields: dict[str, dict[str, str]] | None = None,
    ) -> rdflib.Graph:
        code_bytes = source_code.encode("utf-8")
        tree = self.parser.parse(code_bytes)

        graph = rdflib.Graph()
        graph.bind("soft", SOFT)
        graph.bind("repo", REPO)
        graph.bind("rdfs", RDFS)

        mod_uri = REPO[f"mod_{sanitize_id(module_name)}"]
        graph.add((mod_uri, RDF.type, SOFT.Module))
        graph.add((mod_uri, RDFS.label, Literal(module_name)))
        graph.add((mod_uri, SOFT.language, Literal("typescript")))

        classes: set[str] = set()
        class_methods: dict[str, set[str]] = {}
        class_fields: dict[str, dict[str, str]] = {}
        methods_meta: list[dict[str, Any]] = []

        def find_classes(node: Any) -> None:
            for child in node.children:
                if child.type in ("class_declaration", "interface_declaration"):
                    cls_name = None
                    for c in child.children:
                        if c.type in ("type_identifier", "identifier"):
                            cls_name = c.text.decode("utf-8")
                            break
                    if cls_name:
                        classes.add(cls_name)
                        class_methods[cls_name] = set()
                        class_fields[cls_name] = {}

                        body = child.child_by_field_name("body")
                        if body:
                            for member in body.children:
                                if member.type in (
                                    "public_field_definition",
                                    "property_definition",
                                    "field_definition",
                                ):
                                    f_name = None
                                    f_type = None
                                    for mc in member.children:
                                        if mc.type == "property_identifier":
                                            f_name = mc.text.decode("utf-8")
                                        elif mc.type == "type_annotation":
                                            f_type = mc.text.decode("utf-8").lstrip(":").strip()
                                    if f_name and f_type:
                                        class_fields[cls_name][f_name] = f_type
                                elif member.type == "method_definition":
                                    m_name = None
                                    for mc in member.children:
                                        if mc.type == "property_identifier":
                                            m_name = mc.text.decode("utf-8")
                                        elif (
                                            mc.type == "formal_parameters"
                                            and m_name == "constructor"
                                        ):
                                            for p in mc.children:
                                                if p.type in (
                                                    "required_parameter",
                                                    "optional_parameter",
                                                ):
                                                    p_f_name, p_f_type, has_mod = None, None, False
                                                    for pc in p.children:
                                                        if pc.type == "accessibility_modifier":
                                                            has_mod = True
                                                        elif pc.type == "identifier":
                                                            p_f_name = pc.text.decode("utf-8")
                                                        elif pc.type == "type_annotation":
                                                            p_f_type = (
                                                                pc.text.decode("utf-8")
                                                                .lstrip(":")
                                                                .strip()
                                                            )
                                                    if p_f_name and p_f_type and has_mod:
                                                        class_fields[cls_name][p_f_name] = p_f_type
                elif child.type == "export_statement":
                    find_classes(child)

        find_classes(tree.root_node)

        def extract_methods(node: Any) -> None:
            for child in node.children:
                if child.type in ("class_declaration", "interface_declaration"):
                    cls_name = None
                    for c in child.children:
                        if c.type in ("type_identifier", "identifier"):
                            cls_name = c.text.decode("utf-8")
                            break
                    if not cls_name:
                        continue

                    cls_uri = REPO[f"cls_{sanitize_id(cls_name)}"]
                    graph.add((cls_uri, RDF.type, SOFT.Class))
                    graph.add((cls_uri, RDFS.label, Literal(cls_name)))
                    graph.add((cls_uri, SOFT.belongsToModule, mod_uri))

                    body = child.child_by_field_name("body")
                    if not body:
                        continue

                    for member in body.children:
                        if member.type in ("method_definition", "method_signature"):
                            method_name = None
                            ret_type = "void"
                            params: list[tuple[str, str | None]] = []
                            body_node = None

                            for mc in member.children:
                                if mc.type == "property_identifier":
                                    method_name = mc.text.decode("utf-8")
                                elif mc.type == "type_annotation":
                                    ret_type = mc.text.decode("utf-8").lstrip(":").strip()
                                elif mc.type == "formal_parameters":
                                    for p in mc.children:
                                        if p.type in ("required_parameter", "optional_parameter"):
                                            p_name = None
                                            p_type = None
                                            for pc in p.children:
                                                if pc.type == "identifier":
                                                    p_name = pc.text.decode("utf-8")
                                                elif pc.type == "type_annotation":
                                                    p_type = (
                                                        pc.text.decode("utf-8").lstrip(":").strip()
                                                    )
                                            if p_name:
                                                params.append((p_name, p_type))
                                elif mc.type == "statement_block":
                                    body_node = mc

                            if method_name and method_name != "constructor":
                                class_methods[cls_name].add(method_name)
                                methods_meta.append(
                                    {
                                        "class": cls_name,
                                        "name": method_name,
                                        "return_type": ret_type,
                                        "params": params,
                                        "body_node": body_node,
                                        "source_code": member.text.decode("utf-8"),
                                    }
                                )
                elif child.type == "export_statement":
                    extract_methods(child)

        extract_methods(tree.root_node)

        # Build RDF Graph
        for meta in methods_meta:
            cls_name = meta["class"]
            method_name = meta["name"]
            func_uri = REPO[f"func_{sanitize_id(cls_name)}.{sanitize_id(method_name)}"]
            cls_uri = REPO[f"cls_{sanitize_id(cls_name)}"]

            graph.add((func_uri, RDF.type, SOFT.Function))
            graph.add((func_uri, RDFS.label, Literal(method_name)))
            graph.add((func_uri, SOFT.belongsToClass, Literal(cls_name)))
            graph.add((func_uri, SOFT.definedInClass, cls_uri))
            graph.add((func_uri, SOFT.belongsToModule, mod_uri))
            graph.add((func_uri, SOFT.returnsType, Literal(meta["return_type"])))
            graph.add((func_uri, SOFT.language, Literal("typescript")))

            if include_bodies and meta["source_code"]:
                graph.add((func_uri, SOFT.sourceBody, Literal(meta["source_code"])))

            for p_name, p_type in meta["params"]:
                p_uri = REPO[
                    f"param_{sanitize_id(cls_name)}_{sanitize_id(method_name)}_{sanitize_id(p_name)}"
                ]
                graph.add((p_uri, RDF.type, SOFT.Parameter))
                graph.add((p_uri, RDFS.label, Literal(p_name)))
                if p_type:
                    graph.add((p_uri, SOFT.hasType, Literal(p_type)))
                graph.add((func_uri, SOFT.hasParameter, p_uri))

            body_node = meta["body_node"]
            if body_node:
                eff_fields = dict(class_fields)
                if global_class_fields:
                    for gc, gf in global_class_fields.items():
                        eff_fields.setdefault(gc, {}).update(gf)

                eff_methods = dict(class_methods)
                if global_class_methods:
                    for gc, gm in global_class_methods.items():
                        eff_methods.setdefault(gc, set()).update(gm)

                invocations = self._extract_ts_calls(body_node, cls_name, eff_fields, eff_methods)
                for invoked_cls, invoked_method in invocations:
                    target_func_uri = REPO[
                        f"func_{sanitize_id(invoked_cls)}.{sanitize_id(invoked_method)}"
                    ]
                    graph.add((func_uri, SOFT.invokes, target_func_uri))

        return graph

    def _extract_ts_calls(
        self,
        node: Any,
        current_cls: str,
        class_fields: dict[str, dict[str, str]],
        class_methods: dict[str, set[str]],
    ) -> set[tuple[str, str]]:
        """Extract method invocations from TypeScript AST node."""
        calls: set[tuple[str, str]] = set()

        def visit(n: Any) -> None:
            if n.type == "call_expression":
                fn_node = n.child_by_field_name("function")
                if fn_node and fn_node.type == "member_expression":
                    prop = fn_node.child_by_field_name("property")
                    obj = fn_node.child_by_field_name("object")
                    if prop:
                        method_name = prop.text.decode("utf-8")
                        target_cls = None

                        if obj:
                            obj_text = obj.text.decode("utf-8")
                            if obj_text.startswith("this."):
                                obj_text = obj_text[5:]
                            target_cls = class_fields.get(current_cls, {}).get(obj_text)
                            if not target_cls and obj_text in class_methods:
                                target_cls = obj_text

                        if not target_cls:
                            matching = [c for c, m in class_methods.items() if method_name in m]
                            if len(matching) == 1:
                                target_cls = matching[0]

                        if target_cls:
                            calls.add((target_cls, method_name))
                elif fn_node and fn_node.type == "identifier":
                    fn_name = fn_node.text.decode("utf-8")
                    matching = [c for c, m in class_methods.items() if fn_name in m]
                    if len(matching) == 1:
                        calls.add((matching[0], fn_name))

            for child in n.children:
                visit(child)

        visit(node)
        return calls
