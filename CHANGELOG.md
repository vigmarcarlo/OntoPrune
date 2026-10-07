# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.3.0] - 2026-10-06

### Added
- **Domain Types & Data Models Extraction:**
  - Automatic detection and RDF modeling (`soft:usesType`) of `@dataclass`, `Enum`, and domain structures.
  - Dedicated `# --- Domain Types & Data Models ---` section in Python stubs renderer, exporting field names and type annotations without leaking internal defaults or logic.
- **Structured Class Containers for MCP & IDEs:**
  - Enclosing `class ClassName:` scopes with instance `self` parameter for both dependencies and target functions, ensuring exact scope and indentation compatibility for AI agents (Cursor, Claude Code, GitHub Copilot).
- **Automated Empirical Benchmark Suite:**
  - Native CLI command: `ontoprune benchmark [--backend {all,gemini,ollama,mock}] [--analyze]`.
  - Automated `Makefile` targets: `make benchmark-mock`, `make benchmark-gemini`, `make benchmark-ollama`, `make test`.
  - Isolated temporary sandboxes evaluating functional fidelity (`Pass@1`) via real `pytest` execution.
- **Mathematical Pre-fill Latency Analysis:**
  - Documented physical proof of how pruning breaks the CPU Pre-fill ($TTFT$) bottleneck in local LLMs (Ollama / Qwen 2.5 Coder 7B), dropping initial wait time from 34.3s down to 13.0s.

### Changed
- Refactored `prune_subgraph` with ultra-fast in-memory copy (`_copy_type_node`) maintaining warm-run CPU overhead under 15ms.
- Updated documentation ([README.md](README.md) and [README.es.md](README.es.md)) with empirical evidence matrix from 24 independent sandbox runs.
- Expanded test suite to **47 automated unit tests** (100% passing).

---

## [0.2.0] - 2026-10-05

### Added
- Multi-language AST parsing via Tree-sitter for Flutter/Dart (`.dart`), Java/Spring Boot (`.java`), and TypeScript/React (`.ts`, `.tsx`, `.js`).
- Multi-module recursive import resolution across project directory structures (`ProjectGraph` and `ImportResolver`).
- Initial Model Context Protocol (MCP) server `ontoprune-mcp` exposing `prune_context` and `verify_response` tools.

---

## [0.1.0] - 2026-10-04

### Added
- Initial release of OntoPrune core engine with Python AST parser.
- SPARQL CONSTRUCT closed-world dependency extraction.
- Output renderers: Python stubs (`stubs`), RDF Turtle (`turtle`), JSON, and natural language (`nl`).
- Contract purity checker `ontoprune check` to detect hallucinated API calls.
