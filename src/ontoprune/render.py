"""
Multi-Format Renderers for OntoPrune Subgraphs.

Transforms RDF subgraphs into deterministic textual representations:
- 'turtle': Canonical Turtle RDF syntax (< 200 tokens)
- 'stubs': Python type signature stubs
- 'json': Structured JSON contract
- 'nl': Natural language contract description
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import rdflib
from rdflib import RDFS, Namespace, URIRef

SOFT = Namespace("https://w3id.org/ontoprune/software#")
REPO = Namespace("https://w3id.org/ontoprune/repo/")


def _extract_function_info(graph: rdflib.Graph, func_uri: URIRef) -> dict[str, Any]:
    """Helper to extract structured metadata for a function from subgraph."""
    label = str(graph.value(func_uri, RDFS.label) or func_uri.split("#")[-1].split("/")[-1])
    class_name = graph.value(func_uri, SOFT.belongsToClass)
    returns = graph.value(func_uri, SOFT.returnsType)
    docstring = graph.value(func_uri, RDFS.comment)
    body = graph.value(func_uri, SOFT.sourceBody)

    params: list[dict[str, str | None]] = []
    for param_uri in sorted(graph.objects(func_uri, SOFT.hasParameter)):
        param_label = graph.value(param_uri, RDFS.label)
        param_type = graph.value(param_uri, SOFT.hasType)
        param_default = graph.value(param_uri, SOFT.hasDefault)
        params.append(
            {
                "name": str(param_label) if param_label else "arg",
                "type": str(param_type) if param_type else None,
                "default": str(param_default) if param_default else None,
            }
        )

    return {
        "uri": str(func_uri),
        "name": label,
        "class": str(class_name) if class_name else None,
        "returns": str(returns) if returns else "Any",
        "docstring": str(docstring).strip() if docstring else None,
        "parameters": params,
        "body": str(body) if body else None,
    }


def render_turtle(graph: rdflib.Graph, target_uri: URIRef) -> str:
    """Render canonical Turtle RDF representation."""
    graph.bind("soft", SOFT)
    graph.bind("repo", REPO)
    graph.bind("rdfs", RDFS)
    return graph.serialize(format="turtle")


def _render_stubs_py(graph: rdflib.Graph, target_uri: URIRef) -> str:
    """Render Python stubs contract for target and its dependencies."""
    target_info = _extract_function_info(graph, target_uri)
    callee_uris = sorted(graph.objects(target_uri, SOFT.invokes))
    callees_info = [_extract_function_info(graph, c) for c in callee_uris]

    lines: list[str] = ["# === OntoPrune Contract: Available APIs ===", ""]

    if callees_info:
        lines.append("# --- Dependencies / Available Invocations ---")
        for callee in callees_info:
            cls_prefix = f"# Class: {callee['class']}\n" if callee["class"] else ""
            args_str = ", ".join(
                f"{p['name']}: {p['type']}" if p["type"] else p["name"]
                for p in callee["parameters"]
            )
            fn_name = callee["name"].split(".")[-1]
            ret_str = f" -> {callee['returns']}" if callee["returns"] else ""
            doc_str = f'    """{callee["docstring"]}"""\n' if callee["docstring"] else ""
            lines.append(f"{cls_prefix}def {fn_name}({args_str}){ret_str}:\n{doc_str}    ...")
        lines.append("")

    lines.append("# --- Target Function Under Scope ---")
    cls_prefix = f"# Class: {target_info['class']}\n" if target_info["class"] else ""
    args_str = ", ".join(
        f"{p['name']}: {p['type']}{' = ' + p['default'] if p['default'] else ''}"
        if p["type"]
        else p["name"]
        for p in target_info["parameters"]
    )
    fn_name = target_info["name"].split(".")[-1]
    ret_str = f" -> {target_info['returns']}" if target_info["returns"] else ""
    doc_str = f'    """{target_info["docstring"]}"""\n' if target_info["docstring"] else ""

    if target_info["body"]:
        lines.append(f"{cls_prefix}# Original implementation:\n{target_info['body']}")
    else:
        lines.append(f"{cls_prefix}def {fn_name}({args_str}){ret_str}:\n{doc_str}    ...")

    return "\n".join(lines)


def _render_stubs_dart(graph: rdflib.Graph, target_uri: URIRef) -> str:
    """Render Dart / Flutter abstract class contract."""
    target_info = _extract_function_info(graph, target_uri)
    callee_uris = sorted(graph.objects(target_uri, SOFT.invokes))
    callees_info = [_extract_function_info(graph, c) for c in callee_uris]

    lines: list[str] = ["// === OntoPrune Contract: Dart Available APIs ===", ""]

    if callees_info:
        lines.append("// --- Dependencies / Available Invocations ---")
        by_class: dict[str, list[dict[str, Any]]] = {}
        for c in callees_info:
            cls = c["class"] or "GlobalScope"
            by_class.setdefault(cls, []).append(c)

        for cls, methods in by_class.items():
            lines.append(f"abstract class {cls} {{")
            for m in methods:
                args = ", ".join(f"{p['type'] or 'dynamic'} {p['name']}" for p in m["parameters"])
                lines.append(f"  {m['returns']} {m['name']}({args});")
            lines.append("}")
        lines.append("")

    lines.append("// --- Target Function Under Scope ---")
    target_cls = target_info["class"] or "GlobalScope"
    t_args = ", ".join(f"{p['type'] or 'dynamic'} {p['name']}" for p in target_info["parameters"])
    lines.append(f"abstract class {target_cls} {{")
    lines.append(f"  {target_info['returns']} {target_info['name']}({t_args});")
    lines.append("}")

    return "\n".join(lines)


def _render_stubs_java(graph: rdflib.Graph, target_uri: URIRef) -> str:
    """Render Java interface stubs contract."""
    target_info = _extract_function_info(graph, target_uri)
    callee_uris = sorted(graph.objects(target_uri, SOFT.invokes))
    callees_info = [_extract_function_info(graph, c) for c in callee_uris]

    lines: list[str] = ["// === OntoPrune Contract: Java Available APIs ===", ""]

    if callees_info:
        lines.append("// --- Dependencies / Available Invocations ---")
        by_class: dict[str, list[dict[str, Any]]] = {}
        for c in callees_info:
            cls = c["class"] or "GlobalScope"
            by_class.setdefault(cls, []).append(c)

        for cls, methods in by_class.items():
            lines.append(f"public interface {cls} {{")
            for m in methods:
                args = ", ".join(f"{p['type'] or 'Object'} {p['name']}" for p in m["parameters"])
                lines.append(f"    {m['returns']} {m['name']}({args});")
            lines.append("}")
        lines.append("")

    lines.append("// --- Target Function Under Scope ---")
    target_cls = target_info["class"] or "GlobalScope"
    t_args = ", ".join(f"{p['type'] or 'Object'} {p['name']}" for p in target_info["parameters"])
    lines.append(f"public interface {target_cls} {{")
    lines.append(f"    {target_info['returns']} {target_info['name']}({t_args});")
    lines.append("}")

    return "\n".join(lines)


def _render_stubs_ts(graph: rdflib.Graph, target_uri: URIRef) -> str:
    """Render TypeScript interface stubs contract."""
    target_info = _extract_function_info(graph, target_uri)
    callee_uris = sorted(graph.objects(target_uri, SOFT.invokes))
    callees_info = [_extract_function_info(graph, c) for c in callee_uris]

    lines: list[str] = ["// === OntoPrune Contract: TypeScript Available APIs ===", ""]

    if callees_info:
        lines.append("// --- Dependencies / Available Invocations ---")
        by_class: dict[str, list[dict[str, Any]]] = {}
        for c in callees_info:
            cls = c["class"] or "GlobalScope"
            by_class.setdefault(cls, []).append(c)

        for cls, methods in by_class.items():
            lines.append(f"export interface {cls} {{")
            for m in methods:
                args = ", ".join(f"{p['name']}: {p['type'] or 'any'}" for p in m["parameters"])
                lines.append(f"    {m['name']}({args}): {m['returns']};")
            lines.append("}")
        lines.append("")

    lines.append("// --- Target Function Under Scope ---")
    target_cls = target_info["class"] or "GlobalScope"
    t_args = ", ".join(f"{p['name']}: {p['type'] or 'any'}" for p in target_info["parameters"])
    lines.append(f"export interface {target_cls} {{")
    lines.append(f"    {target_info['name']}({t_args}): {target_info['returns']};")
    lines.append("}")

    return "\n".join(lines)


def render_stubs(graph: rdflib.Graph, target_uri: URIRef) -> str:
    """Render stubs contract, auto-detecting language dialect from RDF graph."""
    lang = None
    # Check target function language or module language
    for val in graph.objects(target_uri, SOFT.language):
        lang = str(val).lower()
        break
    if not lang:
        for val in graph.objects(predicate=SOFT.language):
            lang = str(val).lower()
            break

    if lang == "dart":
        return _render_stubs_dart(graph, target_uri)
    elif lang == "java":
        return _render_stubs_java(graph, target_uri)
    elif lang in ("typescript", "ts", "javascript", "js", "tsx"):
        return _render_stubs_ts(graph, target_uri)
    return _render_stubs_py(graph, target_uri)


def render_json(graph: rdflib.Graph, target_uri: URIRef) -> str:
    """Render JSON contract for target and callees."""
    target_info = _extract_function_info(graph, target_uri)
    callee_uris = sorted(graph.objects(target_uri, SOFT.invokes))
    callees_info = [_extract_function_info(graph, c) for c in callee_uris]

    contract = {
        "target": target_info,
        "allowed_dependencies": callees_info,
    }
    return json.dumps(contract, indent=2, ensure_ascii=False)


def render_nl(graph: rdflib.Graph, target_uri: URIRef) -> str:
    """Render structured natural language contract."""
    target_info = _extract_function_info(graph, target_uri)
    callee_uris = sorted(graph.objects(target_uri, SOFT.invokes))
    callees_info = [_extract_function_info(graph, c) for c in callee_uris]

    target_name = target_info["name"]
    target_cls = f" belonging to class '{target_info['class']}'" if target_info["class"] else ""
    target_params = (
        ", ".join(f"{p['name']} ({p['type'] or 'Any'})" for p in target_info["parameters"])
        or "none"
    )

    lines = [
        f"Function under scope: '{target_name}'{target_cls}.",
        f"- Parameters: {target_params}",
        f"- Return type: {target_info['returns']}",
    ]
    if target_info["docstring"]:
        lines.append(f"- Purpose: {target_info['docstring']}")

    if callees_info:
        lines.append("\nAuthorized dependencies that this function may invoke:")
        for c in callees_info:
            c_cls = f" (in {c['class']})" if c["class"] else ""
            c_params = (
                ", ".join(f"{p['name']}: {p['type'] or 'Any'}" for p in c["parameters"])
                or "no arguments"
            )
            lines.append(f"- '{c['name']}'{c_cls} with {c_params} -> returns {c['returns']}")

    return "\n".join(lines)


RENDERERS: dict[str, Callable[[rdflib.Graph, URIRef], str]] = {
    "turtle": render_turtle,
    "stubs": render_stubs,
    "json": render_json,
    "nl": render_nl,
}


def render_contract(graph: rdflib.Graph, target_uri: URIRef, fmt: str = "stubs") -> str:
    """Render subgraph to desired format."""
    renderer = RENDERERS.get(fmt.lower())
    if not renderer:
        valid = list(RENDERERS.keys())
        raise ValueError(f"Unknown format '{fmt}'. Supported formats: {valid}")
    return renderer(graph, target_uri)
