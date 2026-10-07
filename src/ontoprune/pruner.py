"""
SPARQL-based Semantic Pruning Engine for OntoPrune.

Extracts the minimal 1-hop software dependency subgraph for a given
target function or method using a precompiled SPARQL CONSTRUCT query.
"""

from __future__ import annotations

import re
import rdflib
from rdflib import RDF, RDFS, Literal, Namespace, URIRef
from rdflib.plugins.sparql import prepareQuery

SOFT = Namespace("https://w3id.org/ontoprune/software#")
REPO = Namespace("https://w3id.org/ontoprune/repo/")

_SPARQL_CONSTRUCT_NO_BODY = prepareQuery(
    """
    PREFIX soft: <https://w3id.org/ontoprune/software#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    CONSTRUCT {
        ?target a soft:Function ;
                rdfs:label ?targetName ;
                soft:language ?lang ;
                soft:belongsToClass ?className ;
                soft:returnsType ?returnType ;
                rdfs:comment ?docstring ;
                soft:decoratedWith ?dec ;
                soft:hasParameter ?param ;
                soft:invokes ?callee ;
                soft:usesType ?domainType .

        ?param a soft:Parameter ;
               rdfs:label ?paramName ;
               soft:hasType ?paramType ;
               soft:hasDefault ?paramDefault .

        ?callee a soft:Function ;
                rdfs:label ?calleeName ;
                soft:belongsToClass ?calleeClass ;
                soft:returnsType ?calleeReturn .
    }
    WHERE {
        ?target a soft:Function ;
                rdfs:label ?targetName .

        OPTIONAL { ?target soft:language ?lang . }
        OPTIONAL { ?target soft:belongsToClass ?className . }
        OPTIONAL { ?target soft:returnsType ?returnType . }
        OPTIONAL { ?target rdfs:comment ?docstring . }
        OPTIONAL { ?target soft:decoratedWith ?dec . }

        OPTIONAL {
            ?target soft:hasParameter ?param .
            ?param rdfs:label ?paramName .
            OPTIONAL { ?param soft:hasType ?paramType . }
            OPTIONAL { ?param soft:hasDefault ?paramDefault . }
        }

        OPTIONAL {
            ?target soft:invokes ?callee .
            ?callee rdfs:label ?calleeName .
            OPTIONAL { ?callee soft:belongsToClass ?calleeClass . }
            OPTIONAL { ?callee soft:returnsType ?calleeReturn . }
        }

        OPTIONAL {
            ?target soft:usesType ?domainType .
        }
    }
    """,
    initNs={"soft": SOFT, "rdfs": RDFS},
)

_SPARQL_CONSTRUCT_WITH_BODY = prepareQuery(
    """
    PREFIX soft: <https://w3id.org/ontoprune/software#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    CONSTRUCT {
        ?target a soft:Function ;
                rdfs:label ?targetName ;
                soft:language ?lang ;
                soft:belongsToClass ?className ;
                soft:returnsType ?returnType ;
                rdfs:comment ?docstring ;
                soft:decoratedWith ?dec ;
                soft:sourceBody ?body ;
                soft:hasParameter ?param ;
                soft:invokes ?callee ;
                soft:usesType ?domainType .

        ?param a soft:Parameter ;
               rdfs:label ?paramName ;
               soft:hasType ?paramType ;
               soft:hasDefault ?paramDefault .

        ?callee a soft:Function ;
                rdfs:label ?calleeName ;
                soft:belongsToClass ?calleeClass ;
                soft:returnsType ?calleeReturn .
    }
    WHERE {
        ?target a soft:Function ;
                rdfs:label ?targetName .

        OPTIONAL { ?target soft:language ?lang . }
        OPTIONAL { ?target soft:belongsToClass ?className . }
        OPTIONAL { ?target soft:returnsType ?returnType . }
        OPTIONAL { ?target rdfs:comment ?docstring . }
        OPTIONAL { ?target soft:decoratedWith ?dec . }
        OPTIONAL { ?target soft:sourceBody ?body . }

        OPTIONAL {
            ?target soft:hasParameter ?param .
            ?param rdfs:label ?paramName .
            OPTIONAL { ?param soft:hasType ?paramType . }
            OPTIONAL { ?param soft:hasDefault ?paramDefault . }
        }

        OPTIONAL {
            ?target soft:invokes ?callee .
            ?callee rdfs:label ?calleeName .
            OPTIONAL { ?callee soft:belongsToClass ?calleeClass . }
            OPTIONAL { ?callee soft:returnsType ?calleeReturn . }
        }

        OPTIONAL {
            ?target soft:usesType ?domainType .
        }
    }
    """,
    initNs={"soft": SOFT, "rdfs": RDFS},
)


