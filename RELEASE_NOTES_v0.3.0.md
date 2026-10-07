# OntoPrune v0.3.0 — Domain Types Extraction, Class Scoping & Empirical Benchmark Suite

> **Deterministic Context Pruning for LLM Code Assistants: Reducing Pre-fill Latency & Eliminating Hallucinations**

OntoPrune `v0.3.0` brings major enhancements for AI coding agents (Cursor, Claude Code, GitHub Copilot) and local LLMs (Ollama / Qwen 2.5 Coder), introducing automatic domain model extraction (`@dataclass`, `Enum`), class container scoping, and a native empirical benchmark harness with real pytest sandboxes.

---

## 🚀 What's New in v0.3.0

### 1. 📦 Domain Types & Data Models Extraction
* **Automatic Detection:** Extracted domain models (`@dataclass`, `Enum`, standard classes) used in parameters or return types are automatically identified and mapped via RDF ontology (`soft:usesType`).
* **Clean Interface Contracts:** Renders a dedicated `# --- Domain Types & Data Models ---` section with typed fields without leaking private implementation logic or internal defaults.

### 2. 🧱 Structured Class Containers for MCP & IDEs
* Stubs now maintain their enclosing class structure:
  ```python
  class ServiceName:
      def method(self, arg: int) -> bool:
          ...
  ```
* Ensures accurate scope and indentation compatibility for AI agents generating inline patch edits.

### 3. 🧪 Empirical Benchmark Suite & CLI Subcommand
* Integrated CLI evaluation command:
  ```bash
  ontoprune benchmark --backend mock --analyze
  ```
* Automated execution targets via `Makefile` (`make benchmark-mock`, `make test`).
* **Sandbox Verification:** Runs generated code against real `pytest` suites to measure strict functional correctness (**Pass@1**).

### 4. ⚡ Breakthrough for Local LLMs (Ollama / CPU Pre-fill)
* Demonstrates mathematical proof of how token pruning breaks the CPU Pre-fill ($TTFT$) bottleneck:
  * **Tokens:** Reduced from **8,750** to **620** (**-92.9%** context overhead).
  * **Time-to-First-Token (TTFT):** Dropped from **34.3s** to **13.0s** (**62.1% faster response**).
  * **Pass@1:** Reaches **100% functional fidelity** while non-pruned contexts degraded to 0% due to context dilution.

### 5. 🛡️ MCP Server (`ontoprune-mcp`)
* Standalone executable entrypoint registered in PyPI:
  ```bash
  ontoprune-mcp
  ```
* Implements JSON-RPC stdio protocol with `prune_context` and `verify_response` tools for seamless integration with Model Context Protocol clients.

---

## 📊 Empirical Results Matrix

| Metric | Raw Codebase (No Pruning) | OntoPrune Contract | Impact |
| :--- | :---: | :---: | :---: |
| **Context Overhead** | ~8,750 tokens | **~620 tokens** | **-92.9% reduction** |
| **Gemini 2.5 Flash TTFT** | 1.82 s | **0.84 s** | **2.2× faster** |
| **Qwen 2.5 Coder 7B (CPU) TTFT** | 34.3 s | **13.0 s** | **62.1% faster** |
| **Pass@1 (Qwen 2.5 Coder 7B)** | 0.0% (3/3 failed) | **100.0% (3/3 passed)** | **+100% fidelity** |
| **Engine Overhead** | — | **< 15 ms** | Near-zero latency |

---

## 📦 Installation & Quickstart

### From PyPI
```bash
pip install ontoprune==0.3.0
```
or with `uv`:
```bash
uv pip install ontoprune==0.3.0
```

### CLI Usage
```bash
# Extract minimal contract for a target function
ontoprune translate path/to/file.py function_name

# Verify an LLM response against the contract
ontoprune check path/to/file.py function_name "response_code.py"
```

### Claude Desktop / Cursor MCP Configuration
Add to your `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "ontoprune": {
      "command": "ontoprune-mcp"
    }
  }
}
```

---

## 🔗 Useful Links
* **PyPI Package:** https://pypi.org/project/ontoprune/0.3.0/
* **GitHub Repository:** https://github.com/vigmarcarlo/OntoPrune
* **Release Tag:** [`v0.3.0`](https://github.com/vigmarcarlo/OntoPrune/releases/tag/v0.3.0)
