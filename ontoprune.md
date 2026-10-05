# OntoPrune: Technical Implementation Specification (v0.1.0-alpha)
*Neuro-Symbolic Context Pruning Middleware for Local SLMs*

---

## 1. Visión y Objetivos del Proyecto

**OntoPrune** es un middleware neurosimbólico ligero diseñado para optimizar el consumo de recursos computacionales (tokens de entrada, latencia $TTFT$ y saturación de memoria) al asistir a modelos de lenguaje pequeños (SLMs) en tareas de análisis y síntesis sobre código fuente.

### 1.1 Objetivos Técnicos Cuantificables
* **Reducción de tokens de entrada:** $\ge 85\%$ comparado con la inyección completa de módulos.
* **Reducción de Time to First Token ($TTFT$):** $\ge 70\%$ al colapsar la matriz de atención de entrada $\mathcal{O}(N^2)$.
* **Sobrecarga de cómputo en CPU:** $\le 15\text{ ms}$ para análisis de AST, ingesta RDF y consulta SPARQL combinadas.
* **Precisión estructural (API Hallucination Rate):** $0\%$ de invocaciones a métodos o parámetros inexistentes en el subgrafo de dependencias.

---

## 2. Arquitectura del Sistema

```
                      [Código Fuente Python (.py)]
                                   │
                                   ▼
                   ┌───────────────────────────────┐
                   │       AST Parser Engine       │
                   │    (Python `ast` / Visitor)   │
                   └───────────────────────────────┘
                                   │
                                   ▼ (Tripletas RDF)
                   ┌───────────────────────────────┐
                   │    In-Memory Triplestore      │
                   │   (`rdflib` / `oxigraph`)     │
                   └───────────────────────────────┘
                                   │
                    [Target Function / Symbol ID]
                                   │
                                   ▼
                   ┌───────────────────────────────┐
                   │    SPARQL Pruning Engine      │
                   │      (CONSTRUCT Query)        │
                   └───────────────────────────────┘
                                   │
                                   ▼ (Subgrafo Podado Turtle: < 200 tokens)
                   ┌───────────────────────────────┐
                   │    Structured Prompt Builder  │
                   └───────────────────────────────┘
                                   │
                                   ▼
                   ┌───────────────────────────────┐
                   │     Local SLM Inference       │
                   │   (Ollama / `llama.cpp` API)  │
                   └───────────────────────────────┘
                                   │
                                   ▼
                    [Salida Verificada y Métricas]
```

---

## 3. Estructura de Archivos del Proyecto

```
ontoprune/
├── pyproject.toml              # Dependencias y metadata del paquete
├── README.md                   # Documentación rápida y badges
├── ontology/
│   └── software.ttl            # Definición formal RDFS/OWL del vocabulario
├── src/
│   └── ontoprune/
│       ├── __init__.py
│       ├── core/
│       │   ├── parser.py       # Visitor AST -> Tripletas RDF
│       │   ├── graph.py        # Gestor de Triplestore en memoria y SPARQL
│       │   └── pruner.py       # Lógica de extracción de subgrafos
│       ├── client/
│       │   └── slm.py          # Cliente HTTP para Ollama / llama.cpp
│       └── benchmark/
│           ├── runner.py       # Orquestador del benchmark comparativo
│           └── metrics.py      # Colector de métricas (TTFT, tokens, ms)
├── fixtures/
│   └── sample_service.py       # Archivo de prueba realista (200-400 LOC)
└── tests/
    ├── test_parser.py
    ├── test_pruner.py
    └── test_benchmark.py
```

---

## 4. Ontología Base (`ontology/software.ttl`)

Vocabulario declarativo mínimo para modelar contratos de software:

