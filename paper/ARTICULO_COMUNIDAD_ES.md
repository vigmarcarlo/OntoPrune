# Cómo Redujimos el 90% de Tokens de Contexto y Aceleramos el TTFT 6.7x en LLMs de Código (Python, Flutter, Java y TypeScript)

**TL;DR:** Cuando le pedimos a un LLM escribir o refactorizar código, pasarle archivos enteros con cientos de líneas genera una latencia de atención cuadrática ($\mathcal{O}(N^2)$), congelamientos de más de 20 segundos en modelos locales pequeños (SLMs) y alucinaciones frecuentes de métodos. Creamos **OntoPrune**, un middleware de código abierto (<12ms en CPU) que extrae de forma determinista el contrato de dependencias mínimo de cualquier función en proyectos multi-archivo. En Python, Flutter/Dart, Java/Spring Boot y TypeScript/React, reduce los tokens del prompt entre **83% y 92%**, acelera el Time-to-First-Token **6.7x** en modelos locales y elimina por completo las alucinaciones de API.

---

### La Frustración: ¿Por Qué Dar Más Contexto Resulta Peor?

Si trabajas con modelos de código —ya sea localmente con Ollama (`qwen2.5-coder`, `llama-3.2`) o mediante APIs en la nube (`gemini-2.5-flash`, `claude-3-5-sonnet`)— probablemente has vivido esto:

Le pides al modelo implementar una prueba unitaria o refactorizar una sola función:
```python
def procesar_orden(orden_id: str, repo: OrderRepository) -> Order:
    ...
```

Para darle "contexto", los editores o prompts suelen inyectar:
- El archivo del servicio completo (500 a 800 líneas).
- Todos los archivos importados, cabeceras y modelos de datos.
- Clases auxiliares y utilitarios de base de datos que la función ni siquiera toca.

#### Los Tres Cuellos de Botella que Esto Detona:

1. **Saturación de Atención ($\mathcal{O}(N^2)$):**
   En laptops o servidores sin tarjetas gráficas masivas, procesar un prompt de 3,000 tokens llena la memoria de atención (*KV-cache*). En modelos de 3B parámetros ejecutados en CPU, puedes esperar **entre 20 y 25 segundos** solo para ver el *primer token emitido* (*Time-to-First-Token* / TTFT).
2. **Pérdida de Precisión y Alucinaciones:**
   Al ver decenas de clases en el prompt, el modelo confunde métodos con nombres parecidos (por ejemplo, llama a `repo.guardar_en_bd()` en vez de `repo.guardar()`), o inventa métodos que jamás existieron en el proyecto.
3. **Costos Innecesarios en la Nube:**
   Enviar miles de tokens de relleno en cada paso de un agente devora presupuestos y agota los límites de tasa de la API.

---

### La Solución: Poda Neuro-Simbólica de Dependencias

Un desarrollador humano no carga en su memoria de trabajo un proyecto de 50,000 líneas para retocar una función. Se enfoca estrictamente en **la frontera funcional**:
- ¿Qué parámetros recibe la función?
- ¿Qué métodos declaran esos tipos?
- ¿Qué servicios externos invoca?

**OntoPrune** opera como un middleware que toma menos de 12 milisegundos en CPU antes de que el prompt toque el modelo:

```
[ Código Fuente del Proyecto ]
 (Python, Flutter/Dart, Java, TypeScript)
               │
               ▼ (< 5 ms análisis sintáctico AST)
[ Grafo de Dependencias Semánticas ]
 (Resolución estricta de símbolos de mundo cerrado)
               │
               ▼ (< 3 ms poda determinista)
[ Contrato Mínimo de Dependencias ]
 (Solo la función objetivo + las firmas exactas invocadas)
               │
               ▼
[ Modelo de Lenguaje (SLM Local o Cloud LLM) ]
```

En lugar de enviarle 2,500 líneas de código, OntoPrune entrega **stubs de código tipado limpios y compactos** con las firmas exactas autorizadas.

---

### Benchmarks Reales en 4 Lenguajes

Evaluamos OntoPrune en proyectos reales estructurados en múltiples archivos:

