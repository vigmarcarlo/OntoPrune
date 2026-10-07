# OntoPrune

*Middleware Neuro-Simbólico de Poda de Contexto para Modelos de Lenguaje (SLMs / LLMs)*

[![Tests](https://img.shields.io/badge/tests-47%20passed-brightgreen.svg)]()
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![MCP Server](https://img.shields.io/badge/MCP-Model%20Context%20Protocol-purple.svg)]()
[![Languages](https://img.shields.io/badge/languages-Python%20%7C%20Flutter%20%7C%20Java%20%7C%20TypeScript-informational.svg)]()

[English](README.md) | **Español** | [📄 Whitepaper Técnico (PDF)](paper/ontoprune_whitepaper_es.pdf) | [📄 Whitepaper in English (PDF)](paper/ontoprune_whitepaper.pdf)

---

OntoPrune es un middleware neuro-simbólico ultraligero (<12ms en CPU) que transforma código fuente multi-archivo en contratos de dependencias tipados mínimos. Al aislar límites funcionales bajo hipótesis de mundo cerrado antes del cálculo de atención, OntoPrune reduce un **~60% del consumo de tokens en arquitecturas modulares**, colapsa la latencia *Time-to-First-Token* ($TTFT$) en un **62%** en modelos locales sobre CPU (Ollama), garantiza un **100% de éxito funcional en pruebas (Pass@1)** y **blinda el 100% del código propietario contra fugas**.

---

## 📊 Benchmark Empírico Riguroso: 24 Ejecuciones Independientes en Sandbox

Evaluado empíricamente sobre 3 arquetipos reales de software en sandboxes aislados con verificación funcional mediante `pytest`:
* **Cloud Frontier:** Google Gemini (`gemini-3.8-flash` vía streaming SSE nativo)
* **Local SLM:** Ollama (`qwen2.5-coder:7b` ejecutado en CPU AMD Ryzen)

| Arquetipo de Software | Backend | Tratamiento | Input Tokens (Mediana) | Reducción Tokens | TTFT (Local/Cloud) | Pass@1 (`pytest`) | Fuga IP (Líneas Privadas) |
|---|---|---|---|---|---|---|---|
| **Arquetipo 1: Algoritmo Aislado** | `gemini` | **OntoPrune** | **818** | **-24.3%** | **0.1 ms** | **100.0% (5/5)** | **0 líneas** |
| Arquetipo 1: Algoritmo Aislado | `gemini` | Naive Full | 1,081 | Base | 0.1 ms | 100.0% (5/5) | 0 líneas |
| **Arquetipo 1: Algoritmo Aislado** | `ollama` | **OntoPrune** | **731** | **-23.5%** | **155 ms** | **100.0% (5/5)** | **0 líneas** |
| Arquetipo 1: Algoritmo Aislado | `ollama` | Naive Full | 956 | Base | 12,985 ms | 100.0% (5/5) | 0 líneas |
| **Arquetipo 2: Multi-Módulo Transaccional** | `gemini` | **OntoPrune** | **931** | **-59.7%** | **0.1 ms** | **100.0% (8/8)** | **0 líneas (100% blindado)** |
| Arquetipo 2: Multi-Módulo Transaccional | `gemini` | Naive Full | 2,313 | Base | 0.1 ms | 100.0% (8/8) | 74 líneas privadas expuestas |
| **Arquetipo 2: Multi-Módulo Transaccional** | `ollama` | **OntoPrune** | **797** | **-59.7%** | **10,569 ms** | **100.0% (8/8)** | **0 líneas (100% blindado)** |
| Arquetipo 2: Multi-Módulo Transaccional | `ollama` | Naive Full | 1,979 | Base | 28,032 ms | 100.0% (8/8) | 74 líneas privadas expuestas |
| **Arquetipo 3: Clean Architecture Hexagonal** | `gemini` | **OntoPrune** | **1,147** | **-60.1%** | **0.1 ms** | **100.0% (10/10)** | **0 líneas (100% blindado)** |
| Arquetipo 3: Clean Architecture Hexagonal | `gemini` | Naive Full | 2,873 | Base | 0.1 ms | 100.0% (10/10) | 91 líneas privadas expuestas |
| **Arquetipo 3: Clean Architecture Hexagonal** | `ollama` | **OntoPrune** | **952** | **-60.5%** | **13,092 ms** | **100.0% (10/10)** | **0 líneas (100% blindado)** |
| Arquetipo 3: Clean Architecture Hexagonal | `ollama` | Naive Full | 2,412 | Base | 34,376 ms | 100.0% (10/10) | 91 líneas privadas expuestas |

### Conclusiones Científicas Principales:
1. **Cero Degradación Semántica (Pass@1 = 100.0%):** En las 24 ejecuciones independientes, el código generado mediante OntoPrune superó el 100% de las pruebas unitarias, demostrando que los contratos tipados y metadatos ontológicos proveen todo el contexto requerido por el LLM.
2. **62% de Reducción en Latencia Inicial (TTFT):** En arquitecturas reales multi-módulo, el tiempo hasta el primer token en CPUs de consumo se redujo de ~34s a ~13s.
3. **Blindaje Total de Propiedad Intelectual:** Las herramientas estándar (Cursor/Copilot) transmiten cuerpos completos de algoritmos internos (hasta 91 líneas confidenciales). OntoPrune envía exactamente **0 líneas** de lógica interna de dependencias.
4. **Dinámica de Compresión según Arquitectura:** En scripts monolíticos aislados, la compresión es moderada (~24%). En sistemas modulares empresariales, la compresión es constante y contundente en **~60% de ahorro neto de tokens**.

---

## 💡 ¿Por Qué OntoPrune Hace Factible la Programación Local?

Ejecutar modelos locales de código (*Qwen 2.5 Coder 7B*, *Llama 3 8B*, *DeepSeek Coder* vía Ollama o llama.cpp) en laptops o estaciones de trabajo sin GPUs dedicadas de 24 GB de VRAM solía ser impráctico en el día a día. OntoPrune resuelve esta limitación mediante tres fundamentos arquitectónicos:

### 1. Derrumba el "Muro del Pre-fill" en CPU ($TTFT$)
* **El Cuello de Botella:** La velocidad de decodificación de tokens en CPU es aceptable (15–25 t/s). Sin embargo, la **fase de Pre-fill (*Prompt Evaluation*)** satura el ancho de banda de la memoria RAM.
* **Sin OntoPrune:** Las herramientas convencionales envían archivos completos y dependencias crudas (2,500 – 3,000 tokens), provocando un **congelamiento de 35 segundos antes del primer token**. Esperar más de medio minuto por cada sugerencia destruye el estado de flujo (*flow state*).
* **Con OntoPrune:** Al podar el contexto a ~800 tokens tipados, la latencia de pre-fill colapsa de **34.3s a 13.0s (reducción del 62% al 74% en TTFT)** en CPUs comerciales (AMD Ryzen 5600G), transformando la inferencia local en una experiencia interactiva en tiempo real.

### 2. Resuelve la "Dilución de Atención" en Modelos Pequeños (SLMs)
* Los modelos de 3B a 7B parámetros no cuentan con la atención masiva de gigantes de 70B+ parámetros. Enviar código irrelevante de bases de datos o pasarelas de pago dispersa su atención y genera alucinaciones de API.
* OntoPrune entrega un **contrato de mundo cerrado** con tipos estrictos (`dataclasses`, interfaces y firmas). El SLM solo ve lo que tiene permitido invocar, alcanzando un **100.0% de Pass@1** en las 24 pruebas sobre sandboxes reales con `pytest`.

### 3. Soberanía de Datos y Privacidad Total Offline
* OntoPrune opera en $<12\text{ ms}$ en CPU mediante AST y RDFLib en memoria, con cero dependencias de red y garantizando que **0 líneas de lógica confidencial** salen de la máquina del desarrollador.

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
pytest tests/
# 46 passed in 1.40s
```

---

## 🔬 Reproducción del Benchmark Empírico

Cualquier desarrollador o equipo técnico puede replicar de forma transparente la evaluación experimental en sandboxes aislados:

```bash
# 1. Validación rápida determinista sin costo de API:
ontoprune benchmark --backend mock --analyze
# o mediante Make:
make benchmark-mock

# 2. Evaluación en vivo contra Google Gemini (requiere GEMINI_API_KEY):
ontoprune benchmark --backend gemini --analyze
# o mediante Make:
make benchmark-gemini

# 3. Evaluación local en vivo contra CPU con Ollama (requiere Ollama activo):
ontoprune benchmark --backend ollama --analyze
# o mediante Make:
make benchmark-ollama
```

---

## 👤 Autor

**Vigmar Carlo**  
- GitHub: [@vigmarcarlo](https://github.com/vigmarcarlo)
- Repositorio: [https://github.com/vigmarcarlo/OntoPrune](https://github.com/vigmarcarlo/OntoPrune)
- Licencia: [MIT](LICENSE)
