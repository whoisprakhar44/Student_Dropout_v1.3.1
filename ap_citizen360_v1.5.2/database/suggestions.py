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


def get_fewshots_jsonl_path(custom_path: str | Path | None = None) -> Path | None:
    """
    Finds fewshots JSONL file within v1.5.4.
    Prioritizes custom_path, then FEWSHOTS_FILE env, then new_fewshots.jsonl,
    followed by fewshots_combined.jsonl.
    """
    if custom_path:
        p = Path(custom_path)
        if p.is_file():
            return p.resolve()
        if (APP_ROOT / custom_path).is_file():
            return (APP_ROOT / custom_path).resolve()
        if (CURRENT_DIR / custom_path).is_file():
            return (CURRENT_DIR / custom_path).resolve()

    env_path = os.getenv("FEWSHOTS_FILE")
    if env_path:
        p = Path(env_path)
        if p.is_file():
            return p.resolve()
        if (APP_ROOT / env_path).is_file():
            return (APP_ROOT / env_path).resolve()

    candidates = [
        APP_ROOT / "new_fewshots.jsonl",
        APP_ROOT / "fewshots_combined.jsonl",
        APP_ROOT.parent / "new_fewshots.jsonl",
        APP_ROOT.parent / "fewshots_combined.jsonl",
    ]
    for p in candidates:
        if p.is_file():
            return p.resolve()
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


def get_cache_file_mtime(cache_path: Path | None = None) -> str:
    """Returns the ISO 8601 modification timestamp of the cache file."""
    target = cache_path or CACHE_FILE
    if target.is_file():
        mtime = os.path.getmtime(target)
        return datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
    return datetime.now(timezone.utc).isoformat()


def build_suggestions_from_file(
    jsonl_path: Path,
    parquet_embeddings: dict[str, list[float]] | None = None,
) -> list[dict[str, Any]]:
    """
    Parses a fewshots JSONL file and pairs questions with vector embeddings.
    Strictly excludes raw SQL from the output suggestion records.
    """
    if parquet_embeddings is None:
        parquet_embeddings = load_parquet_fewshots()

    suggestions: list[dict[str, Any]] = []
    if not jsonl_path.is_file():
        logger.warning(f"Fewshots file not found: {jsonl_path}")
        return suggestions

    with open(jsonl_path, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
                q = row.get("question", "").strip()
                if not q:
                    continue

                emb = parquet_embeddings.get(normalize_key(q), [])

                item: dict[str, Any] = {
                    "id": str(row.get("id", f"fewshot_{idx:03d}")),
                    "question": q,
                    "intent": row.get("intent", ""),
                    "topic": row.get("topic", ""),
                    "difficulty": row.get("difficulty", ""),
                    "use_case": row.get("use_case", ""),
                    "embedding": emb,
                }

                # Optional metadata from extended schemas (e.g. new_fewshots)
                if "degree" in row:
                    item["degree"] = str(row["degree"])
                if "tables" in row:
                    item["tables"] = row["tables"]

                suggestions.append(item)
            except Exception as e:
                logger.warning(f"Error parsing line {idx} in {jsonl_path}: {e}")

    return suggestions


def load_or_build_suggestions(
    force_refresh: bool = False,
    file_path: str | Path | None = None,
    cache_path: Path | None = None,
) -> list[dict[str, Any]]:
    """
    Returns the list of fewshot items with pre-computed vector embeddings.
    
    1. If file_path is not specified and memory cache is valid (and not force_refresh),
       returns in-memory cache.
    2. If cache JSON file exists on disk (and not force_refresh), loads and returns it.
    3. Otherwise, parses questions from the JSONL file (defaulting to new_fewshots.jsonl),
       attaches Milvus embeddings, persists to cache JSON file, and updates memory cache.
    """
    global _SUGGESTIONS_CACHE, _CACHE_UPDATED_AT

    target_cache = cache_path or CACHE_FILE

    if _SUGGESTIONS_CACHE is not None and not force_refresh and file_path is None:
        return _SUGGESTIONS_CACHE

    # 1. Try reading from disk cache if no custom file is specified and no refresh forced
    if not force_refresh and file_path is None and target_cache.is_file():
        try:
            with open(target_cache, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list) and len(data) > 0:
                    _SUGGESTIONS_CACHE = data
                    _CACHE_UPDATED_AT = get_cache_file_mtime(target_cache)
                    logger.info(f"Loaded {len(data)} fewshots from disk cache {target_cache}.")
                    return _SUGGESTIONS_CACHE
        except Exception as e:
            logger.warning(f"Could not load suggestions from disk cache: {e}")

    # 2. Read embeddings directly from Milvus parquet
    parquet_embeddings = load_parquet_fewshots()

    # 3. Resolve JSONL file path
    jsonl_path = get_fewshots_jsonl_path(file_path)
    if not jsonl_path or not jsonl_path.is_file():
        logger.error(f"Fewshot source file could not be found: {file_path or 'candidates'}")
        if _SUGGESTIONS_CACHE is not None:
            return _SUGGESTIONS_CACHE
        return []

    # 4. Build suggestions from JSONL and attach embeddings
    suggestions = build_suggestions_from_file(jsonl_path, parquet_embeddings)

    # 5. Save to disk cache
    try:
        target_cache.parent.mkdir(parents=True, exist_ok=True)
        with open(target_cache, "w", encoding="utf-8") as f:
            json.dump(suggestions, f, ensure_ascii=False)
        _CACHE_UPDATED_AT = get_cache_file_mtime(target_cache)
        logger.info(f"Persisted {len(suggestions)} fewshot suggestions from {jsonl_path.name} to {target_cache}")
    except Exception as e:
        logger.warning(f"Failed to persist suggestions cache to disk: {e}")
        _CACHE_UPDATED_AT = datetime.now(timezone.utc).isoformat()

    _SUGGESTIONS_CACHE = suggestions
    return _SUGGESTIONS_CACHE


def get_cache_metadata(cache_path: Path | None = None) -> dict[str, Any]:
    """Returns metadata about the cache (timestamp, total count, status)."""
    target_cache = cache_path or CACHE_FILE
    items = load_or_build_suggestions(cache_path=target_cache)
    global _CACHE_UPDATED_AT
    if not _CACHE_UPDATED_AT:
        _CACHE_UPDATED_AT = get_cache_file_mtime(target_cache)
    return {
        "status": "success",
        "count": len(items),
        "updated_at": _CACHE_UPDATED_AT,
        "cache_file": str(target_cache.name),
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