def find_symbol_uri(graph: rdflib.Graph, symbol_name: str) -> URIRef:
    """Fast indexed symbol lookup."""
    # 1. Exact URI
    if symbol_name.startswith("http://") or symbol_name.startswith("https://"):
        target_uri = URIRef(symbol_name)
        if (target_uri, RDF.type, SOFT.Function) in graph:
            return target_uri

    # 2. Fast exact label lookup
    exact_matches = [
        s
        for s in graph.subjects(RDFS.label, Literal(symbol_name))
        if (s, RDF.type, SOFT.Function) in graph
    ]
    if len(exact_matches) == 1:
        return exact_matches[0]

    # 3. Partial suffix match (e.g. 'procesar_orden' matching 'OrderService.procesar_orden')
    suffix = f".{symbol_name}"
    candidates = []
    for s in graph.subjects(RDF.type, SOFT.Function):
        label_val = str(graph.value(s, RDFS.label) or "")
        if label_val.endswith(suffix):
            candidates.append(s)

    if len(candidates) == 1:
        return candidates[0]
    elif len(candidates) > 1:
        labels = [str(graph.value(c, RDFS.label)) for c in candidates]
        raise ValueError(f"Ambiguous target symbol '{symbol_name}'. Multiple candidates: {labels}.")

    raise KeyError(f"Symbol '{symbol_name}' not found in code graph.")


def _copy_type_node(src: rdflib.Graph, dst: rdflib.Graph, type_uri: URIRef) -> None:
    """Copies a domain class node and all its attributes into destination graph."""
    for p, o in src.predicate_objects(type_uri):
        dst.add((type_uri, p, o))
        if p == SOFT.hasAttribute:
            for ap, ao in src.predicate_objects(o):
                dst.add((o, ap, ao))


def prune_subgraph(
    graph: rdflib.Graph,
    target_symbol: str,
    include_body: bool = False,
) -> tuple[rdflib.Graph, URIRef]:
    """
    Executes precompiled SPARQL CONSTRUCT query to extract the pruned
    1-hop dependency subgraph and direct domain types for target_symbol.
    """
    target_uri = find_symbol_uri(graph, target_symbol)

    query = _SPARQL_CONSTRUCT_WITH_BODY if include_body else _SPARQL_CONSTRUCT_NO_BODY
    result = graph.query(query, initBindings={"target": target_uri})

    subgraph = rdflib.Graph()
    subgraph.bind("soft", SOFT)
    subgraph.bind("repo", REPO)
    subgraph.bind("rdfs", RDFS)

    for triple in result:
        subgraph.add(triple)

    # Ultra-fast indexed copy of domain models directly used by target's signature & body
    ret_type = str(graph.value(target_uri, SOFT.returnsType) or "")
    sig_words = set(re.findall(r"\b[A-Za-z0-9_]+\b", ret_type))
    for param_uri in graph.objects(target_uri, SOFT.hasParameter):
        p_type = str(graph.value(param_uri, SOFT.hasType) or "")
        sig_words.update(re.findall(r"\b[A-Za-z0-9_]+\b", p_type))

    for d_uri in list(graph.objects(target_uri, SOFT.usesType)):
        label = str(graph.value(d_uri, RDFS.label) or "")
        if label in sig_words or include_body:
            _copy_type_node(graph, subgraph, d_uri)
            for nested in graph.objects(d_uri, SOFT.usesType):
                _copy_type_node(graph, subgraph, nested)

    return subgraph, target_uri
