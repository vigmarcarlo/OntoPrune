"""
Sandbox Functional Evaluator for Empirical Benchmarking.

Executes pytest test suites against LLM-generated code in an isolated temporary
environment to compute the Pass@1 success metric with mathematical precision.
"""

from __future__ import annotations

import ast
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass
class EvaluationResult:
    syntax_valid: bool
    all_passed: bool
    passed_count: int
    failed_count: int
    total_count: int
    pass_rate: float
    error_message: str = ""
    raw_output: str = ""


class SandboxEvaluator:
    """Evaluates generated Python code by running real pytest suites in isolated sandboxes."""

    def __init__(self, python_binary: str | None = None) -> None:
        self.python_binary = python_binary or self._detect_python()

    def _detect_python(self) -> str:
        repo_root = Path(__file__).resolve().parent.parent
        venv_py = repo_root / ".venv" / "bin" / "python"
        if venv_py.exists():
            return str(venv_py)
        import sys
        return sys.executable

    @staticmethod
    def extract_code(raw_llm_text: str) -> str:
        """Extracts python code block from markdown responses."""
        match = re.search(r"```(?:python)?\s*\n([\s\S]*?)```", raw_llm_text)
        if match:
            return match.group(1).strip()
        # Fallback: assume raw code
        return raw_llm_text.strip()

    @staticmethod
    def check_syntax(code: str) -> tuple[bool, str]:
        """Validates that code parses into a valid Python AST."""
        try:
            ast.parse(code)
            return True, ""
        except SyntaxError as e:
            return False, f"SyntaxError at line {e.lineno}: {e.msg}"

    def evaluate_code(
        self,
        fixture_dir: str | Path,
        target_relative_file: str,
        target_symbol_name: str,
        generated_code: str,
        test_relative_file: str,
    ) -> EvaluationResult:
        """
        1. Validates AST syntax.
        2. Copies fixture_dir into a temporary scratch directory.
        3. Injects generated_code into target_relative_file.
        4. Runs pytest on test_relative_file.
        5. Computes Pass@1 metrics and returns EvaluationResult.
        """
        code_to_test = self.extract_code(generated_code)
        syntax_ok, syntax_err = self.check_syntax(code_to_test)
        if not syntax_ok:
            return EvaluationResult(
                syntax_valid=False,
                all_passed=False,
                passed_count=0,
                failed_count=0,
                total_count=0,
                pass_rate=0.0,
                error_message=syntax_err,
            )

        src_fixture = Path(fixture_dir).resolve()
        temp_dir = tempfile.mkdtemp(prefix="ontoprune_bench_")

        try:
            # Copy entire fixture suite to temp directory
            dst_fixture = Path(temp_dir) / src_fixture.name
            shutil.copytree(src_fixture, dst_fixture)

            target_file = dst_fixture / target_relative_file
            if not target_file.exists():
                return EvaluationResult(
                    syntax_valid=True,
                    all_passed=False,
                    passed_count=0,
                    failed_count=0,
                    total_count=0,
                    pass_rate=0.0,
                    error_message=f"Target file {target_relative_file} not found in sandbox.",
                )

            # Read original and replace target method or replace entire module
            orig_content = target_file.read_text(encoding="utf-8")
            
            # If generated code is a complete class or function, replace in file
            # or overwrite target method if AST matches
            target_file.write_text(self._patch_file(orig_content, target_symbol_name, code_to_test), encoding="utf-8")

            # Execute pytest in sandbox
            test_target = dst_fixture / test_relative_file
            cmd = [
                self.python_binary,
                "-m",
                "pytest",
                str(test_target),
                "-q",
                "--tb=short",
            ]

            env = os.environ.copy()
            env["PYTHONPATH"] = str(dst_fixture.parent)

            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=str(dst_fixture.parent),
                timeout=25,
                env=env,
            )

            raw_out = proc.stdout + "\n" + proc.stderr
            return self._parse_pytest_output(proc.returncode, raw_out)

        except subprocess.TimeoutExpired:
            return EvaluationResult(
                syntax_valid=True,
                all_passed=False,
                passed_count=0,
                failed_count=0,
                total_count=0,
                pass_rate=0.0,
                error_message="Execution timed out (possible infinite loop in generated code).",
            )
        except Exception as ex:
            return EvaluationResult(
                syntax_valid=True,
                all_passed=False,
                passed_count=0,
                failed_count=0,
                total_count=0,
                pass_rate=0.0,
                error_message=str(ex),
            )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _patch_file(self, original_text: str, target_symbol: str, replacement_code: str) -> str:
        """
        Smart patching:
        - If replacement_code contains module-level imports or from __future__,
          it represents a complete file replacement.
        - If replacement_code defines a class matching an existing class in original_text,
          replaces the entire class.
        - Otherwise, locates target function/method in AST and replaces it, reindenting
          replacement_code to match the target's indentation depth.
        """
        if "from __future__" in replacement_code:
            return replacement_code

        # If replacement defines a class that already exists in the file, replace that class
        rep_class_match = re.search(r"^class\s+([A-Za-z0-9_]+)", replacement_code, re.MULTILINE)
        if rep_class_match:
            rep_class_name = rep_class_match.group(1)
            try:
                tree = ast.parse(original_text)
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef) and node.name == rep_class_name:
                        lines = original_text.splitlines(keepends=True)
                        start_line = node.lineno - 1
                        end_line = getattr(node, "end_lineno", len(lines))
                        prefix = "".join(lines[:start_line])
                        suffix = "".join(lines[end_line:])
                        return prefix + replacement_code + "\n" + suffix
            except Exception:
                pass

        try:
            tree = ast.parse(original_text)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == target_symbol:
                    lines = original_text.splitlines(keepends=True)
                    start_line = node.lineno - 1
                    end_line = getattr(node, "end_lineno", len(lines))

                    target_line = lines[start_line]
                    indent_match = re.match(r"^(\s*)", target_line)
                    indent = indent_match.group(1) if indent_match else ""

                    # Reindent replacement_code to match target method's indentation
                    rep_lines = replacement_code.splitlines()
                    non_empty = [l for l in rep_lines if l.strip()]
                    if non_empty:
                        base_indent = min(len(re.match(r"^(\s*)", l).group(1)) for l in non_empty)
                        reindented = []
                        for l in rep_lines:
                            if l.strip():
                                reindented.append(indent + l[base_indent:])
                            else:
                                reindented.append("")
                        replacement_code = "\n".join(reindented)

                    prefix = "".join(lines[:start_line])
                    suffix = "".join(lines[end_line:])
                    return prefix + replacement_code + "\n" + suffix
        except Exception:
            pass

        pattern = rf"(def {re.escape(target_symbol)}\s*\([^)]*\)[^:]*:[\s\S]*?)(?=\n\s*def |\n\s*class |\Z)"
        if re.search(pattern, original_text):
            return re.sub(pattern, replacement_code, original_text, count=1)

        return replacement_code

    def _parse_pytest_output(self, returncode: int, output: str) -> EvaluationResult:
        """Parses pytest summary line (e.g. '8 passed in 0.02s' or '2 failed, 6 passed in 0.05s')."""
        passed = 0
        failed = 0

        passed_match = re.search(r"(\d+)\s+passed", output)
        if passed_match:
            passed = int(passed_match.group(1))

        failed_match = re.search(r"(\d+)\s+failed", output)
        if failed_match:
            failed = int(failed_match.group(1))

        error_match = re.search(r"(\d+)\s+error", output)
        if error_match:
            failed += int(error_match.group(1))

        total = passed + failed
        if total == 0:
            all_passed = returncode == 0
            pass_rate = 1.0 if all_passed else 0.0
        else:
            all_passed = (returncode == 0) and (failed == 0)
            pass_rate = passed / total if total > 0 else 0.0

        return EvaluationResult(
            syntax_valid=True,
            all_passed=all_passed,
            passed_count=passed,
            failed_count=failed,
            total_count=total,
            pass_rate=pass_rate,
            raw_output=output,
        )
