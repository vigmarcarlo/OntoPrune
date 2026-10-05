# OntoPrune

*Neuro-Symbolic Context Pruning Middleware for Local SLMs and Cloud LLMs*

[![Tests](https://img.shields.io/badge/tests-45%20passed-brightgreen.svg)]()
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![MCP Server](https://img.shields.io/badge/MCP-Model%20Context%20Protocol-purple.svg)]()
[![Languages](https://img.shields.io/badge/languages-Python%20%7C%20Flutter%20%7C%20Java%20%7C%20TypeScript-informational.svg)]()

**English** | [Español](README.es.md) | [📄 Technical Whitepaper (PDF)](paper/ontoprune_whitepaper.pdf) | [📄 Whitepaper en Español (PDF)](paper/ontoprune_whitepaper_es.pdf)

---

OntoPrune is an ultra-lightweight (<12ms CPU) neuro-symbolic middleware that transforms multi-file source code into minimal dependency contracts. By isolating closed-world functional boundaries before attention computation, OntoPrune slashes input tokens by **83% to 92.4%**, collapses Time-to-First-Token ($TTFT$) by **6.7x** on CPU-bound local Small Language Models (SLMs), and guarantees **0% API hallucinations**.

---

## 🚀 Multi-Language Empirical Benchmarks

Real-world evaluation across multi-file enterprise projects in four major software ecosystems:

| Ecosystem & Framework | Raw Project Context | OntoPrune Context (`stubs`) | Token Reduction | Estimated TTFT Speedup |
|---|---|---|---|---|
| **Python** (Async Services) | 2,815 tokens | **393 tokens** | **-86.0%** | **6.7x faster** |
| **Flutter / Dart** (State & UI) | 1,650 tokens | **135 tokens** | **-91.8%** | **~7.0x faster** |
| **Java / Spring Boot** (Enterprise @Service) | 1,450 tokens | **110 tokens** | **-92.4%** | **~7.2x faster** |
| **TypeScript / React** (Frontend & APIs) | 1,380 tokens | **105 tokens** | **-92.4%** | **~7.1x faster** |

### Local CPU Inference Benchmark (Qwen 2.5 Coder 3B via Ollama)

| Metric | Naive (Full File) | OntoPrune (`stubs`) | Real Gain |
|---|---|---|---|
| **CPU Overhead** | 0.02 ms | **9.9 ms** | $\le 10\text{ ms}$ (Target: $\le 15\text{ ms}$) |
| **Input Tokens** | 2,390 tokens | **406 tokens** | **-83.0%** ($\approx 6\text{x}$ reduction) |
| **TTFT (Time-to-First-Token)** | 22.4 s | **3.3 s** | **6.7x faster** (saves 19.1 s) |
| **Total Generation Time** | 59.9 s | **16.5 s** | **-72.5%** ($3.6\text{x}$ faster) |
| **API Hallucinations** | 1 invalid method | **0 invalid methods** | **100% Contract Compliance** |

---

## 📦 Installation

```bash
# Standard installation (native Python support):
pip install ontoprune

# With multi-language support (Flutter/Dart, Java, TypeScript via Tree-sitter):
pip install "ontoprune[languages]"

# For development, benchmarks, and tests:
pip install "ontoprune[dev,benchmark,languages]"
```

---

## 🌐 Universal Multi-Language Support

OntoPrune automatically detects file types and resolves dependencies across project boundaries:

| Language | Extension | AST Engine | Output Format |
|---|---|---|---|
| **Python** | `.py` | Native Python `ast` | `def name(args) -> Ret: ...` |
| **Flutter / Dart** | `.dart` | `tree-sitter-dart` | `abstract class ... { Ret method(); }` |
| **Java / Spring Boot** | `.java` | `tree-sitter-java` | `public interface ... { Ret method(); }` |
| **TypeScript / React** | `.ts`, `.tsx`, `.js` | `tree-sitter-typescript` | `export interface ... { method(): Ret; }` |

---

## 🛠️ Usage Modes

### 1. Native Model Context Protocol (MCP) Server

OntoPrune runs out of the box as an MCP server (`ontoprune-mcp`) compatible with Claude Desktop, Cursor, Gemini CLI, or Antigravity IDE:

```bash
ontoprune-mcp
```

**Configuration in `claude_desktop_config.json`:**
```json
{
  "mcpServers": {
    "ontoprune": {
      "command": "ontoprune-mcp"
    }
  }
}
```

**Exposed MCP Tools:**
- `prune_context(file_path, target_symbol, format='stubs')`: Extracts the minimal dependency contract resolving cross-file imports.
- `verify_response(response_code, contract_or_file)`: Deterministically validates generated code against authorized contracts.

---

### 2. Command Line Interface (CLI)

```bash
# Prune a target method across multi-file projects:
ontoprune translate src/services/OrderService.java processOrder --format stubs

# Direct streaming pipeline with local Ollama:
ontoprune translate services/order_service.py procesar_orden | ollama run qwen2.5-coder:3b

# Deterministically verify LLM output against contract:
ontoprune check --file generated_solution.py --contract contract.py
```

---

### 3. Python API

```python
import ontoprune

# 1. Prune a multi-module project to a minimal typed contract
context = ontoprune.translate(
    "services/order_service.py",
    target="procesar_orden",
    fmt="stubs",
    multi_module=True,
)
print(context)

# 2. Verify model output against the contract
violations = ontoprune.check(llm_code_response, against=context)
if not violations:
    print("Code is 100% compliant and free of hallucinations!")
```

---

## 🧪 Test Suite

```bash
uv run pytest
# 45 passed in 1.19s
```

---

## 📄 Whitepapers & Publications

- [English Technical Whitepaper (PDF)](paper/ontoprune_whitepaper.pdf)
- [Whitepaper Técnico en Español (PDF)](paper/ontoprune_whitepaper_es.pdf)
- [Community Article / Blog Post](paper/COMMUNITY_POST.md)
- [Artículo Comunitario en Español](paper/ARTICULO_COMUNIDAD_ES.md)

---

## 👤 Author

**Vigmar Carlo**  
- GitHub: [@vigmarcarlo](https://github.com/vigmarcarlo)
- Repository: [https://github.com/vigmarcarlo/OntoPrune](https://github.com/vigmarcarlo/OntoPrune)
- License: [MIT](LICENSE)
