"""vLLM connectivity and model availability checks."""

from __future__ import annotations

import os

import requests


def chat_model_name() -> str:
    return os.getenv("VLLM_MODEL", "qwen3.5:0.8b-mlx")


def vllm_base_url() -> str:
    return os.getenv("VLLM_BASE_URL", "http://localhost:8000/v1").rstrip("/")


def _vllm_root_url() -> str:
    """Return the vLLM server root (without /v1 suffix)."""
    url = vllm_base_url()
    if url.endswith("/v1"):
        return url[:-3]
    return url


def list_vllm_models() -> list[str]:
    response = requests.get(f"{vllm_base_url()}/models", timeout=10)
    response.raise_for_status()
    return [m.get("id", "") for m in response.json().get("data", [])]


def model_is_available(model: str | None = None) -> bool:
    target = model or chat_model_name()
    available = list_vllm_models()
    return any(
        name == target
        or name.startswith(f"{target}:")
        or target in name
        for name in available
    )


def check_llm() -> dict:
    """Check vLLM server health and model availability."""
    model = chat_model_name()
    try:
        # Check health endpoint first
        health_url = f"{_vllm_root_url()}/health"
        health_resp = requests.get(health_url, timeout=10)
        server_ok = health_resp.status_code == 200

        available = list_vllm_models()
        ok = model_is_available(model)
        return {
            "llm_server": "ok" if server_ok else "degraded",
            "model": model,
            "model_available": ok,
            "available_models": available,
        }
    except Exception as exc:
        return {
            "llm_server": "error",
            "model": model,
            "model_available": False,
            "error": str(exc),
        }


# Backward compatibility aliases
check_ollama = check_llm
