"""
Massive Automated Empirical Benchmark Runner for OntoPrune.

Executes Phase 2 of the Empirical Validation Framework:
- 3 Archetypes (Algorithm, Multi-Module, Clean Architecture)
- 2 Treatments (OntoPrune vs Naive Full Context)
- 2 Models (Google Gemini 3.8 Flash vs Ollama Qwen 2.5 Coder 7B)
- Evaluates Pass@1 with pytest in isolated sandboxes
- Measures TTFT, total latency, server token counts, and IP leakage
- Emits Go / No-Go decision matrix
"""

from __future__ import annotations

import json
import os
import statistics
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from benchmark.clients import GeminiClient, LLMClient, MockClient, OllamaClient, StreamResult
from benchmark.evaluators import EvaluationResult, SandboxEvaluator
from ontoprune import check, translate


@dataclass
class RunRecord:
    archetype: str
    treatment: str
    backend: str
    model: str
    iteration: int
    input_tokens: int
    output_tokens: int
    ttft_ms: float
    total_time_ms: float
    syntax_valid: bool
    all_passed: bool
    passed_tests: int
    total_tests: int
    pass_rate: float
    violations: int
    ip_leaked_lines: int
    error: str = ""


class MassiveBenchmarkSuite:
    def __init__(
        self,
        gemini_api_key: str | None = None,
        ollama_host: str = "http://localhost:11434",
        output_dir: str = ".benchmarks",
    ) -> None:
        self.gemini_key = gemini_api_key or os.environ.get("GEMINI_API_KEY", "")
        self.ollama_host = ollama_host
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.evaluator = SandboxEvaluator()

        self.scenarios = [
            {
                "id": "archetype_1_algorithm",
                "name": "Arquetipo 1: Algoritmo Aislado",
                "fixture_dir": "fixtures/benchmark_suite/archetype_1_algorithm",
                "target_file": "validator.py",
                "target_symbol": "evaluate_transaction",
                "test_file": "test_validator.py",
                "task_instruction": (
                    "### INSTRUCCIÓN DE INGENIERÍA DE SOFTWARE\n"
                    "Implementa o refactoriza el método `evaluate_transaction` de la clase `TransactionRiskEvaluator`.\n"
                    "Reglas de negocio obligatorias:\n"
                    "1. Si `amount <= 0.0`, lanza `ValueError`.\n"
                    "2. Si `amount > self.max_daily_limit`, suma 40 puntos y agrega 'EXCEEDS_DAILY_LIMIT'.\n"
                    "3. Si `self.evaluate_velocity(recent_count)` es True, suma 30 puntos y agrega 'HIGH_VELOCITY_BURST'.\n"
                    "4. Si `is_international` es True, suma 20 puntos y agrega 'CROSS_BORDER_RISK'.\n"
                    "5. Clampa el puntaje a [0.0, 100.0]. Asigna el nivel: >=80 CRITICAL, >=50 HIGH, >=20 MEDIUM, sino LOW.\n"
                    "6. Retorna una instancia de `RiskAssessment` con el checksum SHA256 calculado via `self.calculate_checksum`.\n"
                    "Provee únicamente el código Python dentro de un bloque ```python ... ```."
                ),
            },
            {
                "id": "archetype_2_multi_module",
                "name": "Arquetipo 2: Servicio Multi-Módulo Transaccional",
                "fixture_dir": "fixtures/benchmark_suite/archetype_2_multi_module",
                "target_file": "order_orchestrator.py",
                "target_symbol": "process_order_checkout",
                "test_file": "test_order_orchestrator.py",
                "task_instruction": (
                    "### INSTRUCCIÓN DE INGENIERÍA DE SOFTWARE\n"
                    "Implementa el método `process_order_checkout(self, order: Order) -> Invoice | None` en `OrderOrchestrator`.\n"
                    "Protocolo transaccional estricto:\n"
                    "1. Registra la orden en `self.orders[order.id] = order`.\n"
                    "2. Valida la orden con `self.validate_order(order)`. Si falla, marca `order.status = OrderStatus.FAILED`, notifica falla con `self.notifier.notify_order_failed` y retorna None.\n"
                    "3. Reserva el stock con `self.inventory.lock_and_reserve(order.items)`. Si falla, marca `order.status = OrderStatus.FAILED`, notifica falla y retorna None.\n"
                    "4. Ejecuta el cobro con `self.payment.charge_customer(order.customer_id, order.total_amount)`.\n"
                    "   Si el cobro no es CAPTURED: libera el stock reservado con `self.inventory.release_reserved_stock(order.items)`, marca `order.status = OrderStatus.FAILED`, notifica falla y retorna None.\n"
                    "5. Si el cobro fue exitoso: marca `order.status = OrderStatus.PAID`, genera una instancia de `Invoice`, notifica aprobación con `self.notifier.notify_order_approved` y retorna la factura.\n"
                    "Provee únicamente el código Python dentro de un bloque ```python ... ```."
                ),
            },
            {
                "id": "archetype_3_clean_arch",
                "name": "Arquetipo 3: Arquitectura Hexagonal Desacoplada",
                "fixture_dir": "fixtures/benchmark_suite/archetype_3_clean_arch",
                "target_file": "use_cases/register_user.py",
                "target_symbol": "execute",
                "test_file": "test_register_user.py",
                "task_instruction": (
                    "### INSTRUCCIÓN DE INGENIERÍA DE SOFTWARE\n"
                    "Implementa el método `execute(self, tenant_id: str, email: str, plain_password: str) -> User` en `RegisterUserUseCase`.\n"
                    "Reglas de negocio empresariales:\n"
                    "1. Normaliza el email con `email.strip().lower()`.\n"
                    "2. Valida la fortaleza de la contraseña con `self.validate_password_strength(plain_password)`.\n"
                    "   Si falla: registra auditoría 'REGISTRATION_FAILED_WEAK_PASSWORD' via `self.audit_logger.log_security_event` y lanza `InvalidPasswordComplexityError`.\n"
                    "3. Verifica si el email ya existe via `self.user_repo.find_by_email(tenant_id, clean_email)`.\n"
                    "   Si existe: registra auditoría 'REGISTRATION_FAILED_DUPLICATE_EMAIL' y lanza `EmailAlreadyExistsError`.\n"
                    "4. Hashea la contraseña con `self.hasher.hash_password(plain_password)`.\n"
                    "5. Genera el token de activación con `self.token_gen.generate_token({'email': clean_email, 'tenant': tenant_id})`.\n"
                    "6. Instancia y persiste `User` con rol `Role.USER` y estado `UserStatus.PENDING_ACTIVATION` via `self.user_repo.save(user)`.\n"
                    "7. Registra auditoría 'USER_REGISTERED_SUCCESS' y despacha el correo de bienvenida via `self.email_dispatcher.send_welcome_email`.\n"
                    "8. Retorna el usuario creado.\n"
                    "Provee únicamente el código Python dentro de un bloque ```python ... ```."
                ),
            },
        ]

    def _build_naive_context(self, fixture_dir: Path) -> tuple[str, int]:
        """Concatenates all .py files in fixture_dir (excluding tests) to simulate naive Copilot/Cursor."""
        parts: list[str] = []
        leaked_lines = 0
        for py_path in sorted(fixture_dir.rglob("*.py")):
            if "test_" in py_path.name or "__init__" in py_path.name:
                continue
            content = py_path.read_text(encoding="utf-8")
            parts.append(f"# ===== FILE: {py_path.name} =====\n{content}")
            # Count implementation lines in dependencies
            if "adapters.py" in py_path.name or "inventory.py" in py_path.name or "payment.py" in py_path.name:
                leaked_lines += len(content.splitlines())
        return "\n\n".join(parts), leaked_lines

    def _build_ontoprune_context(self, target_file: Path, target_symbol: str) -> tuple[str, int]:
        """Extracts minimal semantic contract via OntoPrune AST & OWL ontology."""
        contract = translate(str(target_file), target_symbol, include_body=True)
        # OntoPrune sends 0 lines of private dependency bodies
        return contract, 0

    def run_suite(
        self,
        backend: str = "all",
        archetype: str = "all",
        repeats_per_scenario: int = 2,
    ) -> list[RunRecord]:
        """Executes full evaluation matrix."""
        records: list[RunRecord] = []

        all_clients: dict[str, tuple[LLMClient, str]] = {
            "gemini": (
                GeminiClient(api_key=self.gemini_key, model="gemini-3.8-flash"),
                "gemini-3.8-flash",
            ),
            "ollama": (
                OllamaClient(host=self.ollama_host, model="qwen2.5-coder:7b", num_threads=4),
                "qwen2.5-coder:7b",
            ),
            "mock": (
                MockClient(model="mock-agent"),
                "mock-agent",
            ),
        }

        if backend == "all":
            clients = {k: v for k, v in all_clients.items() if k in ("gemini", "ollama")}
        else:
            clients = {backend: all_clients[backend]}

        active_scenarios = self.scenarios
        if archetype != "all":
            arch_key = f"archetype_{archetype}"
            active_scenarios = [s for s in self.scenarios if s["id"].startswith(arch_key)]

        print("=" * 80)
        print(" INICIANDO PROTOCOLO DE VALIDACIÓN EMPÍRICA RIGUROSA - ONTOPRUNE")
        print(f" Arquetipos: {len(active_scenarios)} | Modelos: {len(clients)} | Repeticiones: {repeats_per_scenario}")
        print("=" * 80)

        for sc in active_scenarios:
            sc_id = sc["id"]
            sc_name = sc["name"]
            fix_dir = Path(sc["fixture_dir"])
            target_path = fix_dir / sc["target_file"]

            print(f"\n▶ EVALUANDO: {sc_name}")

            # 1. Prepare contexts
            naive_ctx, naive_leaked = self._build_naive_context(fix_dir)
            onto_ctx, onto_leaked = self._build_ontoprune_context(target_path, sc["target_symbol"])

            treatments = [
                ("ontoprune", onto_ctx, onto_leaked),
                ("naive", naive_ctx, naive_leaked),
            ]

            for t_name, ctx_text, leaked_lines in treatments:
                full_prompt = (
                    f"// === CONTEXTO DE CÓDIGO DISPONIBLE ===\n{ctx_text}\n\n"
                    f"{sc['task_instruction']}"
                )

                for b_name, (client, model_name) in clients.items():
                    print(f"   [{t_name.upper():10s}] en [{b_name.upper():6s} ({model_name})] ... ", end="", flush=True)

                    for rep in range(1, repeats_per_scenario + 1):
                        t_start = time.perf_counter()
                        error_msg = ""
                        stream_res = StreamResult(0.0, 0.0, 0, 0, "")

                        try:
                            stream_res = client.generate_stream(full_prompt, temperature=0.0, seed=42 + rep)
                        except Exception as ex:
                            error_msg = str(ex)

                        # Evaluate Pass@1 in isolated sandbox
                        eval_res = EvaluationResult(False, False, 0, 0, 0, 0.0, error_message=error_msg)
                        if stream_res.text:
                            eval_res = self.evaluator.evaluate_code(
                                fixture_dir=fix_dir,
                                target_relative_file=sc["target_file"],
                                target_symbol_name=sc["target_symbol"],
                                generated_code=stream_res.text,
                                test_relative_file=sc["test_file"],
                            )

                        # Check contract violations
                        violations = 0
                        if stream_res.text:
                            v_list = check(stream_res.text, against=onto_ctx)
                            violations = len(v_list)

                        rec = RunRecord(
                            archetype=sc_id,
                            treatment=t_name,
                            backend=b_name,
                            model=model_name,
                            iteration=rep,
                            input_tokens=stream_res.input_tokens,
                            output_tokens=stream_res.output_tokens,
                            ttft_ms=round(stream_res.ttft_ms, 1),
                            total_time_ms=round(stream_res.total_time_ms, 1),
                            syntax_valid=eval_res.syntax_valid,
                            all_passed=eval_res.all_passed,
                            passed_tests=eval_res.passed_count,
                            total_tests=eval_res.total_count,
                            pass_rate=round(eval_res.pass_rate, 2),
                            violations=violations,
                            ip_leaked_lines=leaked_lines,
                            error=error_msg or eval_res.error_message,
                        )
                        records.append(rec)

                        status_str = f"[{eval_res.passed_count}/{eval_res.total_count}]" if eval_res.all_passed else f"[F:{eval_res.passed_count}/{eval_res.total_count}]"
                        print(f" {status_str}", end="", flush=True)
                        if b_name == "gemini":
                            time.sleep(2.5)
                        else:
                            time.sleep(1.0)

                    # Print quick summary for this treatment/backend
                    recent = [r for r in records if r.archetype == sc_id and r.treatment == t_name and r.backend == b_name]
                    avg_tokens = int(statistics.mean(r.input_tokens for r in recent))
                    avg_ttft = statistics.mean(r.ttft_ms for r in recent)
                    pass_rate_pct = statistics.mean(r.pass_rate for r in recent) * 100.0
                    print(f" | AvgTokens: {avg_tokens:5d} | TTFT: {avg_ttft:6.1f}ms | Pass@1: {pass_rate_pct:5.1f}%")

        # Save raw results
        results_file = self.output_dir / "results_matrix.json"
        with open(results_file, "w", encoding="utf-8") as f:
            json.dump([asdict(r) for r in records], f, indent=2)

        print("\n" + "=" * 80)
        print(f" BATERÍA DE PRUEBAS COMPLETADA. Datos guardados en: {results_file}")
        print("=" * 80)

        return records


