"""
Streaming LLM Clients for Real Inference Benchmarking.

Provides low-overhead streaming clients for:
- Google Gemini REST API (streamGenerateContent)
- Ollama REST API (/api/generate)

Captures:
- Time to First Token (TTFT) via monotonic high-resolution timer
- Total execution time
- Real token counts from server usage metadata
- Output text response
"""

from __future__ import annotations

import json
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass

import requests


@dataclass
class StreamResult:
    ttft_ms: float
    total_time_ms: float
    input_tokens: int
    output_tokens: int
    text: str


class LLMClient(ABC):
    @abstractmethod
    def generate_stream(
        self,
        prompt: str,
        temperature: float = 0.0,
        seed: int = 42,
    ) -> StreamResult:
        pass


ACTIVE_GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")


class GeminiClient(LLMClient):
    """
    Direct REST streaming client for Gemini API using Server-Sent Events / chunked JSON.
    Native Google Generative Language endpoint with direct streaming.
    """

    def __init__(self, api_key: str | None = None, model: str = "gemini-3.8-flash") -> None:
        self.api_key = api_key or ACTIVE_GEMINI_KEY
        self.model = model

    def generate_stream(
        self,
        prompt: str,
        temperature: float = 0.0,
        seed: int = 42,
    ) -> StreamResult:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:streamGenerateContent?alt=sse&key={self.api_key.strip()}"
        )
        headers = {"Content-Type": "application/json"}
        payload = {
            "systemInstruction": {
                "parts": [
                    {
                        "text": (
                            "You are an expert programming assistant working with OntoPrune minimal dependency contracts. "
                            "Return only clean, production-ready Python code inside markdown ```python ... ``` blocks."
                        )
                    }
                ]
            },
            "contents": [
                {
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": {
                "temperature": temperature,
            },
        }

        resp = None
        for attempt in range(4):
            try:
                resp = requests.post(url, json=payload, headers=headers, stream=True, timeout=60.0)
                if resp.status_code in (429, 503):
                    time.sleep(2.0 * (attempt + 1))
                    continue
                resp.raise_for_status()
                break
            except Exception as e:
                if attempt == 3:
                    raise e
                time.sleep(2.0 * (attempt + 1))

        if resp is None:
            raise RuntimeError("Failed to connect to Gemini API after retries.")

        t_start = time.perf_counter()
        ttft_ms = 0.0
        full_text: list[str] = []
        input_tokens = 0
        output_tokens = 0

        for line in resp.iter_lines():
            if not line:
                continue
            line_str = line.decode("utf-8").strip()
            if not line_str.startswith("data:"):
                continue

            data_str = line_str[5:].strip()
            try:
                chunk = json.loads(data_str)
            except json.JSONDecodeError:
                continue

            candidates = chunk.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                for p in parts:
                    txt = p.get("text", "")
                    if txt:
                        if not ttft_ms:
                            ttft_ms = (time.perf_counter() - t_start) * 1000.0
                        full_text.append(txt)

            usage = chunk.get("usageMetadata")
            if usage:
                input_tokens = usage.get("promptTokenCount", input_tokens)
                output_tokens = usage.get("candidatesTokenCount", output_tokens)

        t_total = (time.perf_counter() - t_start) * 1000.0
        text_content = "".join(full_text)

        if input_tokens == 0:
            input_tokens = max(1, len(prompt) // 4)
        if output_tokens == 0:
            output_tokens = max(1, len(text_content) // 4)

        return StreamResult(
            ttft_ms=ttft_ms or t_total,
            total_time_ms=t_total,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            text=text_content,
        )


class OllamaClient(LLMClient):
    """
    Streaming HTTP client for local Ollama instances.
    """

    def __init__(
        self,
        host: str = "http://localhost:11434",
        model: str = "qwen2.5-coder:7b",
        num_threads: int = 4,
    ) -> None:
        self.host = host.rstrip("/")
        self.model = model
        self.num_threads = num_threads

    def generate_stream(
        self,
        prompt: str,
        temperature: float = 0.0,
        seed: int = 42,
    ) -> StreamResult:
        url = f"{self.host}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": True,
            "options": {
                "temperature": temperature,
                "seed": seed,
                "num_thread": self.num_threads,
            },
        }

        t_start = time.perf_counter()
        ttft_ms = 0.0
        full_text: list[str] = []
        prompt_eval_count = 0
        eval_count = 0

        resp = requests.post(url, json=payload, stream=True, timeout=120.0)
        resp.raise_for_status()

        for line in resp.iter_lines():
            if not line:
                continue
            chunk = json.loads(line.decode("utf-8"))
            resp_str = chunk.get("response", "")
            if resp_str:
                if not ttft_ms:
                    ttft_ms = (time.perf_counter() - t_start) * 1000.0
                full_text.append(resp_str)

            if chunk.get("done"):
                prompt_eval_count = chunk.get("prompt_eval_count", 0)
                eval_count = chunk.get("eval_count", 0)

        t_total = (time.perf_counter() - t_start) * 1000.0
        text_content = "".join(full_text)

        if prompt_eval_count == 0:
            prompt_eval_count = max(1, len(prompt) // 4)
        if eval_count == 0:
            eval_count = max(1, len(text_content) // 4)

        return StreamResult(
            ttft_ms=ttft_ms or t_total,
            total_time_ms=t_total,
            input_tokens=prompt_eval_count,
            output_tokens=eval_count,
            text=text_content,
        )


class MockClient(LLMClient):
    """Deterministic offline client simulating valid responses for benchmark sandboxes."""

    def __init__(self, model: str = "mock-model") -> None:
        self.model = model

    def generate_stream(
        self,
        prompt: str,
        temperature: float = 0.0,
        seed: int = 42,
    ) -> StreamResult:
        in_tokens = max(1, len(prompt) // 4)

        if "TransactionRiskEvaluator" in prompt or "evaluate_transaction" in prompt:
            code = """
```python
def evaluate_transaction(
    self,
    transaction_id: str,
    user_id: str,
    amount: float,
    recent_count: int,
    is_international: bool = False,
) -> RiskAssessment:
    if amount <= 0.0:
        raise ValueError("Amount must be positive")
    score = 0.0
    reasons = []
    if amount > self.max_daily_limit:
        score += 40.0
        reasons.append("EXCEEDS_DAILY_LIMIT")
    if self.evaluate_velocity(recent_count):
        score += 30.0
        reasons.append("HIGH_VELOCITY_BURST")
    if is_international:
        score += 20.0
        reasons.append("CROSS_BORDER_RISK")
    score = max(0.0, min(100.0, score))
    if score >= 80.0:
        lvl = RiskLevel.CRITICAL
    elif score >= 50.0:
        lvl = RiskLevel.HIGH
    elif score >= 20.0:
        lvl = RiskLevel.MEDIUM
    else:
        lvl = RiskLevel.LOW
    chk = self.calculate_checksum(transaction_id, amount, user_id)
    return RiskAssessment(score=score, level=lvl, flagged_reasons=reasons, checksum=chk)
```
"""
        elif "OrderOrchestrator" in prompt or "process_order_checkout" in prompt:
            code = """
```python
def process_order_checkout(self, order: Order) -> Invoice | None:
    self.orders[order.id] = order
    if not self.validate_order(order):
        order.status = OrderStatus.FAILED
        self.notifier.notify_order_failed(order.customer_id, "Fallo al validar orden")
        return None
    if not self.inventory.lock_and_reserve(order.items):
        order.status = OrderStatus.FAILED
        self.notifier.notify_order_failed(order.customer_id, "Stock no disponible")
        return None
    res = self.payment.charge_customer(order.customer_id, order.total_amount)
    if res.status != PaymentStatus.CAPTURED:
        self.inventory.release_reserved_stock(order.items)
        order.status = OrderStatus.FAILED
        self.notifier.notify_order_failed(order.customer_id, "Pago declinado")
        return None
    order.status = OrderStatus.PAID
    inv_id = f"inv_{order.id}"
    invoice = Invoice(invoice_id=inv_id, order_id=order.id, total_amount=order.total_amount)
    self.notifier.notify_order_approved(order.customer_id, inv_id)
    return invoice
```
"""
        else:
            code = """
```python
def execute(self, tenant_id: str, email: str, plain_password: str) -> User:
    clean_email = email.strip().lower()
    if not self.validate_password_strength(plain_password):
        self.audit_logger.log_security_event("REGISTRATION_FAILED_WEAK_PASSWORD", tenant_id, {"email": clean_email})
        raise InvalidPasswordComplexityError("Password does not meet enterprise complexity.")
    existing = self.user_repo.find_by_email(tenant_id, clean_email)
    if existing is not None:
        self.audit_logger.log_security_event("REGISTRATION_FAILED_DUPLICATE_EMAIL", tenant_id, {"email": clean_email})
        raise EmailAlreadyExistsError(f"Email '{clean_email}' already registered.")
    hashed_pw = self.hasher.hash_password(plain_password)
    token = self.token_gen.generate_token({"email": clean_email, "tenant": tenant_id})
    user = User(
        id=f"usr_{tenant_id}_{clean_email}",
        email=clean_email,
        password_hash=hashed_pw,
        tenant_id=tenant_id,
        roles=[Role.USER],
        status=UserStatus.PENDING_ACTIVATION,
        activation_token=token,
    )
    self.user_repo.save(user)
    self.audit_logger.log_security_event("USER_REGISTERED_SUCCESS", tenant_id, {"user_id": user.id, "email": clean_email})
    activation_link = f"https://auth.enterprise.com/activate?token={token}"
    self.email_dispatcher.send_welcome_email(clean_email, activation_link)
    return user
```
"""
        out_tokens = max(1, len(code) // 4)
        return StreamResult(
            ttft_ms=5.0,
            total_time_ms=25.0,
            input_tokens=in_tokens,
            output_tokens=out_tokens,
            text=code,
        )


def create_client(
    backend: str = "gemini",
    model: str | None = None,
    host: str = "http://localhost:11434",
    api_key: str | None = None,
) -> LLMClient:
    """Factory for inference clients."""
    if backend.lower() == "gemini":
        target_model = model or "gemini-3.8-flash"
        return GeminiClient(api_key=api_key, model=target_model)
    elif backend.lower() == "ollama":
        target_model = model or "qwen2.5-coder:3b"
        return OllamaClient(host=host, model=target_model)
    elif backend.lower() in ("mock", "dry_run"):
        target_model = model or "mock-model"
        return MockClient(model=target_model)
    else:
        raise ValueError(f"Unsupported backend '{backend}'. Choose 'gemini', 'ollama', or 'mock'.")

