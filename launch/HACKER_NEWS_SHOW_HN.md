# Show HN: OntoPrune – Neuro-Symbolic Context Pruning for Local SLMs and Coding Agents

**URL:** https://github.com/vigmarcarlo/OntoPrune
**Title:** Show HN: OntoPrune – Neuro-symbolic context pruner cutting 85% tokens and 6.7x TTFT on CPU

Hi HN!

When writing code with local LLMs (or large cloud models), the default strategy is usually naive: dump entire files or grep chunks into the context window. 

On local hardware (running Ollama on a CPU/laptop), this is painful: processing a 2,400-token prompt on a 3B model can take 20+ seconds just to reach the first token (Time to First Token / TTFT). Moreover, models regularly hallucinate plausible-sounding methods that don't actually exist in the codebase.

To solve this, I built **OntoPrune**: a lightweight (< 10 ms CPU overhead) neuro-symbolic middleware that:
1. Parses source code AST into an in-memory RDF knowledge graph using an internal ontology.
2. Runs a deterministic SPARQL query to extract the exact 1-hop closure (signatures, docstrings, called dependencies) needed for the function you're editing.
3. Projects that graph back as minimal, typed Python stubs (< 400 tokens).
4. Verifies the LLM's response using an AST call-checker, flagging any unauthorized API calls with 0 false negatives.

### Empirical Benchmarks

Running live on CPU (12 cores) with `qwen2.5-coder:3b`:
- **Input tokens:** 2,390 -> 406 tokens (**-83.0%**)
- **TTFT:** 22.4s -> 3.3s (**6.7x faster**, saving 19s per prompt)
- **Total latency:** 59.9s -> 16.5s (**-72.5%**)
- **API Hallucinations:** 1 invalid call in naive prompt -> **0 in OntoPrune**

On Google Gemini 3.8 Flash:
- **Input tokens:** 2,815 -> 393 tokens (**-86.0%**)

### Design Philosophy
- **The ontology is invisible:** You never write RDF or SPARQL manually. OntoPrune exposes standard Python APIs, a CLI, and a Model Context Protocol (MCP) server for Cursor / Claude Desktop / Antigravity.
- **Pure Python & Zero GPU:** Core engine uses Python's standard `ast` and `rdflib`. Parsing + SPARQL resolution completes in **9.9 ms**.
- **Multi-Module Aware:** Automatically resolves relative and absolute imports across project boundaries.

### Quick Start
```bash
pip install ontoprune

# As CLI:
ontoprune translate services/order_service.py procesar_orden --format stubs

# Or run as MCP server:
ontoprune-mcp
```

Full benchmark code, reproducible suite, and technical whitepaper are in the repository:
https://github.com/vigmarcarlo/OntoPrune

I'd love your feedback on the architecture and benchmark results!