if __name__ == "__main__":
    import argparse
    from benchmark.analyze_results import analyze_matrix

    parser = argparse.ArgumentParser(
        prog="massive_evaluator",
        description="Massive Automated Empirical Benchmark Suite for OntoPrune",
    )
    parser.add_argument(
        "--backend",
        default="all",
        choices=["all", "gemini", "ollama", "mock"],
        help="Inference engine backend (default: all)",
    )
    parser.add_argument(
        "--archetype",
        default="all",
        choices=["all", "1", "2", "3"],
        help="Archetype filter: 1 (Algorithm), 2 (Multi-Module), 3 (Clean Arch), or all",
    )
    parser.add_argument(
        "--repeats",
        default=2,
        type=int,
        help="Number of evaluation repetitions per scenario (default: 2)",
    )
    parser.add_argument(
        "--output-dir",
        default=".benchmarks",
        type=str,
        help="Output directory for raw JSON results (default: .benchmarks)",
    )
    parser.add_argument(
        "--analyze",
        action="store_true",
        help="Run statistical analysis and generate final Markdown report immediately",
    )

    args = parser.parse_args()

    suite = MassiveBenchmarkSuite(output_dir=args.output_dir)
    suite.run_suite(
        backend=args.backend,
        archetype=args.archetype,
        repeats_per_scenario=args.repeats,
    )

    if args.analyze:
        report = analyze_matrix(json_path=f"{args.output_dir}/results_matrix.json")
        print("\n" + report)
