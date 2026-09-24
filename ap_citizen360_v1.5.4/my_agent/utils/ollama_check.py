"""Model backend connectivity and availability checks (vLLM backend)."""

from __future__ import annotations

import os
import requests


def get_backend() -> str:
    return os.getenv("LLM_BACKEND", "vllm").strip().lower()


def chat_model_name() -> str:
    return os.getenv("VLLM_CHAT_MODEL", "qwen")


def vllm_base_url() -> str:
    url = os.getenv("VLLM_BASE_URL", "http://localhost:8000/v1").rstrip("/")
    if not url.endswith("/v1"):
        url = f"{url}/v1"
    return url


def vllm_embedding_url() -> str:
    url = os.getenv("VLLM_EMBEDDING_BASE_URL", "http://localhost:8005/v1").rstrip("/")
    if not url.endswith("/v1"):
        url = f"{url}/v1"
    return url


def list_vllm_models() -> list[str]:
    api_key = os.getenv("VLLM_API_KEY", "EMPTY")
    headers = {"Authorization": f"Bearer {api_key}"}
    response = requests.get(f"{vllm_base_url()}/models", headers=headers, timeout=10)
    response.raise_for_status()
    data = response.json().get("data", [])
    return [m.get("id", "") for m in data if isinstance(m, dict)]


def model_is_available(model: str | None = None) -> bool:
    target = model or chat_model_name()
    try:
        available = list_vllm_models()
        if not available:
            return False
        # Check for direct or substring match (e.g. "qwen" in "Qwen/Qwen2.5-7B-Instruct")
        matched = any(
            target.lower() in m.lower() or m.lower() in target.lower()
            for m in available
        )
        return matched or (len(available) > 0 and (not target or "qwen" in target.lower()))
    except Exception:
        return False


def check_backend() -> dict:
    model = chat_model_name()
    try:
        available = list_vllm_models()
        ok = model_is_available(model)

        # Check embedding service on port 8005
        emb_model = os.getenv("VLLM_EMBEDDING_MODEL", "nomic-embed-text-v1.5")
        emb_ok = False
        try:
            emb_res = requests.get(
                f"{vllm_embedding_url()}/models",
                headers={"Authorization": f"Bearer {os.getenv('VLLM_EMBEDDING_API_KEY', 'EMPTY')}"},
                timeout=5,
            )
            emb_ok = emb_res.status_code == 200
        except Exception:
            emb_ok = False

        return {
            "backend": "vllm",
            "vllm": "ok",
            "model": model,
            "model_available": ok,
            "available_models": available,
            "vllm_url": vllm_base_url(),
            "embedding_model": emb_model,
            "embedding_url": vllm_embedding_url(),
            "embedding_available": emb_ok,
        }
    except Exception as exc:
        return {
            "backend": "vllm",
            "vllm": "error",
            "model": model,
            "model_available": False,
            "error": str(exc),
            "vllm_url": vllm_base_url(),
        }


# Backwards compatibility aliases
check_ollama = check_backend
list_ollama_models = list_vllm_models
ollama_base_url = vllm_base_url
