# OntoPrune: Protocolo de Validación Empírica y Criterios Go / No-Go

> **Documento de Referencia Científica e Ingeniería de Software**  
> **Versión:** 1.0.0  
> **Fecha:** 6 de Octubre de 2026  
> **Propósito:** Definir un marco experimental objetivo, reproducible y cuantitativo para determinar con base en evidencia empírica si se debe continuar invirtiendo esfuerzo en OntoPrune o no.

---

## 1. Propósito y Tesis Fundamental

### 1.1 La Hipótesis Central
> *"La poda ontológica neuro-simbólica del grafo de dependencias de un proyecto (OntoPrune) reduce drásticamente el volumen de tokens de entrada (>70%) y el tiempo de respuesta (TTFT), protegiendo la lógica propietaria confidencial sin degradar la capacidad del modelo de lenguaje para generar código sintáctica y semánticamente correcto (Pass@1)."*

### 1.2 La Pregunta de Decisión (Go / No-Go)
**¿OntoPrune ofrece una ventaja medible, reproducible y defensible frente a las alternativas existentes (enviar archivos completos o RAG naive)?**
* **SI (GO):** Si se superan los umbrales cuantitativos definidos en la Sección 6, se justifica formalmente el desarrollo del producto, patentes o publicaciones científicas.
* **NO (NO-GO):** Si la poda degrada severamente la tasa de éxito (Pass@1 < 80%) o si el ahorro de tokens/latencia resulta estadísticamente insignificante (< 30%), el proyecto se detiene o se reorienta de inmediato, evitando el costo hundido.

---

## 2. Las 4 Dimensiones de Evaluación Cuantitativa

Para erradicar cualquier tipo de especulación, cada experimento recopilará datos duros en 4 dimensiones independientes:

```
                          ┌─────────────────────────────────────┐
                          │    EVALUACIÓN CIENTÍFICA ONTOPRUNE   │
                          └──────────────────┬──────────────────┘
                 ┌───────────────────┬───────┴───────────┬───────────────────┐
                 ▼                   ▼                   ▼                   ▼
        [1. Compresión]      [2. Corrección]     [3. Rendimiento]     [4. Privacidad IP]
        - Prompt Tokens      - Pass@1 (pytest)   - TTFT (ms)          - AST Nodes leaked
        - Token Ratio (%)    - Hallucinations    - Latencia Total (s) - Secret isolation
        - Facturación ($)    - Contrato (0 viol) - CPU local (%)      - Zero-Knowledge %
```

### Dimensión 1: Eficiencia de Contexto (Token Compression Ratio)
* **Variable:** Conteo exacto de tokens de entrada reportados por la API (`usageMetadata.promptTokenCount` en Gemini / `usage.prompt_tokens` en OpenAI / tokenizer `tiktoken`).
* **Fórmula de Ahorro:**
  $$\text{Compresión (\%)} = \left(1 - \frac{\text{Tokens}_{\text{OntoPrune}}}{\text{Tokens}_{\text{Línea Base}}}\right) \times 100$$
* **Impacto Económico:** Estimación del costo de API mensual para un equipo de 10 desarrolladores (asumiendo 50 peticiones diarias por dev).

### Dimensión 2: Fidelidad Semántica y Corrección (Pass@1)
* **Variable 1 (Ejecución Funcional):** Tasa de éxito Pass@1 al ejecutar la suite de pruebas unitarias (`pytest`) sobre el código generado:
  $$\text{Pass@1} = \frac{\text{Ejecuciones con 100\% tests aprobados}}{\text{Total de ejecuciones}} \times 100$$
* **Variable 2 (Violación de Contrato / Alucinación):** Conteo de símbolos o llamadas a métodos externos inexistentes detectados por el validador ontológico de OntoPrune.

### Dimensión 3: Latencia e Interactividad
* **Variable 1 (TTFT - Time To First Token):** Tiempo de alta precisión en milisegundos (`time.perf_counter()`) desde el envío del HTTP POST hasta el primer fragmento de streaming recibido.
* **Variable 2 (Latencia Total de Generación):** Tiempo transcurrido hasta el cierre del stream (`[DONE]`).
* **Variable 3 (Carga de Recursos Locales):** Porcentaje de uso de CPU durante la ráfaga (en hardware Ryzen 5 5600G) y delta de consumo de RAM.