| Lenguaje y Framework | Contexto Completo | Contexto con OntoPrune | Reducción de Tokens | Aceleración Estimada |
| :--- | :--- | :--- | :--- | :--- |
| **Python (Servicios Asíncronos)** | 2,815 tokens | **393 tokens** | **-86.0%** | **6.7x más rápido** |
| **Flutter / Dart (UI y Estado)** | 1,650 tokens | **135 tokens** | **-91.8%** | **~7x más rápido** |
| **Java / Spring Boot (@Service)** | 1,450 tokens | **110 tokens** | **-92.4%** | **~7.2x más rápido** |
| **TypeScript / React (TSX y API)** | 1,380 tokens | **105 tokens** | **-92.4%** | **~7.1x más rápido** |

#### Benchmark de Inferencia en CPU Local (Qwen 2.5 Coder 3B vía Ollama):

| Métrica | Prompt Crudo Completo | Prompt Podado con OntoPrune | Mejora |
| :--- | :--- | :--- | :--- |
| **Tamaño del Prompt** | 2,390 tokens | **406 tokens** | **-83.0%** |
| **Tiempo al Primer Token (TTFT)** | 22.39 segundos | **3.34 segundos** | **6.7x de aceleración** |
| **Tiempo Total de Generación** | 59.91 segundos | **16.46 segundos** | **3.6x más rápido** |
| **Alucinaciones de API** | 1 error | **0 errores** | **100% de precisión** |

---

### El Experimento de Formatos: ¿Por Qué el Lenguaje Natural Falló?

Una duda recurrente fue: *"¿Por qué no pedirle a un modelo que resuma el contexto en un párrafo en lenguaje natural?"*

Hicimos una prueba de ablación controlada manteniendo exactamente las mismas dependencias podadas, pero representándolas en cuatro formatos distintos:

1. **`STUBS` (Firmas de Código Tipado):** 406 tokens | 3.3s TTFT | **0 alucinaciones (Óptimo)**
2. **`GRAFO` (Relaciones Simbólicas):** 817 tokens | 7.0s TTFT | **0 alucinaciones**
3. **`JSON` (Esquema Clave-Valor):** 881 tokens | 7.4s TTFT | **4 alucinaciones**
4. **`NL` (Resumen en Lenguaje Natural):** 432 tokens | 3.5s TTFT | **7 alucinaciones (Severo)**

**Conclusión clave:** Los modelos de código fueron entrenados con código. Las explicaciones en lenguaje natural introducen ambigüedad léxica y el modelo empieza a adivinar nombres de métodos. Con **stubs de código tipado**, las alucinaciones desaparecen por completo.

---

### Cerrando el Ciclo: Verificación Determinista de Alucinaciones

Podar el prompt es el primer paso. ¿Cómo asegurarse de que el código generado no inventó métodos no autorizados?

OntoPrune incluye un comando determinista de validación: `ontoprune check`.

Analiza el código generado usando árboles sintácticos (Tree-Sitter), extrae cada llamada a función, filtra los métodos nativos del framework (como `notifyListeners` en Flutter o `useState` en React) y los compara con el contrato autorizado:

```bash
# Valida la salida del modelo contra el contrato:
ontoprune check --file solucion_generada.py --contract contrato.py
```

Si el modelo usó un método fuera del contrato, OntoPrune lo detecta con **100% de precisión en milisegundos**, sin gastar llamadas extra a otro LLM para evaluar la respuesta.

---

### Cómo Probarlo

OntoPrune está desarrollado en Python (sin dependencias de GPU ni de red) y es de código abierto con licencia MIT.

#### 1. Uso desde la Terminal (CLI)
```bash
pip install ontoprune

# Podar una función objetivo en cualquier lenguaje:
ontoprune prune --file src/services/OrderService.java --func processOrder
```

#### 2. Servidor Nativo Model Context Protocol (MCP)
Se conecta directamente a clientes compatibles con MCP (Claude Desktop, Cursor, Gemini, Antigravity IDE):
```json
{
  "mcpServers": {
    "ontoprune": {
      "command": "ontoprune-mcp"
    }
  }
}
```
Herramientas expuestas:
- `prune_context(file_path, target_symbol)`
- `verify_response(response_code, contract_or_file)`

---

### Enlaces y Recursos
- **Whitepaper Técnico Completo (PDF):** `paper/ontoprune_whitepaper_es.pdf`
- **Repositorio en GitHub:** [https://github.com/vigmarcarlo/OntoPrune](https://github.com/vigmarcarlo/OntoPrune)
- **PyPI:** [https://pypi.org/project/ontoprune/](https://pypi.org/project/ontoprune/)
