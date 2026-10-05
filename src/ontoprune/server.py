"""
Model Context Protocol (MCP) Server for OntoPrune.

Exposes OntoPrune's semantic pruning and contract verification
as standard MCP tools for LLMs, IDEs, and autonomous coding agents.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer

from ontoprune import check, translate

# Initialize OntoPrune MCP Server
mcp_server = MCPServer("ontoprune")


@mcp_server.tool()
def prune_context(
    file_path: str,
    target_symbol: str,
    format: str = "stubs",
    include_body: bool = False,
    project_root: str | None = None,
) -> str:
    """
    Extracts a minimal, hallucination-resistant context contract for a given function or method.
    Reduces input tokens by >80% while preserving exact type signatures and dependencies across project modules.

    Args:
        file_path: Absolute or relative path to the Python source file.
        target_symbol: Identifier of the function or method (e.g. 'procesar_orden' or 'OrderService.procesar_orden').
        format: Desired output format: 'stubs' (default, optimal for code LLMs), 'turtle' (RDF), 'json', or 'nl'.
        include_body: Whether to include the raw source code body of the target function.
        project_root: Optional root directory of the project (auto-detected if omitted).

    Returns:
        The compact pruned contract string.
    """
    path = Path(file_path)
    if not path.exists():
        return f"Error: File '{file_path}' does not exist."

    try:
        contract = translate(
            source_or_file=path,
            target=target_symbol,
            fmt=format,
            include_body=include_body,
            multi_module=True,
            project_root=project_root,
        )
        return contract
    except Exception as err:
        return f"Error pruning context: {err}"


@mcp_server.tool()
def verify_response(
    response_code: str,
    contract_or_file: str,
    target_symbol: str | None = None,
) -> dict[str, Any]:
    """
    Verifies LLM-generated code against an ontological software contract to detect
    hallucinated or unauthorized method/function calls.

    Args:
        response_code: The Python code snippet or markdown text produced by the model.
        contract_or_file: Either the rendered contract string OR the path to the original Python file.
        target_symbol: If contract_or_file is a file path, specify the target symbol to extract its contract.

    Returns:
        Dictionary with validation status, count of violations, and list of invalid calls.
    """
    contract_text = contract_or_file
    path = Path(contract_or_file)
    if path.exists() and path.is_file():
        if not target_symbol:
            # Check against full file
            contract_text = path.read_text(encoding="utf-8")
        else:
            try:
                contract_text = translate(path, target=target_symbol, fmt="stubs")
            except Exception as err:
                return {
                    "is_valid": False,
                    "error": f"Failed to extract contract from file: {err}",
                    "hallucinations": [],
                }

    violations = check(response_code, against=contract_text)
    return {
        "is_valid": len(violations) == 0,
        "hallucination_count": len(violations),
        "invalid_calls": violations,
        "summary": "100% Valid Contract Compliance"
        if not violations
        else f"{len(violations)} invalid calls detected",
    }


def run_stdio() -> None:
    """Run the MCP server over standard input/output (stdio transport)."""
    mcp_server.run()


if __name__ == "__main__":
    run_stdio()