### Dimensión 4: Fuga de Propiedad Intelectual (AST Implementation Leakage)
* **Definición:** Medición estricta de qué porcentaje de líneas y nodos sintácticos de implementación interna (cuerpos de funciones dependientes, queries SQL, fórmulas matemáticas, variables privadas) abandonan la máquina local.
* **Fórmula:**
  $$\text{IP Leaked (\%)} = \frac{\text{Líneas de implementación de dependencias enviadas}}{\text{Líneas totales de implementación en el proyecto}} \times 100$$
  * *OntoPrune Meta:* **0.0%** (solo signaturas públicas y stubs con `pass`).
  * *Línea Base Naive:* **100.0%** (se envían los archivos completos con toda la lógica).

---

## 3. Diseño Experimental: Grupos de Tratamiento y Control

Cada tarea se ejecutará de forma ciega y automatizada bajo 3 condiciones idénticas:

| Grupo | Nombre | Estrategia de Contexto | Descripción |
| :--- | :--- | :--- | :--- |
| **Control A** | **Naive Full Context** | Inclusión de Archivos Completos | Lo que hace Cursor/Copilot por defecto: adjunta el archivo objetivo y todos los archivos importados directamente. |
| **Control B** | **Naive Truncation** | Recorte arbitrario por tokens | Recorte plano de los primeros 1,000 tokens del archivo sin análisis sintáctico. |
| **Tratamiento** | **OntoPrune Minimal** | Poda Ontológica por Dependencias | Extracción de contrato formal: signaturas públicas de dependencias + stubs vacíos + cuerpo del método objetivo. |

### Modelos de Evaluación
Para asegurar validez ecológica, se prueba en los dos extremos de la industria:
1. **Cloud Frontier LLM:** Google Gemini (`gemini-3.8-flash` vía API REST).
2. **Local Edge SLM:** Ollama (`qwen2.5-coder:7b` corriendo en CPU local con 4 hilos).

*Parámetros fijados:* Temperatura = 0.0 (determinismo), Semilla = 42, Iteraciones = $N = 5$ por tratamiento.

---

## 4. Banco de Pruebas: 3 Arquetipos de Código Real

