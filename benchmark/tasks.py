"""
Standardized Evaluation Tasks for Empirical Benchmarking.
"""

from __future__ import annotations

TASKS = {
    "refactor": """
### INSTRUCCIÓN DE INGENIERÍA DE SOFTWARE
Refactoriza la función objetivo para agregar un control de auditoría previo:
1. Valida la orden antes de cualquier operación.
2. Reserva el stock necesario.
3. Ejecuta el cobro a través de la pasarela de pagos.
4. Emite la factura correspondiente y actualiza el estado a PAGADO.
5. Emite la notificación al cliente.

REGLA ESTRICTA DE INTEGRIDAD:
Implementa el código Python completo de la función refactorizada dentro de un bloque ```python ... ```.
DEBES UTILIZAR EXCLUSIVAMENTE los métodos y servicios definidos en el contrato provisto.
NO inventes métodos, parámetros ni servicios que no existan explícitamente en el contexto.
""",
    "unit_test": """
### INSTRUCCIÓN DE INGENIERÍA DE SOFTWARE
Escribe pruebas unitarias con `pytest` y `unittest.mock` para la función objetivo:
- Cubre el flujo exitoso y los flujos alternativos (ej. fallo de validación o fallo de pago).
- Utiliza únicamente los métodos y contratos provistos.

Implementa el código dentro de un bloque ```python ... ```.
""",
}


def get_task_prompt(task_name: str = "refactor") -> str:
    """Returns the standardized task prompt text."""
    if task_name not in TASKS:
        valid = list(TASKS.keys())
        raise ValueError(f"Unknown task '{task_name}'. Available: {valid}")
    return TASKS[task_name].strip()
