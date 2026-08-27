"""
Local suggestions & cache verification test for ap_citizen360_v1.5.4
====================================================================
Validates suggestions caching and ingestion features within ap_citizen360_v1.5.4:
1. Loads 200 few-shot questions from new_fewshots.jsonl (default).
2. 100% (200/200) pre-computed 768-dim embeddings from Milvus DB parquet.
3. No raw SQL stored in cache or served.
4. Cache metadata contains valid updated_at timestamp and item count.
5. get_fewshot_suggestions(limit=-1) returns all 200 items.
6. Custom file path ingestion support (e.g. fewshots_combined.jsonl).
"""

import os
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(CURRENT_DIR))

from database.suggestions import (
    load_or_build_suggestions,
    get_fewshot_suggestions,
    get_cache_metadata,
)
from ingest_suggestions import ingest_fewshot_suggestions


def run_local_tests():
    print("=" * 70)
    print("Running Local Verification on ap_citizen360_v1.5.4")
    print("=" * 70)

    # 1. Force ingest new_fewshots.jsonl
    print("[1] Ingesting new_fewshots.jsonl...")
    res = ingest_fewshot_suggestions(
        input_file="new_fewshots.jsonl",
        force=True,
        verify=True,
    )
    assert res["status"] == "success"
    assert res["total_count"] == 200
    assert res["embeddings_count"] == 200

    # 2. Test cache metadata
    meta = get_cache_metadata()
    print(f"[OK] Cache metadata: {meta}")
    assert meta["status"] == "success"
    assert meta["count"] == 200, f"Expected 200, got {meta['count']}"
    assert "updated_at" in meta and len(meta["updated_at"]) > 0

    # 3. Test limit=-1
    all_items = get_fewshot_suggestions(limit=-1)
    print(f"[OK] Total items returned with limit=-1: {len(all_items)}")
    assert len(all_items) == 200, f"Expected 200, got {len(all_items)}"

    # 4. Test limit=5
    limited = get_fewshot_suggestions(limit=5)
    print(f"[OK] Total items returned with limit=5: {len(limited)}")
    assert len(limited) == 5

    # 5. Verify no SQL is present in any item
    assert not any("sql" in s for s in all_items), "Error: SQL statement found in suggestions!"
    print("[OK] Confirmed no SQL stored or returned in items")

    # 6. Verify 100% Milvus 768-dim embeddings
    emb_count = sum(1 for s in all_items if len(s.get("embedding", [])) == 768)
    print(f"[OK] 768-dim Milvus embeddings count: {emb_count} / {len(all_items)} (100%)")
    assert emb_count == 200, f"Expected 200 embeddings, got {emb_count}"

    first = all_items[0]
    print(f"[OK] Sample item ID: {first['id']}")
    print(f"[OK] Sample item question: {first['question']}")
    print(f"[OK] Item keys: {list(first.keys())}")

    # 7. Test custom file ingestion on demand (e.g. fewshots_combined.jsonl)
    print("\n[7] Testing dynamic loading of custom file: fewshots_combined.jsonl...")
    custom_items = load_or_build_suggestions(file_path="fewshots_combined.jsonl", force_refresh=True)
    print(f"[OK] Loaded {len(custom_items)} items from fewshots_combined.jsonl")
    assert len(custom_items) == 213, f"Expected 213, got {len(custom_items)}"

    # Restore default new_fewshots.jsonl cache
    print("\n[8] Restoring new_fewshots.jsonl as active cache...")
    load_or_build_suggestions(file_path="new_fewshots.jsonl", force_refresh=True)

    print("=" * 70)
    print("ap_citizen360_v1.5.4 ALL LOCAL SUGGESTIONS TESTS PASSED 100%!")
    print("=" * 70)


if __name__ == "__main__":
    run_local_tests()

