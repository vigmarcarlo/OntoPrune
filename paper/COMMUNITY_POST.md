# How We Cut 90% of Context Tokens and Sped Up TTFT by 6.7x in Coding LLMs (Python, Flutter, Java & TypeScript)

**TL;DR:** When asking LLMs to write or refactor code, dumping entire multi-file modules into the prompt causes quadratic attention latency ($\mathcal{O}(N^2)$), 20+ second freezes on local SLMs, and frequent API hallucinations. We built **OntoPrune**, an open-source deterministic middleware (<12ms CPU) that extracts the exact minimal dependency contract of any target function across multi-file projects. Across Python, Flutter/Dart, Java/Spring Boot, and TypeScript/React, it slashes prompt tokens by **83%–92%**, accelerates Time-to-First-Token by **6.7x** on CPU-bound local models, and completely eliminates API hallucinations.

---

### The Frustration: Why More Context Is Actually Worse

If you work with coding models—whether you run local models via Ollama (`qwen2.5-coder`, `llama-3.2`) or call cloud frontier APIs (`gemini-2.5-flash`, `claude-3-5-sonnet`)—you have probably encountered this exact loop:

You ask the model to implement a unit test or refactor a single function:
```python
def process_order(order_id: str, repo: OrderRepository) -> Order:
    ...
```
To give the model "context", tools or developer prompts typically dump:
- The entire 600-line service file.
- All 15 imported files and headers.
- Unrelated models, utility classes, and database helpers.

#### The Three Bottlenecks This Triggers:

1. **Attention Bottleneck ($\mathcal{O}(N^2)$):** 
   On local laptops/CPUs, processing a 3,000-token prompt creates massive KV-cache pressure. On a 3B parameter model, you can easily wait **20 to 25 seconds** just for the model to emit its *first token* (Time-to-First-Token / TTFT).
2. **"Lost in the Middle" & API Hallucinations:**
   When an LLM sees multiple repositories and dozens of helper functions, it easily confuses homonymous methods (e.g. calling `OrderRepo.save_to_db()` instead of `OrderRepo.save()`), or invents APIs that don't exist in your codebase.
3. **Cloud API Costs:**
   Passing thousands of boilerplate tokens per agent step burns budget and hits rate limits.

---

### The Solution: Neuro-Symbolic Dependency Pruning

Human software engineers don't keep an entire 50,000-line codebase in active working memory to write a single method. They focus strictly on **the functional boundary**:
- What parameters does this function receive?
- What methods are declared on those types?
- What services does it call?

**OntoPrune** acts as a sub-12ms deterministic middleware before the prompt ever touches the neural network:

```
[ Your Multi-File Codebase ]
 (Python, Flutter/Dart, Java, TypeScript)
               │
               ▼ (< 5 ms AST parsing)
[ Semantic Dependency Graph ]
 (Closed-world symbol resolution & deconfliction)
               │
               ▼ (< 3 ms deterministic pruning)
[ Minimal Dependency Contract ]
 (Only the target function + exact invoked signatures)
               │
               ▼
[ Neural Model (Local SLM or Cloud LLM) ]
```

Instead of sending 2,500 lines of implementation logic, OntoPrune passes **clean, typed language stubs** representing strictly the authorized contracts.

---

### Empirical Benchmarks: 4 Languages Tested

We benchmarked OntoPrune across realistic multi-file projects in **Python**, **Dart (Flutter)**, **Java (Spring Boot)**, and **TypeScript (React)**:

| Language & Framework | Full Project Context | OntoPrune Context | Token Reduction | TTFT Speedup |
| :--- | :--- | :--- | :--- | :--- |
| **Python (Async Services)** | 2,815 tokens | **393 tokens** | **-86.0%** | **6.7x faster** |
| **Flutter / Dart (State & UI)** | 1,650 tokens | **135 tokens** | **-91.8%** | **~7x faster** |
| **Java / Spring Boot (@Service)** | 1,450 tokens | **110 tokens** | **-92.4%** | **~7.2x faster** |
| **TypeScript / React (TSX & APIs)** | 1,380 tokens | **105 tokens** | **-92.4%** | **~7.1x faster** |

#### Local CPU Inference Benchmark (Qwen 2.5 Coder 3B on Ollama):

| Metric | Raw Unpruned Prompt | OntoPrune Pruned Prompt | Improvement |
| :--- | :--- | :--- | :--- |
| **Prompt Size** | 2,390 tokens | **406 tokens** | **-83.0%** |
| **Time-to-First-Token (TTFT)** | 22.39 seconds | **3.34 seconds** | **6.7x speedup** |
| **Total Response Time** | 59.91 seconds | **16.46 seconds** | **3.6x faster** |
| **API Hallucinations** | 1 error | **0 errors** | **100% compliant** |

---

### The Format Experiment: Why Natural Language Fails

A common question we received: *"Why not just ask an LLM or summarizer to write a short paragraph explaining the context?"*

We ran a controlled ablation study keeping the underlying pruned dependencies identical, but projecting them into different formats:

1. **`STUBS` (Language-Native Typed Signatures):** 406 tokens | 3.3s TTFT | **0 hallucinations**
2. **`GRAPH` (Relational Assertions):** 817 tokens | 7.0s TTFT | **0 hallucinations**
3. **`JSON` (Key-Value Schema):** 881 tokens | 7.4s TTFT | **4 hallucinations**
4. **`NL` (Natural Language Summary):** 432 tokens | 3.5s TTFT | **7 hallucinations (Severe)**

**Key Takeaway:** Code models are pre-trained on code. When you give them natural language summaries, lexical ambiguity creeps in, and the model starts guessing method names. When you give them **strict, typed code stubs**, hallucinations drop to **zero**.

---

### Closing the Loop: Deterministic Hallucination Verification

Pruning the prompt is only half the battle. How do you ensure the model didn't hallucinate an unauthorized method anyway?

OntoPrune includes a deterministic CLI command and API: `ontoprune check`.

It parses the generated code using Tree-Sitter ASTs, extracts every function invocation, filters framework builtins (like Dart's `notifyListeners` or React's `useState`), and compares them against the authorized contract:

```bash
# Verify model output against the contract:
ontoprune check --file generated_solution.py --contract contract.py
```

If the model called a method that wasn't in the dependency contract, OntoPrune flags it immediately with **100% precision**, without spending extra LLM judge tokens.

---

### How to Use It Today

OntoPrune is written in Python (zero GPU or cloud dependencies) and is open-source under the MIT license.

#### 1. CLI Usage
```bash
pip install ontoprune

# Prune a target function from any project (Python, Dart, Java, TypeScript):
ontoprune prune --file src/services/OrderService.java --func processOrder
```

#### 2. Native Model Context Protocol (MCP) Server
OntoPrune runs as an MCP server for Claude Desktop, Cursor, Gemini, or Antigravity IDE:
```json
{
  "mcpServers": {
    "ontoprune": {
      "command": "ontoprune-mcp"
    }
  }
}
```
Available tools:
- `prune_context(file_path, target_symbol)`
- `verify_response(response_code, contract_or_file)`

---

### Links & Paper
- **Full Whitepaper (PDF):** `paper/ontoprune_whitepaper.pdf`
- **GitHub Repository:** [https://github.com/vigmarcarlo/OntoPrune](https://github.com/vigmarcarlo/OntoPrune)
- **PyPI:** [https://pypi.org/project/ontoprune/](https://pypi.org/project/ontoprune/)

Feedback, benchmarks on your own local models, and PRs are very welcome!