```turtle
@prefix rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix owl:  <http://www.w3.org/2002/07/owl#> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .
@prefix soft: <https://w3id.org/ontoprune/software#> .

# Clases Principales
soft:Module     a owl:Class ; rdfs:label "Module" .
soft:Class      a owl:Class ; rdfs:label "Class" .
soft:Function   a owl:Class ; rdfs:label "Function or Method" .
soft:Parameter  a owl:Class ; rdfs:label "Parameter" .

# Propiedades Estructurales
soft:containsClass    a owl:ObjectProperty ; rdfs:domain soft:Module ;   rdfs:range soft:Class .
soft:containsFunction a owl:ObjectProperty ; rdfs:domain soft:Module ;   rdfs:range soft:Function .
soft:hasMethod        a owl:ObjectProperty ; rdfs:domain soft:Class ;    rdfs:range soft:Function .
soft:inheritsFrom     a owl:ObjectProperty ; rdfs:domain soft:Class ;    rdfs:range soft:Class .
soft:hasParameter     a owl:ObjectProperty ; rdfs:domain soft:Function ; rdfs:range soft:Parameter .

# Dependencias e Invocaciones
soft:invokes          a owl:ObjectProperty ; rdfs:domain soft:Function ; rdfs:range soft:Function .

# Propiedades Literales
soft:hasType          a owl:DatatypeProperty ; rdfs:range xsd:string .
soft:returnsType      a owl:DatatypeProperty ; rdfs:range xsd:string .
```

---

## 5. Especificación de Componentes Críticos

### 5.1 AST Parser y Generador de Tripletas (`src/ontoprune/core/parser.py`)

* **Entrada:** Código fuente Python como string o archivo en disco.
* **Procesamiento:** `ast.NodeVisitor` recorriendo nodos `ClassDef`, `FunctionDef`, `arg`, `Call`.
* **Salida:** `rdflib.Graph` poblado con URIs canónicas bajo el prefijo `repo:`.

**Reglas de Mapeo Semántico:**
1. Cada función genera URI: `repo:func_{func_name}`.
2. Cada parámetro genera URI: `repo:param_{func_name}_{param_name}`.
3. Si un nodo `Call` coincide con un identificador local o importado, se emite `(repo:func_X, soft:invokes, repo:func_Y)`.
4. Los tipos de retorno (`returns`) y anotaciones de argumentos se guardan como literales en `soft:returnsType` y `soft:hasType`.

---

### 5.2 Motor de Poda Semántica (`src/ontoprune/core/pruner.py`)

Aísla formalmente el vecindario de dependencias de la función consultada mediante una consulta SPARQL `CONSTRUCT`:

```sparql
PREFIX soft: <https://w3id.org/ontoprune/software#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

CONSTRUCT {
    ?target a soft:Function ;
            rdfs:label ?targetName ;
            soft:belongsToClass ?className ;
            soft:returnsType ?returnType ;
            rdfs:comment ?docstring ;
            soft:hasParameter ?param ;
            soft:invokes ?callee .

    ?param rdfs:label ?paramName ;
           soft:hasType ?paramType .

    ?callee a soft:Function ;
            rdfs:label ?calleeName ;
            soft:returnsType ?calleeReturn .
}
WHERE {
    VALUES ?target { <TARGET_FUNCTION_URI> }
    ?target rdfs:label ?targetName .

    OPTIONAL { ?cls soft:hasMethod ?target ; rdfs:label ?className . }
    OPTIONAL { ?target soft:returnsType ?returnType . }
    OPTIONAL { ?target rdfs:comment ?docstring . }

    OPTIONAL {
        ?target soft:hasParameter ?param .
        ?param rdfs:label ?paramName .
        OPTIONAL { ?param soft:hasType ?paramType . }
    }

    OPTIONAL {
        ?target soft:invokes ?callee .
        ?callee rdfs:label ?calleeName .
        OPTIONAL { ?callee soft:returnsType ?calleeReturn . }
    }
}
```

---

### 5.3 Inferencia y Conexión con SLM (`src/ontoprune/client/slm.py`)

