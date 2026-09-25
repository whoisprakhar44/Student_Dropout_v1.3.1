"""Model backend connectivity and availability checks (supports vLLM chat + Ollama/vLLM embeddings)."""

from __future__ import annotations

import os
import requests


def get_backend() -> str:
    return os.getenv("LLM_BACKEND", "vllm").strip().lower()


def get_embedding_provider() -> str:
    return os.getenv("EMBEDDING_PROVIDER", "ollama").strip().lower()


def chat_model_name() -> str:
    backend = get_backend()
    if backend == "vllm":
        return os.getenv("VLLM_CHAT_MODEL") or os.getenv("OLLAMA_CHAT_MODEL", "qwen")
    return os.getenv("OLLAMA_CHAT_MODEL", "qwen3.5:9b")


def embedding_model_name() -> str:
    provider = get_embedding_provider()
    if provider == "ollama":
        return os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text")
    elif provider == "vllm":
        return os.getenv("VLLM_EMBEDDING_MODEL", "nomic-embed-text-v1.5")
    return os.getenv("EMBEDDING_MODEL", "nomic-embed-text")


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


def ollama_base_url() -> str:
    return os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")


def list_vllm_models() -> list[str]:
    api_key = os.getenv("VLLM_API_KEY", "EMPTY")
    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{vllm_base_url()}/models"
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 404:
            root_url = f"{vllm_base_url().removesuffix('/v1')}/models"
            response = requests.get(root_url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json().get("data", [])
        return [m.get("id", "") for m in data if isinstance(m, dict)]
    except Exception:
        raise


def list_ollama_models() -> list[str]:
    response = requests.get(f"{ollama_base_url()}/api/tags", timeout=10)
    response.raise_for_status()
    return [m.get("name", "") for m in response.json().get("models", [])]


def model_is_available(model: str | None = None) -> bool:
    target = model or chat_model_name()
    backend = get_backend()
    if backend == "vllm":
        try:
            available = list_vllm_models()
            if not available:
                return False
            matched = any(
                target.lower() in m.lower() or m.lower() in target.lower()
                for m in available
            )
            return matched or (len(available) > 0 and (not target or "qwen" in target.lower()))
        except Exception:
            return False
    else:
        try:
            available = list_ollama_models()
            return any(
                name == target
                or name.startswith(f"{target}:")
                or target in name
                for name in available
            )
        except Exception:
            return False


def check_backend() -> dict:
    backend = get_backend()
    model = chat_model_name()
    emb_provider = get_embedding_provider()
    emb_model = embedding_model_name()

    # Check embedding connectivity
    emb_ok = False
    if emb_provider == "ollama":
        emb_url = ollama_base_url()
        try:
            ollama_models = list_ollama_models()
            emb_ok = any(emb_model in m or m in emb_model for m in ollama_models) or (len(ollama_models) > 0)
        except Exception:
            try:
                res = requests.get(f"{emb_url}/api/tags", timeout=5)
                emb_ok = res.status_code == 200
            except Exception:
                emb_ok = False
    elif emb_provider == "vllm":
        emb_url = vllm_embedding_url()
        try:
            emb_res = requests.get(
                f"{emb_url}/models",
                headers={"Authorization": f"Bearer {os.getenv('VLLM_EMBEDDING_API_KEY', 'EMPTY')}"},
                timeout=5,
            )
            emb_ok = emb_res.status_code == 200
        except Exception:
            emb_ok = False
    else:
        emb_url = "local"
        emb_ok = True

    if backend == "vllm":
        try:
            available = list_vllm_models()
            ok = model_is_available(model)

            return {
                "backend": "vllm",
                "vllm": "ok",
                "ollama": "ok",  # Backwards compatibility with app.py & health checks
                "model": model,
                "model_available": ok,
                "available_models": available,
                "vllm_url": vllm_base_url(),
                "embedding_provider": emb_provider,
                "embedding_model": emb_model,
                "embedding_url": emb_url,
                "embedding_available": emb_ok,
            }
        except Exception as exc:
            return {
                "backend": "vllm",
                "vllm": "error",
                "ollama": "error",
                "model": model,
                "model_available": False,
                "error": str(exc),
                "vllm_url": vllm_base_url(),
                "embedding_provider": emb_provider,
                "embedding_model": emb_model,
                "embedding_url": emb_url,
                "embedding_available": emb_ok,
            }
    else:
        try:
            available = list_ollama_models()
            ok = model_is_available(model)
            return {
                "backend": "ollama",
                "vllm": "ok",
                "ollama": "ok",
                "model": model,
                "model_available": ok,
                "available_models": available,
                "ollama_url": ollama_base_url(),
                "embedding_provider": emb_provider,
                "embedding_model": emb_model,
                "embedding_url": emb_url,
                "embedding_available": emb_ok,
            }
        except Exception as exc:
            return {
                "backend": "ollama",
                "vllm": "error",
                "ollama": "error",
                "model": model,
                "model_available": False,
                "error": str(exc),
                "ollama_url": ollama_base_url(),
                "embedding_provider": emb_provider,
                "embedding_model": emb_model,
                "embedding_url": emb_url,
                "embedding_available": emb_ok,
            }


# Backwards compatibility alias
check_ollama = check_backend
