"""
SPARQL-based Semantic Pruning Engine for OntoPrune.

Extracts the minimal 1-hop software dependency subgraph for a given
target function or method using a precompiled SPARQL CONSTRUCT query.
"""

from __future__ import annotations

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
                soft:invokes ?callee .

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
                soft:invokes ?callee .

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
    for s, _, o in graph.triples((None, RDFS.label, None)):
        if (s, RDF.type, SOFT.Function) in graph:
            label_val = str(o)
            if label_val.endswith(suffix):
                candidates.append(s)

    if len(candidates) == 1:
        return candidates[0]
    elif len(candidates) > 1:
        labels = [str(graph.value(c, RDFS.label)) for c in candidates]
        raise ValueError(f"Ambiguous target symbol '{symbol_name}'. Multiple candidates: {labels}.")

    raise KeyError(f"Symbol '{symbol_name}' not found in code graph.")


def prune_subgraph(
    graph: rdflib.Graph,
    target_symbol: str,
    include_body: bool = False,
) -> tuple[rdflib.Graph, URIRef]:
    """
    Executes precompiled SPARQL CONSTRUCT query to extract the pruned
    1-hop dependency subgraph for target_symbol.
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

    return subgraph, target_uri