Para evitar sesgos por "ejemplos de juguete", el benchmark se alimentará de 3 arquetipos representativos:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        ARQUETIPOS DE EVALUACIÓN                        │
├─────────────────────────┬─────────────────────────┬────────────────────┤
│ Arquetipo 1: Simple     │ Arquetipo 2: Medio      │ Arquetipo 3: Clean │
│ (Módulo Aislado)        │ (Multi-Dependencia)     │ Architecture (6+)  │
│ - 1 archivo             │ - 3 archivos            │ - Capas desacopl.  │
│ - Algoritmo y parsing   │ - Repo + Payment + Mail │ - Interfaces & DTO │
│ - ~120 líneas           │ - ~550 líneas           │ - ~1,600 líneas    │
└─────────────────────────┴─────────────────────────┴────────────────────┘
```

### Arquetipo 1: Módulo Algorítmico Aislado (`fixtures/sample_algorithm.py`)
* **Contexto:** Lógica de validación matemática y sanitización de datos.
* **Tarea:** *"Refactoriza la función para soportar validación estricta de límites e incorporar manejo de excepciones personalizadas."*
* **Suite de Pruebas:** 5 tests unitarios predefinidos.

### Arquetipo 2: Servicio Transaccional Multi-Dependencia (`fixtures/order_flow/`)
* **Contexto:** `order_service.py` depende de `payment_gateway.py`, `inventory_repository.py` y `models.py`.
* **Problema:** En el enfoque tradicional, hay que enviar los 4 archivos (~600 líneas con detalles de base de datos y llaves de stripe mockeadas).
* **Tarea:** *"Implementa la cancelación y reembolso de orden cumpliendo con el protocolo de reversa de stock y notificación al cliente."*
* **Suite de Pruebas:** 8 tests unitarios con mocks de base de datos y pagos.

### Arquetipo 3: Arquitectura Limpia Hexagonal (`fixtures/enterprise_core/`)
* **Contexto:** Use-Case que interactúa con 3 interfaces de dominio y 2 entidades, dentro de una estructura de más de 1,500 líneas.
* **Problema:** Enviar todo el árbol supera los límites o diluye la atención del modelo (*lost in the middle*).
* **Tarea:** *"Genera la suite completa de pruebas unitarias (`pytest`) cubriendo todas las ramificaciones del caso de uso."*
* **Suite de Pruebas:** Evaluación de cobertura de ramas (`pytest-cov`).

---

## 5. Arquitectura del Harness Automatizado

Se utilizará y extenderá el módulo `benchmark/` ya existente en el repositorio:

```
benchmark/
├── __main__.py          # Entrypoint CLI para lanzar la suite completa
├── runner.py            # Orquestador del experimento (Tratamiento vs Controles)
├── clients.py           # Conectores streaming con medición de TTFT (Gemini & Ollama)
├── tasks.py             # Definición de tareas estandarizadas
├── evaluators.py        # Ejecutor de pytest en sandbox y cálculo de Pass@1
└── reporting.py         # Generador de tablas comparativas y exportación CSV/JSON
```

### Flujo Automatizado de Cada Ejecución:
1. **Extracción de Contexto:** Genera la versión Naive (archivos concatenados) y la versión OntoPrune (contrato mínimo podado).
2. **Medición de Entrada:** Cuenta tokens exactos y mide tiempo de CPU del parser OntoPrune.
3. **Inferencia en Paralelo:** Lanza las 5 repeticiones contra el modelo objetivo con temporizador de nanosegundos.
4. **Verificación Estática:** Pasa el código resultante por el validador ontológico (`ontoprune.check`).
5. **Ejecución Dinámica:** Inyecta el código generado en el sandbox y ejecuta `pytest -q`.
6. **Consolidación:** Almacena resultados en `.benchmarks/results_<timestamp>.json`.

---

## 6. Matriz de Decisión Go / No-Go (Criterios Cuantitativos)

Para que el resultado sea concluyente y sin ambigüedades, se establecen los siguientes umbrales:

| Métrica | Umbral Crítico (NO-GO) | Umbral Aceptable | Umbral Excepcional (GO TOTAL) |
| :--- | :--- | :--- | :--- |
| **Ahorro de Tokens (Prompt)** | **< 50%** (Ahorro insuficiente) | **60% - 75%** | **> 80% de reducción** |
| **Tasa de Éxito (Pass@1)** | **< 75%** (El pruning rompe la IA) | **75% - 90%** | **$\ge$ 95% (Igual o superior a Naive)** |
| **Reducción de TTFT (Nube)** | **< 20%** de mejora | **30% - 50%** de mejora | **> 50% más rápido** |
| **Fuga de Lógica Privada (IP)** | **> 15%** de código sensible filtrado | **< 5%** | **0.0% (Zero-Knowledge estricto)** |
| **Sobrecarga de CPU de Poda** | **> 150 ms** por podar | **20 ms - 50 ms** | **< 15 ms (Imperceptible)** |

### Reglas de Veredicto:
* **VEREDICTO: GO INMEDIATO:** Si en los Arquetipos 2 y 3 se logra **>75% de ahorro de tokens**, **Pass@1 $\ge$ 90%** y **0% fuga de código privado**.  
  *Justificación:* Demuestra que OntoPrune es un middleware indispensable de compresión y seguridad enterprise.
* **VEREDICTO: PIVOTE / REPLANTEAMIENTO:** Si el ahorro de tokens es muy alto (>80%), pero el modelo falla en los tests (Pass@1 < 75%) por falta de información complementaria (ej. docstrings o tipos de retorno).
  *Acción:* Ajustar el nivel de poda (incluir más metadatos de tipos).
* **VEREDICTO: NO-GO (DETENER INVERSIÓN):** Si la línea base (Naive) obtiene 95% de tests pasando y OntoPrune solo obtiene 50%, o si los LLMs modernos no muestran beneficio apreciable en costo/tiempo con el contrato podado.
  *Acción:* Detener el desarrollo antes de asumir costos mayores.

---

## 7. Plan de Implementación por Fases

### Fase 1: Preparación del Banco de Pruebas (Día 1)
- [x] Adaptar `benchmark/clients.py` para soportar claves `AQ.` en Gemini y Ollama con 4 hilos.
- [ ] Construir los fixtures de los 3 arquetipos (`fixtures/benchmark_suite/`) con sus suites de pruebas `pytest` asociadas.
- [ ] Implementar el evaluador de ejecución funcional (`pytest` runner sandbox).

### Fase 2: Ejecución Masiva y Recolección de Datos (Día 2)
- [ ] Ejecutar el benchmark automatizado:
  * 3 Arquetipos $\times$ 3 Tratamientos $\times$ 2 Modelos (Gemini 3.8 / Ollama 7B) $\times$ 5 Repeticiones = **90 corridas controladas**.
- [ ] Exportar resultados crudos a `.benchmarks/results_matrix.json`.

### Fase 3: Análisis Estadístico y Reporte de Decisión (Día 3)
- [ ] Compilar tabla resumen con medias, medianas, percentil 90 y desviaciones estándar.
- [ ] Generar gráficos comparativos de Tokens vs Pass@1 y TTFT.
- [ ] Emitir el **Informe de Veredicto Final Go / No-Go**.
