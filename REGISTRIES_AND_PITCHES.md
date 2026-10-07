# OntoPrune — Registros MCP & Pitches Técnicos (v0.3.0)

Documento de referencia para la indexación en registros del ecosistema MCP y comunicación con equipos de ingeniería.

---

## PARTE 1: Manifiestos de Registro MCP

### 1. Smithery (`smithery.yaml`) — *Creado y subido al repositorio*
* Ubicación: [`smithery.yaml`](smithery.yaml)
* Para publicar vía CLI:
  1. Obtener clave gratuita en: [https://smithery.ai/account/api-keys](https://smithery.ai/account/api-keys)
  2. Ejecutar en terminal:
     ```bash
     npx -y @smithery/cli publish
     ```
  *(O vincular directamente el repositorio `vigmarcarlo/OntoPrune` en [smithery.ai](https://smithery.ai))*

### 2. Glama (`glama.json`) — *Creado y subido al repositorio*
* Ubicación: [`glama.json`](glama.json)
* Para indexar:
  * Ingresar a [https://glama.ai/mcp/servers](https://glama.ai/mcp/servers) y registrar la URL: `https://github.com/vigmarcarlo/OntoPrune`. Glama detectará automáticamente `glama.json`.

---

## PARTE 2: Pull Request para el Directorio Oficial de Anthropic

* **Repositorio:** [modelcontextprotocol/servers](https://github.com/modelcontextprotocol/servers)
* **Título del PR:**
  ```text
  feat: add OntoPrune (neuro-symbolic code context pruning & IP protection)
  ```
* **Descripción del PR:**
  ```markdown
  ### What does this server do?
  OntoPrune acts as a deterministic context-pruning middleware for Claude Code and coding agents. Using in-memory RDF knowledge graphs and Tree-Sitter, it extracts minimal typed stubs, domain models (dataclasses/Enums), and class enclosures in <12 ms on CPU.

  ### Empirical Validation (2026-10-06):
  - **-60.1% billable input tokens** on modular and clean architecture projects (Gemini & Qwen).
  - **-62% TTFT latency** on local CPU evaluation (AMD Ryzen 5600G with qwen2.5-coder:7b).
  - **100.0% Pass@1 parity** across 24 independent isolated pytest sandboxes.
  - **0 leaked private lines** vs. 74–91 proprietary lines exposed by naive injection.

  - **Repository:** https://github.com/vigmarcarlo/OntoPrune
  - **PyPI Package:** https://pypi.org/project/ontoprune/0.3.0/
  - **License:** MIT
  ```

---

## PARTE 3: Pitches Técnicos Directos

### Contacto 1: Anthropic (Claude Code & MCP Ecosystem)
**Objetivo:** Developer Tooling & MCP Core Team  
**Asunto:** `OntoPrune MCP: 60% context compression, 100% Pass@1 & formal IP protection for Claude Code`  
```text
Hola [Nombre / MCP Core Team],

Desarrollamos OntoPrune (https://github.com/vigmarcarlo/OntoPrune), un servidor MCP neurosimbólico ligero diseñado específicamente para mitigar la saturación de contexto y la fuga de código confidencial en asistentes como Claude Code.

En lugar de volcar módulos monolíticos o depender de RAG léxico con ruido, OntoPrune construye un grafo RDF local en memoria mediante gramáticas nativas de Tree-Sitter y extrae contratos mínimos tipados (cierre semántico de 1 salto + dataclasses/Enums) en <12 ms sobre CPU.

Completamos una evaluación empírica rigurosa (24 sandboxes aislados con pytest):
- Reducción consistente del 60.1% al 60.5% en tokens de entrada en proyectos modulares y Clean Architecture.
- 100.0% de fidelidad funcional (Pass@1 idéntico al contexto completo Naive).
- 0 líneas privadas expuestas frente a 74-91 líneas confidenciales filtradas por el enfoque tradicional.
- Servidor MCP nativo listo para usar en Cursor y Claude Code (`ontoprune-mcp`).

Acabamos de registrar el servidor en los directorios comunitarios y nos encantaría someterlo como caso de referencia oficial de optimización neurosimbólica dentro del ecosistema MCP de Anthropic.

El reporte empírico completo y el repositorio están disponibles bajo MIT: https://github.com/vigmarcarlo/OntoPrune

Saludos cordiales,
Vigmar Carlo
Software Architect & Author of OntoPrune
```

---

### Contacto 2: Google DeepMind / Google Cloud (Gemini Code Assist & Vertex AI Serving)
**Objetivo:** Staff Engineers en ML Systems Efficiency y Developer Ecosystems  
**Asunto:** `Pre-attention context pruning for Gemini: 60% token reduction & 100% Pass@1 verified on gemini-3.8-flash`  
```text
Estimado [Nombre / Gemini Developer Tools Team],

Le escribo para compartir los hallazgos de OntoPrune (https://github.com/vigmarcarlo/OntoPrune), una capa middleware neurosimbólica que actúa como filtro determinista antes de la atención (pre-attention filter) para tareas de síntesis y refactorización de código en Google Gemini.

Evaluamos el pipeline utilizando la API SSE de gemini-3.8-flash sobre arquitecturas de software complejas:
1. Reducción neta del 59.7% al 60.1% en tokens de entrada facturables en proyectos multi-módulo y arquitectura hexagonal.
2. 100.0% de tasa de éxito funcional (Pass@1) verificada en 24 sandboxes independientes con pytest (paridad total con Naive Full Context).
3. 100% de blindaje de propiedad intelectual: cero líneas de algoritmos internos expuestas a la llamada del modelo (frente a 91 líneas privadas enviadas por herramientas convencionales).

Al resolver las relaciones de llamadas e inyectar únicamente stubs tipados y modelos de dominio en <10 ms sobre CPU, la carga en la memoria HBM de los aceleradores disminuye sustancialmente, abriendo la puerta a multiplicar la concurrencia de peticiones en Gemini Code Assist.

Publicamos el código, los benchmarks reproducibles y el whitepaper técnico bajo licencia MIT. Estaré encantado de compartir el harness de evaluación o explorar una integración piloto como proxy de optimización.

Atentamente,
Vigmar Carlo
https://github.com/vigmarcarlo/OntoPrune
```

---

### Contacto 3: Cursor / Anysphere (Fundadores e Ingenieros de Indexación)
**Objetivo:** Aman Sanger, Michael Truell o ingenieros del sistema de contexto/indexación de Cursor  
**Asunto:** `Solving Cursor's context bloat: 60% token savings & 62% TTFT drop via AST-RDF closures (Open Source)`  
```text
Hola [Aman / Michael / Cursor Team],

Construimos OntoPrune (https://github.com/vigmarcarlo/OntoPrune) para atacar un cuello de botella que impacta directamente la latencia y los costos de contexto en agentes de edición de código: el volcado de archivos completos y el ruido de embeddings en bases de código modulares.

OntoPrune reemplaza el RAG heurístico por un grafo ontológico formal en memoria: extrae las firmas tipadas, modelos de dominio (dataclasses/Enums) y el ámbito de clase del método objetivo en <12 ms en CPU.

Acabamos de validar los benchmarks (6C/12T CPU local y cloud SSE):
- -60.1% de tokens de entrada en proyectos modulares y Clean Architecture.
- -62% de latencia TTFT en modelos locales (de 34s a 13s en CPU).
- 100.0% Pass@1 en 24 sandboxes pytest (cero código roto).
- 0 líneas privadas expuestas al modelo (protección total contra fugas de IP corporativa).
- Compatible de forma nativa con Cursor mediante Model Context Protocol (MCP).

Pueden probarlo de inmediato agregando `ontoprune-mcp` a la configuración MCP de Cursor. El código, los arquetipos de prueba y el analizador estadístico están abiertos en GitHub: https://github.com/vigmarcarlo/OntoPrune

¡Me encantaría saber qué opinan!
Vigmar Carlo
```
