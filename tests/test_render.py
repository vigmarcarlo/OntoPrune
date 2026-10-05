"""
Unit tests for multi-format renderers and context size verification.
"""

from pathlib import Path

from ontoprune import translate
from ontoprune.parser import parse_file
from ontoprune.pruner import prune_subgraph
from ontoprune.render import render_contract


def test_render_all_formats() -> None:
    fixture_path = Path(__file__).parent.parent / "fixtures" / "sample_service.py"
    graph = parse_file(fixture_path)
    subgraph, target_uri = prune_subgraph(graph, "procesar_orden")

    for fmt in ["stubs", "turtle", "json", "nl"]:
        rendered = render_contract(subgraph, target_uri, fmt=fmt)
        assert len(rendered) > 0, f"Renderer '{fmt}' returned empty string"
        assert "procesar_orden" in rendered


def test_token_reduction_over_85_percent() -> None:
    """Verify criterion: pruned context achieves >= 85% token reduction compared to full file."""
    fixture_path = Path(__file__).parent.parent / "fixtures" / "sample_service.py"
    full_source = fixture_path.read_text(encoding="utf-8")

    full_tokens = len(full_source) / 4.0

    stubs_rendered = translate(fixture_path, "procesar_orden", fmt="stubs")
    stubs_tokens = len(stubs_rendered) / 4.0

    reduction_pct = ((full_tokens - stubs_tokens) / full_tokens) * 100.0

    assert reduction_pct >= 85.0, (
        f"Expected token reduction >= 85%, got {reduction_pct:.2f}% "
        f"({stubs_tokens:.0f} vs {full_tokens:.0f} estimated tokens)"
    )


def test_subgraph_compact_size() -> None:
    """Verify pruned contract is compact and drastically smaller than original source."""
    fixture_path = Path(__file__).parent.parent / "fixtures" / "sample_service.py"

    stubs_rendered = translate(fixture_path, "procesar_orden", fmt="stubs")
    stubs_tokens = len(stubs_rendered) / 4.0
    # Stubs for 7 dependencies with docs fits comfortably in ~300 tokens
    assert stubs_tokens < 400, f"Stubs tokens {stubs_tokens:.0f} exceeded 400 limit"

    turtle_rendered = translate(fixture_path, "procesar_orden", fmt="turtle")
    turtle_tokens = len(turtle_rendered) / 4.0
    # Turtle for 7 dependencies fits in ~500 tokens
    assert turtle_tokens < 600, f"Turtle tokens {turtle_tokens:.0f} exceeded 600 limit"
