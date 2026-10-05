# OntoPrune

*Middleware Neuro-Simbólico de Poda de Contexto para Modelos de Lenguaje (SLMs / LLMs)*

[![Tests](https://img.shields.io/badge/tests-45%20passed-brightgreen.svg)]()
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![MCP Server](https://img.shields.io/badge/MCP-Model%20Context%20Protocol-purple.svg)]()
[![Languages](https://img.shields.io/badge/languages-Python%20%7C%20Flutter%20%7C%20Java%20%7C%20TypeScript-informational.svg)]()

[English](README.md) | **Español** | [📄 Whitepaper Técnico (PDF)](paper/ontoprune_whitepaper_es.pdf) | [📄 Whitepaper in English (PDF)](paper/ontoprune_whitepaper.pdf)

---

OntoPrune es un middleware ultraligero (<12ms en CPU) que transforma código fuente en contratos de contexto mínimos utilizando representación de dependencias de mundo cerrado. Reduce drásticamente los tokens de entrada (hasta un **92.4%**) y colapsa la latencia TTFT (*Time-to-First-Token*, **6.7x más rápido**) en modelos de lenguaje pequeños (SLMs) y frontier models, eliminando por completo las alucinaciones de API.

---

## 🚀 Resultados Empíricos Multi-Lenguaje

Evaluación real sobre proyectos modulares en cuatro ecosistemas de software:

| Ecosistema | Contexto Crudo | OntoPrune (`stubs`) | Reducción de Tokens | Aceleración Estimada |
|---|---|---|---|---|
| **Python** (Servicios Asíncronos) | 2,815 tokens | **393 tokens** | **-86.0%** | **6.7x más rápido** |
| **Flutter / Dart** (UI y Estado) | 1,650 tokens | **135 tokens** | **-91.8%** | **~7x más rápido** |
| **Java / Spring Boot** (Enterprise) | 1,450 tokens | **110 tokens** | **-92.4%** | **~7.2x más rápido** |
| **TypeScript / React** (Frontend/API) | 1,380 tokens | **105 tokens** | **-92.4%** | **~7.1x más rápido** |

### Benchmark de Inferencia en CPU Local (Qwen 2.5 Coder 3B vía Ollama)

| Métrica | Naive (Archivo Completo) | OntoPrune (`stubs`) | Ganancia Real |
|---|---|---|---|
| **Sobrecarga CPU** | 0.02 ms | **9.9 ms** | $\le 10\text{ ms}$ (Meta: $\le 15\text{ ms}$) |
| **Tokens de Entrada** | 2,390 tokens | **406 tokens** | **-83.0%** ($\approx 6\text{x}$ menos) |
| **TTFT (Time-to-First-Token)** | 22.4 s | **3.3 s** | **6.7x más rápido** (ahorra 19.1 s) |
| **Tiempo Total de Generación** | 59.9 s | **16.5 s** | **-72.5%** ($3.6\text{x}$ más rápido) |
| **Alucinaciones de API** | 1 método inválido | **0 métodos inválidos** | **100% Precisión Contractual** |

---

## 📦 Instalación

```bash
# Instalación estándar:
pip install ontoprune

# Con soporte multi-lenguaje (Flutter/Dart, Java, TypeScript vía Tree-sitter):
pip install "ontoprune[languages]"

# Para desarrollo y pruebas:
pip install "ontoprune[dev,benchmark,languages]"
```

---

## 🌐 Soporte Multi-Lenguaje Universal

OntoPrune detecta automáticamente el lenguaje y genera contratos tipados nativos:

| Lenguaje | Extensión | Motor AST | Formato de Salida |
|---|---|---|---|
| **Python** | `.py` | Python `ast` nativo | `def nombre(args) -> Ret: ...` |
| **Flutter / Dart** | `.dart` | `tree-sitter-dart` | `abstract class ... { Ret metodo(); }` |
| **Java / Spring Boot** | `.java` | `tree-sitter-java` | `public interface ... { Ret metodo(); }` |
| **TypeScript / React** | `.ts`, `.tsx`, `.js` | `tree-sitter-typescript` | `export interface ... { metodo(): Ret; }` |

---

## 🛠️ Modos de Uso

### 1. Como Servidor MCP (Model Context Protocol)

OntoPrune incluye un servidor MCP nativo (`ontoprune-mcp`) para conectarse con Claude Desktop, Cursor, Gemini o Antigravity:

```bash
ontoprune-mcp
```

**Configuración en `claude_desktop_config.json`:**
```json
{
  "mcpServers": {
    "ontoprune": {
      "command": "ontoprune-mcp"
    }
  }
}
```

**Herramientas MCP expuestas:**
- `prune_context(file_path, target_symbol, format='stubs')`: Extrae el contrato mínimo resolviendo dependencias entre múltiples archivos.
- `verify_response(response_code, contract_or_file)`: Detecta alucinaciones en código generado comparándolo contra el contrato.

---

### 2. Desde la Línea de Comandos (CLI)

```bash
# Podar una función objetivo en proyectos multi-archivo:
ontoprune translate src/services/OrderService.java processOrder --format stubs

# Pipeline directo con Ollama:
ontoprune translate services/order_service.py procesar_orden | ollama run qwen2.5-coder:3b

# Verificar determinísticamente si una respuesta de un LLM alucina métodos:
ontoprune check --file respuesta_llm.py --contract contrato.py
```

---

### 3. Como Librería Python

```python
import ontoprune

# 1. Extraer contrato de contexto compacto (formato stubs)
context = ontoprune.translate(
    "services/order_service.py",
    target="procesar_orden",
    fmt="stubs",
    multi_module=True,
)
print(context)

# 2. Verificar respuestas del modelo frente al contrato
violations = ontoprune.check(llm_code_response, against=context)
if not violations:
    print("Código 100% válido y libre de alucinaciones")
```

---

## 🧪 Pruebas Automatizadas

```bash
uv run pytest
# 45 passed in 1.19s
```

---

## 👤 Autor

**Vigmar Carlo**  
- GitHub: [@vigmarcarlo](https://github.com/vigmarcarlo)
- Repositorio: [https://github.com/vigmarcarlo/OntoPrune](https://github.com/vigmarcarlo/OntoPrune)
- Licencia: [MIT](LICENSE)
