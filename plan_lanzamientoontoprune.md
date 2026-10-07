# OntoPrune: Plan Maestro de Ingeniería, Publicación y Despliegue (v0.3.0)

*Estrategia técnica para validación de arquitectura neurosimbólica y vinculación de alto impacto con proveedores de infraestructura LLM y herramientas de desarrollo.*

---

## 1. Visión y Objetivos del Despliegue

El propósito de esta fase es consolidar los hallazgos empíricos de **OntoPrune** (Pass@1 del 100%, reducción del $85.1\%$ en $TTFT$ y hasta $92.4\%$ en tokens de entrada), resolver los detalles semánticos pendientes (tipos de dominio y scopes de clase) y posicionar la tecnología directamente frente a líderes técnicos de plataformas críticas (Anthropic, Google Cloud/DeepMind, Cursor y Microsoft/GitHub).

### 1.1 Objetivos de Negocio y Reconocimiento
* **Publicación científica abierta:** Preprint formal en arXiv con identificador persistente.
* **Adopción de ecosistema:** Publicación del servidor en los directorios oficiales del Model Context Protocol (MCP).
* **Validación de industria:** Demostración técnica directa ante ingenieros principales de sistemas de inferencia y optimización de código.

---

## 2. Cronograma y Ruta Crítica

```
SEMANA 1: Consolidación de Ingeniería
├── Implementación de tipos de dominio (dataclasses / Enums)
├── Contexto estructurado de clase para servidor MCP
└── Arnés unificado de benchmarking (`make benchmark`)

SEMANA 2: Empaquetado y Publicación Abierta
├── Release v0.3.0 en GitHub (MIT) y PyPI (`ontoprune`)
├── Registro en Smithery.ai, Glama.ai y repo oficial MCP
└── Envío del preprint formal a arXiv (cs.SE / cs.AI)

SEMANA 3: Alcance Técnico Directo y Demostraciones
├── Divulgación de métricas objetivas (Pass@1, TTFT, Token Delta)
├── Comunicación directa con Staff Engineers y Tech Leads
└── Coordinación de demos técnicas y evaluación de alianzas
```

---

## 3. Especificación de Ajustes de Ingeniería (Fase 1)

### 3.1 Soporte para Tipos de Dominio (`dataclasses` y `Enums`)

#### Problema Identificado
Al aislar métodos con tipos propios de retorno o parámetros complejos (ej. `evaluate_transaction(...) -> RiskAssessment`), el extractor omite la definición de los campos de `RiskAssessment` o las opciones de `RiskLevel`, obligando al modelo neuronal a inferirlos del contexto textual.

#### Solución Técnica
1. **Extensión del AST Visitor (`src/ontoprune/core/parser.py`):**
   * Detectar nodos `ast.ClassDef` decorados con `@dataclass` o que hereden de `enum.Enum`.
   * Registrar sus atributos tipados mediante la propiedad ontológica `soft:hasField` y `soft:hasType`.
2. **Actualización de la Ontología (`ontology/software.ttl`):**
   ```turtle
   soft:DataClass   a owl:Class ; rdfs:subClassOf soft:Class .
   soft:EnumType    a owl:Class ; rdfs:subClassOf soft:Class .
   soft:hasField    a owl:ObjectProperty ; rdfs:domain soft:Class ; rdfs:range soft:Parameter .
   ```
3. **Consulta SPARQL `CONSTRUCT` Extendida:**
   * Al seleccionar el símbolo objetivo, si algún parámetro o tipo de retorno coincide con una clase de dominio del proyecto, incluir automáticamente la definición de su estructura (campos y tipos) en el subgrafo podado.

### 3.2 Formateo con Ámbito de Clase para Clientes MCP

#### Problema Identificado
Clientes de edición como Cursor, Claude Code o Copilot aplican diffs automáticos. Si el stub de un método se entrega aislado sin la firma de su clase contenedora, pueden ocurrir desalineaciones de indentación o ambigüedad sobre la presencia del argumento de instancia (`self`).

#### Solución Técnica
El generador de stubs (`stubs_projector.py`) debe estructurar los métodos dentro de su jerarquía real:
```python
# Contrato podado emitido por ontoprune-mcp
from dataclasses import dataclass
from typing import Optional

@dataclass
class RiskAssessment:
    score: float
    level: str

class TransactionValidator:
    def __init__(self, repository: PaymentRepo) -> None: ...
    
    def evaluate_transaction(self, tx_id: str, amount: float) -> RiskAssessment: ...
```

### 3.3 Automatización del Benchmark (`Makefile`)

Creación de un archivo `Makefile` en la raíz del repositorio para garantizar replicabilidad absoluta con un solo comando:

```makefile
.PHONY: install test benchmark benchmark-cloud check clean

install:
	pip install -e ".[dev]"

test:
	pytest tests/ -v --cov=ontoprune

benchmark:
	python -m ontoprune.benchmark \
		--file fixtures/sample_service.py \
		--func procesar_orden \
		--backend ollama \
		--model qwen2.5-coder:3b \
		--compare-formats

benchmark-cloud:
	python -m ontoprune.benchmark \
		--file fixtures/sample_service.py \
		--func procesar_orden \
		--backend gemini \
		--model gemini-3.8-flash

check:
	ontoprune check --file fixtures/sample_service.py --target procesar_orden
```

---

## 4. Estrategia de Publicación y Presencia en Ecosistemas

