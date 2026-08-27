"""
Few-Shot Suggestions Service & Cache Manager (ap_citizen360_v1.5.4)
==================================================================
Reads strictly from ap_citizen360_v1.5.4/fewshots_combined.jsonl and pre-computed
768-dim vector embeddings directly from ap_citizen360_v1.5.4/milvus_schemas.db,
caches them in-memory and on disk (without raw SQL statements), and provides cache
timestamp metadata so the frontend can cache the full list in the browser and
handle 100% of the ranking client-side.
"""

import os
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("suggestions_service")

CURRENT_DIR = Path(__file__).resolve().parent
APP_ROOT = CURRENT_DIR.parent
CACHE_FILE = CURRENT_DIR / "fewshot_suggestions_cache.json"

# Global in-memory cache
_SUGGESTIONS_CACHE: list[dict[str, Any]] | None = None
_CACHE_UPDATED_AT: str | None = None


def get_parquet_dirs() -> list[Path]:
    """Finds Milvus DB few_shot_store parquet directories within v1.5.4."""
    candidates = [
        APP_ROOT / "milvus_schemas.db" / "collections" / "schema_chunks" / "partitions" / "few_shot_store" / "data",
        APP_ROOT.parent / "milvus_schemas.db" / "collections" / "schema_chunks" / "partitions" / "few_shot_store" / "data",
    ]
    return [p for p in candidates if p.is_dir()]


def get_fewshots_jsonl_path() -> Path | None:
    """Finds fewshots_combined.jsonl within v1.5.4."""
    candidates = [
        APP_ROOT / "fewshots_combined.jsonl",
        APP_ROOT.parent / "fewshots_combined.jsonl",
    ]
    for p in candidates:
        if p.is_file():
            return p
    return None


def normalize_key(text: str) -> str:
    """Normalizes string for robust dictionary matching."""
    return " ".join(str(text).strip().lower().split())


def load_parquet_fewshots() -> dict[str, list[float]]:
    """Loads embedding vectors mapped by question text from Milvus few_shot_store parquet."""
    embeddings_map: dict[str, list[float]] = {}
    p_dirs = get_parquet_dirs()
    if not p_dirs:
        return embeddings_map

    try:
        import pandas as pd
        for p_dir in p_dirs:
            for p_file in p_dir.glob("*.parquet"):
                try:
                    df = pd.read_parquet(p_file)
                    for _, row in df.iterrows():
                        q_text = row.get("embedding_text") or row.get("question")
                        if not q_text:
                            continue
                        emb = row.get("embedding")
                        if emb is not None and hasattr(emb, "tolist"):
                            emb = emb.tolist()
                        elif emb is not None and isinstance(emb, list):
                            emb = list(emb)
                        else:
                            emb = []
                        if emb:
                            embeddings_map[normalize_key(q_text)] = emb
                except Exception as e:
                    logger.warning(f"Could not read parquet {p_file}: {e}")
    except Exception as e:
        logger.warning(f"Could not load parquet embeddings: {e}")

    return embeddings_map


def get_cache_file_mtime() -> str:
    """Returns the ISO 8601 modification timestamp of the cache file."""
    if CACHE_FILE.is_file():
        mtime = os.path.getmtime(CACHE_FILE)
        return datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
    return datetime.now(timezone.utc).isoformat()


def load_or_build_suggestions(force_refresh: bool = False) -> list[dict[str, Any]]:
    """
    Returns the list of fewshot items strictly from fewshots_combined.jsonl
    with vector embeddings from Milvus DB (without SQL queries).
    """
    global _SUGGESTIONS_CACHE, _CACHE_UPDATED_AT

    if _SUGGESTIONS_CACHE is not None and not force_refresh:
        return _SUGGESTIONS_CACHE

    # 1. Try reading from disk cache
    if not force_refresh and CACHE_FILE.is_file():
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list) and len(data) > 0:
                    _SUGGESTIONS_CACHE = data
                    _CACHE_UPDATED_AT = get_cache_file_mtime()
                    logger.info(f"Loaded {len(data)} fewshots from disk cache {CACHE_FILE}.")
                    return _SUGGESTIONS_CACHE
        except Exception as e:
            logger.warning(f"Could not load suggestions from disk cache: {e}")

    # 2. Read embeddings directly from Milvus parquet
    parquet_embeddings = load_parquet_fewshots()

    # 3. Read strictly questions from fewshots_combined.jsonl
    jsonl_path = get_fewshots_jsonl_path()
    suggestions: list[dict[str, Any]] = []

    if jsonl_path and jsonl_path.is_file():
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for idx, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                    q = row.get("question", "").strip()
                    emb = parquet_embeddings.get(normalize_key(q), [])

                    # Store only question and its embedding (no raw SQL stored)
                    suggestions.append({
                        "id": row.get("id", f"fewshot_{idx:03d}"),
                        "question": q,
                        "intent": row.get("intent", ""),
                        "topic": row.get("topic", ""),
                        "difficulty": row.get("difficulty", ""),
                        "use_case": row.get("use_case", ""),
                        "embedding": emb,
                    })
                except Exception as e:
                    logger.warning(f"Error parsing line {idx} in {jsonl_path}: {e}")

    # 4. Save to disk cache
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(suggestions, f, ensure_ascii=False)
        _CACHE_UPDATED_AT = get_cache_file_mtime()
        logger.info(f"Persisted {len(suggestions)} fewshot suggestions to {CACHE_FILE}")
    except Exception as e:
        logger.warning(f"Failed to persist suggestions cache to disk: {e}")
        _CACHE_UPDATED_AT = datetime.now(timezone.utc).isoformat()

    _SUGGESTIONS_CACHE = suggestions
    return _SUGGESTIONS_CACHE


def get_cache_metadata() -> dict[str, Any]:
    """Returns metadata about the cache (timestamp, total count, status)."""
    items = load_or_build_suggestions()
    global _CACHE_UPDATED_AT
    if not _CACHE_UPDATED_AT:
        _CACHE_UPDATED_AT = get_cache_file_mtime()
    return {
        "status": "success",
        "count": len(items),
        "updated_at": _CACHE_UPDATED_AT,
        "cache_file": str(CACHE_FILE.name),
    }


def get_fewshot_suggestions(limit: int | None = None) -> list[dict[str, Any]]:
    """
    Returns raw fewshot suggestions list.
    If limit is -1, None, or <= 0, returns ALL items.
    If limit > 0, returns the first `limit` items.
    """
    suggestions = load_or_build_suggestions()
    if limit is not None and limit > 0:
        return suggestions[:limit]
    return suggestions
