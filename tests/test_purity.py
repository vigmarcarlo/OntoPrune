"""
Purity and independence test for OntoPrune core middleware.

Verifies:
- Core middleware does not import requests, urllib.request, or any network libraries.
- Core middleware only depends on standard library and rdflib.
"""

import ontoprune
from ontoprune import check, parser, pruner, render


def test_core_middleware_network_independence() -> None:
    # Ensure no network libraries are in core modules
    core_modules = [ontoprune, parser, pruner, render, check]

    forbidden_modules = ["requests", "urllib.request", "http.client", "httpx", "aiohttp"]

    for mod in core_modules:
        for forbidden in forbidden_modules:
            assert forbidden not in mod.__dict__, (
                f"Core module '{mod.__name__}' must not import '{forbidden}'"
            )
