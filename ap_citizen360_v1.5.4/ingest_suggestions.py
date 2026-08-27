#!/usr/bin/env python3
"""
Few-Shot Suggestions Ingestion & Cache Builder (ap_citizen360_v1.5.4)
====================================================================
Ingests fewshot questions from JSONL files (e.g. new_fewshots.jsonl, fewshots_combined.jsonl),
matches/generates 768-dim embeddings from Milvus DB parquet store (or Ollama fallback),
removes all raw SQL to ensure secure client-side usage, and persists the cache to disk.

Usage:
    python ingest_suggestions.py
    python ingest_suggestions.py --file new_fewshots.jsonl
    python ingest_suggestions.py --file fewshots_combined.jsonl --output database/fewshot_suggestions_cache.json --force
    python ingest_suggestions.py --help
"""

import os
import sys
import json
import argparse
import logging
from pathlib import Path
from typing import Any

# Ensure project root is on sys.path
CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from database.suggestions import (
    get_fewshots_jsonl_path,
    load_parquet_fewshots,
    normalize_key,
    build_suggestions_from_file,
    get_cache_file_mtime,
    CACHE_FILE,
    APP_ROOT,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("ingest_suggestions")


def generate_ollama_embedding(
    text: str,
    model: str = "nomic-embed-text",
    ollama_url: str | None = None,
) -> list[float]:
    """Generates embedding vector via Ollama for queries not yet in Milvus parquet."""
    import requests

    base_url = ollama_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    url = f"{base_url}/api/embeddings"
    res = requests.post(url, json={"model": model, "prompt": text[:4096]}, timeout=60)
    res.raise_for_status()
    return res.json().get("embedding", [])


def ingest_fewshot_suggestions(
    input_file: str | Path | None = None,
    output_cache: str | Path | None = None,
    force: bool = False,
    embed_missing: bool = False,
    verify: bool = True,
) -> dict[str, Any]:
    """
    Ingests fewshot questions, attaches precomputed/generated vector embeddings,
    strips raw SQL, and writes the cache JSON file.
    """
    jsonl_path = get_fewshots_jsonl_path(input_file)
    if not jsonl_path or not jsonl_path.is_file():
        raise FileNotFoundError(
            f"Fewshots file not found: '{input_file}'. Checked candidates in {APP_ROOT}."
        )

    out_path = Path(output_cache).resolve() if output_cache else CACHE_FILE.resolve()

    logger.info("=" * 70)
    logger.info("FEW-SHOT SUGGESTIONS INGESTION")
    logger.info("=" * 70)
    logger.info(f"Source JSONL file   : {jsonl_path}")
    logger.info(f"Target Cache file   : {out_path}")
    logger.info(f"Force overwrite     : {force}")

    # 1. Load parquet embeddings from Milvus few_shot_store
    parquet_embeddings = load_parquet_fewshots()
    logger.info(f"Precomputed parquet embeddings loaded: {len(parquet_embeddings)} vectors")

    # 2. Parse source JSONL
    items = build_suggestions_from_file(jsonl_path, parquet_embeddings)
    total_items = len(items)
    logger.info(f"Parsed {total_items} questions from {jsonl_path.name}")

    # 3. Check for missing embeddings & optionally generate
    matched_embs = sum(1 for item in items if len(item.get("embedding", [])) == 768)
    missing_count = total_items - matched_embs

    if missing_count > 0:
        logger.warning(f"Found {missing_count} questions without precomputed parquet embeddings.")
        if embed_missing:
            logger.info("Generating missing embeddings via Ollama...")
            generated = 0
            for item in items:
                if len(item.get("embedding", [])) != 768:
                    try:
                        emb = generate_ollama_embedding(item["question"])
                        if len(emb) == 768:
                            item["embedding"] = emb
                            generated += 1
                    except Exception as e:
                        logger.warning(f"Failed to generate embedding for '{item['question'][:40]}...': {e}")
            logger.info(f"Generated {generated} missing embeddings via Ollama.")
            matched_embs = sum(1 for item in items if len(item.get("embedding", [])) == 768)
        else:
            logger.info("Tip: Pass --embed-missing to generate vectors via Ollama for missing questions.")
    else:
        logger.info(f"100% of questions ({matched_embs}/{total_items}) matched Milvus 768-dim embeddings.")

    # 4. Strip any residual SQL (ensure security & zero SQL leakage)
    for item in items:
        if "sql" in item:
            del item["sql"]

    # 5. Persist to cache file
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False)

    file_size_kb = round(out_path.stat().st_size / 1024, 2)
    mtime = get_cache_file_mtime(out_path)

    logger.info(f"Successfully saved {len(items)} suggestions to {out_path} ({file_size_kb} KB)")

    # 6. Verification assertions if requested
    if verify:
        logger.info("Running verification assertions...")
        assert out_path.is_file(), f"Output file {out_path} does not exist!"
        with open(out_path, "r", encoding="utf-8") as f:
            verified_data = json.load(f)
        assert len(verified_data) == total_items, f"Count mismatch: {len(verified_data)} vs {total_items}"
        assert not any("sql" in s for s in verified_data), "Security failure: raw SQL found in output cache!"
        logger.info("Verification passed: Count matches, 0 SQL leaks, valid JSON.")

    logger.info("=" * 70)
    logger.info("INGESTION COMPLETED SUCCESSFULLY!")
    logger.info("=" * 70)

    return {
        "status": "success",
        "source_file": str(jsonl_path),
        "cache_file": str(out_path),
        "total_count": total_items,
        "embeddings_count": matched_embs,
        "file_size_kb": file_size_kb,
        "updated_at": mtime,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Ingest few-shot questions and compile the suggestions cache."
    )
    parser.add_argument(
        "-f", "--file",
        dest="input_file",
        default=None,
        help="Path or name of fewshot JSONL file (defaults to new_fewshots.jsonl or fewshots_combined.jsonl).",
    )
    parser.add_argument(
        "-o", "--output",
        dest="output_cache",
        default=None,
        help=f"Target cache JSON path (defaults to {CACHE_FILE}).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force overwrite existing cache file.",
    )
    parser.add_argument(
        "--embed-missing",
        action="store_true",
        help="Call Ollama embedding endpoint to generate vectors for questions not in parquet store.",
    )
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="Skip post-generation verification checks.",
    )

    args = parser.parse_args()

    try:
        res = ingest_fewshot_suggestions(
            input_file=args.input_file,
            output_cache=args.output_cache,
            force=args.force,
            embed_missing=args.embed_missing,
            verify=not args.no_verify,
        )
        print(json.dumps(res, indent=2))
    except Exception as e:
        logger.error(f"Ingestion failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