### 4.1 Paquetizado en PyPI
* **Nombre de distribución:** `ontoprune`
* **Puntos de entrada de consola:**
  * `ontoprune`: CLI principal para inspección, poda y verificación simbólica (`check`).
  * `ontoprune-mcp`: Servidor de comunicación estándar para clientes compatibles con el Protocolo de Contexto de Modelo.

### 4.2 Registro en el Ecosistema MCP de Anthropic
1. Configuración de manifiesto `smithery.yaml`:
   ```yaml
   name: ontoprune
   version: 0.3.0
   description: High-performance neuro-symbolic context pruning middleware for LLMs.
   runtime: python
   entrypoint: ontoprune.mcp:run_server
   tags:
     - code-intelligence
     - context-pruning
     - neuro-symbolic
     - cost-optimization
   ```
2. Publicación en directorios comunitarios:
   * **Smithery.ai** (`npx -y @smithery/cli publish`)
   * **Glama.ai**
3. Solicitud de incorporación (*Pull Request*) en el repositorio central de servidores MCP (`modelcontextprotocol/servers`) de Anthropic, categorizado como servidor de referencia para optimización de contexto en código.

### 4.3 Envío a arXiv
* **Categorías:** `cs.SE` (Software Engineering) y `cs.AI` (Artificial Intelligence).
* **Título formal:** *Neuro-Symbolic Context Pruning: Collapsing Attention Bottlenecks in Language Models via Ontological Dependency Subgraphs*.
* **Aspectos a destacar en el abstract:**
  * Reducción de tokens de entrada facturables de hasta $92.4\%$.
  * Reducción de latencia $TTFT$ de $85.1\%$ en CPU ($6.7\times$ speedup).
  * $100\%$ de éxito funcional (Pass@1) verificado por tests automáticos.
  * Cero alucinaciones de API mediante stubs de lenguajes tipados.

---

## 5. Protocolo de Comunicación Técnica de Alto Nivel

Para aproximarse a tomadores de decisiones de ingeniería sin intermediarios comerciales o de reclutamiento, se establecen los siguientes lineamientos:

### 5.1 Perfiles Clave por Organización

| Organización | Rol Objetivo | Ángulo de Valor |
|---|---|---|
| **Anthropic** | MCP Core Team / Claude Code Leads | Validación práctica del ecosistema MCP; reducción de costos de inferencia en agentes de software. |
| **Google Cloud / DeepMind** | Staff Software Engineers (Vertex AI Serving / Gemini Developer Experience) | Aumento de densidad y concurrencia por TPU/GPU al descargar la computación de contexto a CPU previa a la atención. |
| **Cursor (Anysphere)** | Founders & Core Systems Architects | Sustitución de embeddings ruidosos por análisis determinista de dependencias de 1 salto en $< 12\text{ ms}$. |
| **Microsoft / GitHub** | Principal Architects (Copilot / Semantic Kernel) | Integración determinista con Tree-Sitter y mitigación de fugas de lógica de negocio. |

### 5.2 Plantilla de Contacto Directo (Email / Mensaje Técnico)

```text
Asunto: OntoPrune: 85% TTFT reduction & 0% API hallucinations via neuro-symbolic context pruning [Open Source]

Estimado [Nombre / Cargo],

Quería compartir con usted y su equipo los resultados de OntoPrune (https://github.com/vigmarcarlo/OntoPrune), un middleware neurosimbólico de código abierto diseñado para colapsar la sobrecarga de atención O(N^2) en modelos de lenguaje orientados a programación.

En lugar de inyectar archivos completos o depender de RAG léxico/vectorial aproximado, OntoPrune utiliza gramáticas nativas de Tree-Sitter y un grafo RDF formal en memoria para aislar el cierre determinista de dependencias (1-hop contract) en < 12 ms sobre CPU.

En benchmarks sistemáticos sobre arquitecturas reales en Python, TypeScript, Java y Dart:
- Reducción del 83.0% al 92.4% en tokens de entrada facturables.
- Reducción del 85.1% en Time-to-First-Token (TTFT) en inferencia local por CPU (de 22.4 s a 3.3 s, aceleración de 6.7x).
- 100% de tasa de éxito funcional (Pass@1) y 0% de alucinaciones de API al proyectar a stubs de lenguajes tipados.
- Servidor Model Context Protocol (MCP) estándar listo para producción.

El whitepaper completo se encuentra disponible como preprint y el arnés de pruebas es 100% reproducible localmente mediante `make benchmark`.

Considerando sus esfuerzos en [Gemini Serving / Claude Code / Cursor Context Engine], me encantaría coordinar una breve conversación técnica o demostración para explorar cómo esta capa de pre-atención puede integrarse en sus pipelines de inferencia.

Atentamente,

Vigmar Carlo
https://github.com/vigmarcarlo/OntoPrune
```

---

## 6. Lista de Verificación para el Lanzamiento

- [ ] Soporte de `dataclasses` y `Enums` validado con tests unitarios en `tests/test_parser.py`.
- [ ] Stubs con preservación de ámbito de clase integrados en `src/ontoprune/mcp/server.py`.
- [ ] Suite de pruebas unitarias y de integración pasando al 100% (`45/45 passed`).
- [ ] Makefile configurado con comandos `benchmark`, `test` y `check`.
- [ ] Documento `ontoprune_paper.md` formateado y listo para arXiv.
- [ ] Servidor MCP publicado en Smithery y referenciado en el README principal.
- [ ] Envío inicial de comunicaciones técnicas directas completado.