* **Endpoint objetivo predeterminado:** `http://localhost:11434/api/generate` (Ollama API estándar).
* **Parámetros de generación:**
  * `model`: `"qwen2.5-coder:3b"`, `"llama3.2:3b"`, o `"phi3.5:latest"`.
  * `temperature`: `0.0` (o `0.1`) para garantizar determinismo estricto.
  * `stream`: `True` para capturar el tiempo exacto del primer token emitido ($TTFT$).
  * `seed`: `42`.

---

### 5.4 Módulo de Benchmarking (`src/ontoprune/benchmark/runner.py`)

El ejecutor ejecuta dos experimentos concurrentes o secuenciales sobre la misma función objetivo:

```
[Experimento 1: Naive Full Context]
Prompt = "Código completo del archivo (300+ líneas) + Tarea"

[Experimento 2: OntoPrune]
1. t0 = perf_counter()
2. Grafo = Parse(AST)
3. Subgrafo = SPARQL_Construct(target_func)
4. t_prep = perf_counter() - t0
Prompt = "Subgrafo Turtle (< 200 tokens) + Tarea"
```

#### Métricas registradas
* $T_{\text{prep}}$: Tiempo de preparación en CPU (ms).
* $N_{\text{in}}$: Tokens de entrada calculados por el motor o tokenizer.
* $TTFT$: Tiempo hasta el primer chunk recibido del stream (ms).
* $T_{\text{total}}$: Duración completa de la inferencia (ms).
* $N_{\text{out}}$: Tokens emitidos.
* **Integridad Semántica:** Detección booleana de llamadas a funciones fuera del contrato provisto.

---

## 6. Fixture de Código de Prueba (`fixtures/sample_service.py`)

El archivo de evaluación debe contener complejidades de producción:
* Servicios de órdenes y facturación con dependencias cruzadas.
* Herencia simple de clases base (`BaseService`, `Repository`).
* Mínimo 250 líneas de código para evidenciar el contraste entre ~3,500 tokens del archivo completo vs. ~150 tokens del subgrafo podado.

---

## 7. Interfaz CLI y Formato de Salida

Comando de ejecución:
```bash
python -m ontoprune.benchmark --file fixtures/sample_service.py --func procesar_orden --model qwen2.5-coder:3b
```

Formato del reporte emitido en `stdout`:
```text
================================================================================
                    ONTOPRUNE - BENCHMARK REPORT (v0.1.0)
================================================================================
Target Symbol : OrderService.procesar_orden
Engine Model  : qwen2.5-coder:3b (via Ollama Local)
Host Device   : CPU / Local VRAM
--------------------------------------------------------------------------------

METRIC                     NAIVE PIPELINE       ONTOPRUNE            DELTA
--------------------------------------------------------------------------------
CPU Overhead               0.25 ms (File read)  6.12 ms (AST+SPARQL) +5.87 ms
Input Tokens               3,280 tokens         138 tokens           -95.79%
Time to First Token (TTFT) 2,120 ms             112 ms               -94.71% (18.9x)
Total Execution Time       4,850 ms             1,340 ms             -72.37%
Output Tokens              340 tokens           310 tokens           -8.82%
Hallucinated API Calls     1 invalid method     0 invalid methods    100% Valid
--------------------------------------------------------------------------------

[SUMMARY]
OntoPrune saved 3,142 input tokens and reduced TTFT by 2.00 seconds with an
overhead of only 6.1 milliseconds on CPU.
================================================================================
```

---

## 8. Criterios de Aceptación para Materialización

1. **Autocontenido:** La librería debe poder instalarse con `pip install -e .` requiriendo únicamente `rdflib>=7.0.0` y `requests>=2.31.0` (o `httpx`).
2. **Determinismo:** Correr el benchmark 5 veces seguidas con el mismo seed debe mantener una varianza en tokens de entrada igual a $0$.
3. **Robustez de AST:** No debe fallar ante decoradores de funciones (`@dataclass`, `@property`, `@staticmethod`).
4. **Independencia de GPU para el middleware:** El parseo y la consulta SPARQL no deben tocar la GPU ni requerir llamadas a red externas.