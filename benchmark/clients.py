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


class GeminiClient(LLMClient):
    """
    Direct REST streaming client for Gemini API using Server-Sent Events / chunked JSON.
    No heavy external SDKs required; uses standard requests.
    """

    def __init__(self, api_key: str | None = None, model: str = "gemini-3.8-flash") -> None:
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable not set.")
        self.model = model

    def generate_stream(
        self,
        prompt: str,
        temperature: float = 0.0,
        seed: int = 42,
    ) -> StreamResult:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:streamGenerateContent"
            f"?alt=sse&key={self.api_key}"
        )
        payload = {
            "contents": [
                {
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": {
                "temperature": temperature,
                "seed": seed,
            },
        }

        t_start = time.perf_counter()
        ttft_ms = 0.0
        full_text: list[str] = []
        input_tokens = 0
        output_tokens = 0

        resp = requests.post(url, json=payload, stream=True, timeout=60.0)
        resp.raise_for_status()

        for line in resp.iter_lines():
            if not line:
                continue
            line_str = line.decode("utf-8")
            if line_str.startswith("data: "):
                data_json = line_str[6:].strip()
                if not data_json:
                    continue
                try:
                    chunk = json.loads(data_json)
                except json.JSONDecodeError:
                    continue

                # Capture TTFT on first text payload
                candidates = chunk.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    for part in parts:
                        text_chunk = part.get("text", "")
                        if text_chunk:
                            if not ttft_ms:
                                ttft_ms = (time.perf_counter() - t_start) * 1000.0
                            full_text.append(text_chunk)

                usage = chunk.get("usageMetadata")
                if usage:
                    input_tokens = usage.get("promptTokenCount", input_tokens)
                    output_tokens = usage.get("candidatesTokenCount", output_tokens)

        t_total = (time.perf_counter() - t_start) * 1000.0
        text_content = "".join(full_text)

        # Fallback estimation if metadata was missing
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

    def __init__(self, host: str = "http://localhost:11434", model: str = "qwen2.5-coder:3b") -> None:
        self.host = host.rstrip("/")
        self.model = model

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
            "temperature": temperature,
            "seed": seed,
            "stream": True,
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
    else:
        raise ValueError(f"Unsupported backend '{backend}'. Choose 'gemini' or 'ollama'.")
