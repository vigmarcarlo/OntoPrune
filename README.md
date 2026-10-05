# OntoPrune

*Neuro-Symbolic Context Pruning Middleware for Local SLMs*

OntoPrune es un middleware traductor ligero que transforma código fuente en contratos de contexto mínimos utilizando representación ontológica (RDF/SPARQL), reduciendo drásticamente los tokens de entrada y la latencia TTFT (Time to First Token) para modelos de lenguaje pequeños (SLMs) y evitando alucinaciones de API.

---

## Resultados Empíricos (Benchmark en CPU)

Evaluación real con streaming sobre [sample_service.py](fixtures/sample_service.py) (300+ LOC) en CPU local (12 cores):

| Métrica | Naive (Archivo Completo) | OntoPrune (`stubs`) | Ganancia Real |
|---|---|---|---|
| **Sobrecarga CPU** | 0.02 ms | **9.9 ms** | $\le 10\text{ ms}$ (Meta: $\le 15\text{ ms}$) |
| **Tokens Entrada** | 2,390 tokens | **406 tokens** | **-83.0%** ($\approx 6\text{x}$ menos) |
| **TTFT (`qwen2.5-coder:3b`)** | 22.4 s | **3.3 s** | **6.7x más rápido** (ahorra 19.1 s) |
| **Tiempo Total (3B)** | 59.9 s | **16.5 s** | **-72.5%** ($3.6\text{x}$ más rápido) |
| **Alucinaciones API** | 1 método inválido | **0 métodos inválidos** | **100% Precisión Contractual** |

---

## Instalación

```bash
pip install -e .

# Con dependencias para benchmarking:
pip install -e ".[dev,benchmark]"
```

---

## Modos de Uso

### 1. Como Servidor MCP (Model Context Protocol)

OntoPrune incluye un servidor MCP nativo (`ontoprune-mcp`) para integrarse con Cursor, Claude Desktop, Gemini CLI o cualquier agente:

```bash
# Ejecutar servidor MCP en transporte stdio:
ontoprune-mcp
```

**Configuración en `claude_desktop_config.json` o similar:**
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
- `prune_context(file_path, target_symbol, format='stubs', include_body=False, project_root=None)`: Extrae el contrato podado mínimo (< 400 tokens) resolviendo dependencias entre múltiples archivos del proyecto.
- `verify_response(response_code, contract_or_file, target_symbol)`: Detecta alucinaciones en código generado comparando contra el contrato o archivo.

---

### 2. Como Librería Python

```python
import ontoprune

# 1. Traducir un archivo a contexto compacto podado (formato stubs)
# Resuelve automáticamente imports relativos y absolutos entre módulos del proyecto
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
    print("Código 100% válido")
```

---

### 3. Desde la Línea de Comandos (CLI & Pipes)

```bash
# Traducir función en proyectos multi-módulo:
ontoprune translate services/order_service.py procesar_orden --format stubs

# Pipeline directo con Ollama en proyectos modulares:
ontoprune translate services/order_service.py procesar_orden | ollama run qwen2.5-coder:3b
```

---

### 4. Ejecución del Benchmark Empírico

```bash
# Correr benchmark comparativo (Naive vs OntoPrune con ablación de formatos):
python -m ontoprune.benchmark --file fixtures/sample_service.py --func procesar_orden --backend ollama --model qwen2.5-coder:3b --compare-formats
```

---

## Modelos de Monetización y Aplicación Comercial

OntoPrune resuelve dos problemas críticos de costo y confiabilidad en ingeniería de IA:

### 1. Token Cost Optimization Gateway (B2B SaaS / Middleware de Ahorro)
- **Problema:** Equipos que operan agentes de código autónomos (Devin, Cursor, Copilot Workspace) gastan miles de dólares mensuales en tokens de entrada donde más del 80% es código irrelevante.
- **Solución:** OntoPrune como proxy o sidecar que poda el contexto antes de enviarlo a APIs comerciales (Gemini, Claude, OpenAI), reduciendo la factura de tokens en un **85%**.
- **Monetización:** Cobro basado en porcentaje de ahorro (*gain-share*: ej. 10% del ahorro mensual generado).

### 2. Local-First Developer Tooling (Edición Profesional / Equipos)
- **Problema:** Desarrolladores y empresas que requieren privacidad estricta ejecutan SLMs en laptops o servidores locales (Ollama/vLLM), sufriendo latencias inaceptables en CPU.
- **Solución:** OntoPrune reduce el TTFT de 22s a 3.3s (6.7x más rápido).
- **Monetización:** Versión open-source para desarrolladores individuales + licencia empresarial para equipos (soporte multi-repositorio, telemetría y reglas de cumplimiento de arquitectura).

### 3. Agent Compliance & CI/CD Security Gate
- **Problema:** Los agentes de código alucinan APIs y rompen contratos de software en producción.
- **Solución:** `ontoprune check` como paso automatizado en GitHub Actions / GitLab CI que bloquea pull requests con llamadas no autorizadas al grafo del sistema.
- **Monetización:** Modelo SaaS de auditoría y seguridad para código generado por agentes.
