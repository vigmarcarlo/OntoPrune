# [Project] OntoPrune: 6.7x faster TTFT on local CPU with Ollama by neuro-symbolic context pruning (83-86% token savings + 0% hallucinations)

**Repository:** https://github.com/vigmarcarlo/OntoPrune
**License:** MIT

Hey r/LocalLLaMA!

If you run small coding models (Qwen 2.5 Coder 1.5B/3B, Gemma 2B, DeepSeek Coder) on commodity hardware (like a CPU-only laptop or mini PC with Ollama), you know the prompt evaluation bottleneck. 

Feeding a 300-line service file into a 3B model on CPU took **22.4 seconds just to generate the first token (TTFT)**. Plus, smaller models frequently invent bogus methods when given too much noisy context.

I built **OntoPrune** to solve this. It's a lightweight, 100% offline Python middleware that acts as a symbolic context compiler:

### What it does:
1. Translates source code into an in-memory knowledge graph using an internal ontology.
2. Extracts the exact 1-hop closure of the function you're editing via SPARQL (only the classes, functions, and interfaces it actually interacts with).
3. Renders the pruned graph back into clean, typed Python stubs (~400 tokens instead of 2,400+).
4. Verifies the model's generated code against the contract AST to catch any API hallucinations.

### Benchmark on local CPU (12 cores, Ollama streaming):
- **Model:** `qwen2.5-coder:3b`
- **Input tokens:** 2,390 -> 406 tokens (**-83.0%**)
- **TTFT (Time to First Token):** 22.4s -> 3.3s (**6.7x faster**, saving 19.1 seconds!)
- **Total generation time:** 59.9s -> 16.5s (**-72.5%**)
- **Hallucinations:** Full file context hallucinated 1 non-existent method call; OntoPrune had **0 invalid calls**.
- **CPU Overhead of OntoPrune:** AST parsing + RDF graph generation + SPARQL query takes **9.9 ms** total.

### Also tested on Gemini 3.8 Flash (Cloud):
- 2,815 tokens -> 393 tokens (**-86.0% cost reduction**).

### Features:
- **Zero RDF exposure:** You and your LLM only interact with regular Python signatures and stubs.
- **Model Context Protocol (MCP):** Comes with `ontoprune-mcp` so you can use it in Cursor, Claude Desktop, Antigravity, or any agent.
- **Multi-module resolution:** Follows project imports across files without choking on circular dependencies.
- **Contract verification:** Deterministically flags hallucinated APIs in CI/CD or CLI pipes.

### How to use:
```bash
pip install ontoprune

# CLI pipe directly into Ollama:
ontoprune translate services/order_service.py procesar_orden --format stubs | ollama run qwen2.5-coder:3b

# Run benchmark on your machine:
python -m ontoprune.benchmark --file fixtures/sample_service.py --func procesar_orden --backend ollama --model qwen2.5-coder:3b
```

Paper and reproducible code are all open-source on GitHub:
https://github.com/vigmarcarlo/OntoPrune

Feedback, PRs, and benchmark runs on different hardware are super welcome!
