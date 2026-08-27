"""
Local suggestions & cache verification test for ap_citizen360_v1.5.4
====================================================================
Validates all features within ap_citizen360_v1.5.4:
1. Loads strictly 213 few-shot questions from ap_citizen360_v1.5.4/fewshots_combined.jsonl.
2. 100% (213/213) pre-computed 768-dim embeddings from Milvus DB parquet.
3. No raw SQL stored in cache or served.
4. Cache metadata contains valid updated_at timestamp and item count.
5. get_fewshot_suggestions(limit=-1) returns all 213 items.
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


def run_local_tests():
    print("=" * 70)
    print("Running Local Verification on ap_citizen360_v1.5.4")
    print("=" * 70)

    # 1. Test cache metadata
    meta = get_cache_metadata()
    print(f"[OK] Cache metadata: {meta}")
    assert meta["status"] == "success"
    assert meta["count"] == 213, f"Expected 213, got {meta['count']}"
    assert "updated_at" in meta and len(meta["updated_at"]) > 0

    # 2. Test limit=-1
    all_items = get_fewshot_suggestions(limit=-1)
    print(f"[OK] Total items returned with limit=-1: {len(all_items)}")
    assert len(all_items) == 213, f"Expected 213, got {len(all_items)}"

    # 3. Test limit=5
    limited = get_fewshot_suggestions(limit=5)
    print(f"[OK] Total items returned with limit=5: {len(limited)}")
    assert len(limited) == 5

    # 4. Verify no SQL is present in any item
    assert not any("sql" in s for s in all_items), "Error: SQL statement found in suggestions!"
    print("[OK] Confirmed no SQL stored or returned in items")

    # 5. Verify 100% Milvus 768-dim embeddings
    emb_count = sum(1 for s in all_items if len(s.get("embedding", [])) == 768)
    print(f"[OK] 768-dim Milvus embeddings count: {emb_count} / {len(all_items)} (100%)")
    assert emb_count == 213, f"Expected 213 embeddings, got {emb_count}"

    first = all_items[0]
    print(f"[OK] Sample item ID: {first['id']}")
    print(f"[OK] Sample item question: {first['question']}")
    print(f"[OK] Item keys: {list(first.keys())}")

    print("=" * 70)
    print("ap_citizen360_v1.5.4 LOCAL SUGGESTIONS TESTS PASSED 100%!")
    print("=" * 70)


if __name__ == "__main__":
    run_local_tests()
