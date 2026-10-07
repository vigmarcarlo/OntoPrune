# RFC: Contexto Jerárquico Multiescala para OntoPrune (v0.4.0)
**Especificación de Requerimientos: Emulando el Modelo Cognitivo del Programador Humano**

* **Autor:** Vigmar Carlo
* **Fecha:** 7 de Octubre, 2026
* **Estado:** Propuesta de Diseño / En Revisión
* **Objetivo:** Evolucionar el motor de poda de OntoPrune desde un corte estático 1-hop hacia un **Contexto Jerárquico Multiescala (Árbol + Outline Estructural + Foco)** que permita a los asistentes de IA asociar nuevas clases, desasociar código obsoleto y heredar capacidades reales sin saturar la ventana de atención.

---

## 1. Motivación y Diagnóstico del Problema

### 1.1 El fallo del "1-Hop Estático"
La versión actual de OntoPrune (0.3.0) extrae de forma impecable las dependencias existentes que una función ya invoca. Sin embargo, en el desarrollo real de software:
* **El código nuevo requiere nuevas asociaciones:** Si un desarrollador desea agregar una nueva funcionalidad (por ejemplo, validación de descuentos en una factura), la clase `DescuentoService` **aún no está invocada en el código**. Si el extractor solo mira llamadas pasadas, la IA no sabe que `DescuentoService` existe.
* **El código a modificar requiere desasociar:** Para refactorizar o desacoplar, la IA necesita conocer el catálogo de componentes del subsistema para sustituirlos.
* **La Herencia es un punto ciego:** En Clean Architecture / DDD, las clases heredan de `BaseAction`, `BaseRepository` o `UseCase`. El modelo necesita saber qué atributos y métodos le proporciona la clase base en `self`.

### 1.2 El Modelo Mental del Programador en el IDE
Un desarrollador en su entorno de trabajo interactúa con tres niveles de abstracción simultáneos:
1. **El Árbol del Subsistema (File Explorer):** Entiende qué archivos y componentes componen el módulo o feature.
2. **El Menú de Capacidades (Symbol Outline):** Ve las clases, métodos y campos del módulo sin sus implementaciones internas (`...`). Esto le permite saber qué piezas tiene disponibles para conectar.
3. **El Foco Quirúrgico (Editor):** Mantiene el cuerpo de código completo únicamente para el método o clase donde tiene el cursor.

---

## 2. Especificación de Ajustes Requeridos

### Ajuste 1: Resolución y Exposición de Clases Padre (Inheritance Resolution)
* **Requerimiento:** Cuando el objetivo a podar sea un método de una clase o la clase misma, OntoPrune debe identificar la jerarquía de herencia (`node.bases`).
* **Alcance:**
  1. Soporte para clases base locales y clases base importadas inter-módulo (e.g. `class EmitirFactura(BaseAction):`).
  2. Modelado explícito en el grafo RDF: `soft:inheritsFrom` vinculando la clase hija con la clase padre.
  3. Extracción de los miembros públicos y protegidos de la clase padre (`atributos`, `métodos`, `firmas`).
  4. Renderizado en el stub Python:
     ```python
     # --- Inherited Base Class & Available Members ---
     class BaseAction:
         db: Session
         logger: Logger
         def validar_permisos(self, usuario_id: str) -> bool: ...

     # --- Target Class ---
     class EmitirFactura(BaseAction):
         def execute(self, req: FacturaRequest) -> FacturaResponse:
             ...
     ```

---

### Ajuste 2: Extractor de Outline Estructural del Subsistema (Structural Outlines)
* **Requerimiento:** Capacidad de extraer el esqueleto estructural (clases, signaturas de métodos, campos tipados con cuerpos omitidos `...`) de los archivos que componen el subsistema o módulo de la funcionalidad.
* **Alcance:**
  1. No incluye implementaciones privadas ni lógica interna.
  2. Actúa como el **"menú de capacidades disponibles"**: permite a la IA descubrir servicios, repositorios o colaboradores hermanos que aún no están conectados pero que el ajuste requiere asociar.
  3. Renderizado compacto:
     ```python
     # [OUTLINE: Available Subsystem Collaborators]
     # src/domain/services/descuentos.py
     class DescuentoService:
         def calcular_descuento(self, monto: float, cupon: str) -> float: ...
         def validar_cupon(self, cupon: str) -> bool: ...
     ```

---

### Ajuste 3: Árbol Jerárquico del Módulo / Feature (Subsystem File Tree)
* **Requerimiento:** Representación espacial compacta de los archivos directamente vinculados al módulo de la funcionalidad.
* **Alcance:**
  1. Ubica al LLM en la topología del proyecto.
  2. Permite al modelo sugerir la creación de nuevos archivos o la importación desde rutas correctas.
  3. Renderizado:
     ```text
     # [SUBSYSTEM TOPOLOGY: application/actions/emitir]
     ├── emitir_factura.py (target)
     ├── emitir_compra_venta.py
     └── base.py
     ```

---

### Ajuste 4: Enriquecimiento de la Herramienta MCP (`prune_context` / Multiescala)
* **Requerimiento:** La herramienta MCP `prune_context` debe soportar la generación del contrato multiescala mediante parámetros declarativos:
* **Parámetros propuestos:**
  * `file_path`: Ruta del archivo objetivo.
  * `target_symbol`: Símbolo a modificar.
  * `include_inheritance` *(bool, default=True)*: Resuelve e incluye la clase base con sus miembros.
  * `include_outline` *(bool, default=True)*: Incluye el outline de los colaboradores del módulo.
  * `include_body` *(bool, default=True)*: Mantiene el cuerpo de código detallado **exclusivamente** para el símbolo objetivo (Focal Code).

---

## 3. Presupuesto de Tokens y Comparativa

| Dimensión | Enfoque Naive (File Dumper) | OntoPrune 0.3.0 (1-Hop Estático) | OntoPrune 0.4.0 (Jerárquico Multiescala) |
| :--- | :---: | :---: | :---: |
| **Archivos leídos** | 4-6 archivos completos | 1 archivo podado | Subsistema estructurado |
| **Tokens consumidos** | 12.000 – 18.000 tokens | ~620 tokens | **~750 – 950 tokens** |
| **Conocimiento de Herencia** | Caótico (código duplicado) | Nulo (clase huérfana) | **Exacto (miembros en `self`)** |
| **Capacidad de Nueva Asociación** | Baja (se ahoga en texto) | Nula (solo ve llamadas viejas) | **Alta (ve el Outline de servicios)** |
| **Riesgo de Alucinación** | Alto | Bajo | **Cero (firmas verificadas AST)** |

---

## 4. Plan de Implementación por Fases

1. **Fase 1: Motor de Herencia (`soft:inheritsFrom`):**
   - Modificar `src/ontoprune/parser.py` para resolver `node.bases` inter-módulo.
   - Enriquecer `src/ontoprune/pruner.py` para incluir nodos de clases padre.
   - Actualizar `renderers/stubs.py` para declarar `class Hijo(Padre):` y listar métodos base.

2. **Fase 2: Generador de Outline Estructural:**
   - Crear extractor de Outlines que recorra archivos del subsistema y devuelva únicamente `class/def` con `...`.

3. **Fase 3: Integración en el Servidor MCP (`ontoprune-mcp`):**
   - Exponer los nuevos campos en `prune_context` para que los agentes en Cursor, Claude Code y Antigravity reciban la estructura completa.

4. **Fase 4: Validación Empírica en Proyecto Real (`kc_store`):**
   - Probar sobre `emitir_factura.py` y validar que el contrato contenga `BaseAction` y los outlines de las acciones hermanas.
