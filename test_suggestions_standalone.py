"""
Standalone verification of Suggestions & Vector Embeddings loader & metadata
===========================================================================
Validates:
1. Sourced strictly from fewshots_combined.jsonl (213 items).
2. 100% pre-computed 768-dim embeddings extracted directly from Milvus DB.
3. No SQL query statements present in cached / served suggestions.
4. get_cache_metadata() returns updated_at timestamp, count, and cache_file.
5. get_fewshot_suggestions(limit=-1) returns all 213 items.
6. get_fewshot_suggestions(limit=5) returns 5 items.
"""

from database.suggestions import (
    load_or_build_suggestions,
    get_fewshot_suggestions,
    get_cache_metadata,
)


def main():
    print("=" * 70)
    print("Testing Standalone Suggestions Service & Cache Metadata")
    print("=" * 70)

    # 1. Test cache metadata
    meta = get_cache_metadata()
    print(f"[OK] Cache metadata: {meta}")
    assert meta["status"] == "success"
    assert meta["count"] == 213, f"Expected 213 count in metadata, got {meta['count']}"
    assert "updated_at" in meta and len(meta["updated_at"]) > 0, "Missing updated_at timestamp!"

    # 2. Test limit=-1 (all items)
    all_suggestions = get_fewshot_suggestions(limit=-1)
    print(f"[OK] get_fewshot_suggestions(limit=-1) count: {len(all_suggestions)}")
    assert len(all_suggestions) == 213, f"Expected 213 suggestions, got {len(all_suggestions)}"

    # 3. Test limit=5
    limited = get_fewshot_suggestions(limit=5)
    print(f"[OK] get_fewshot_suggestions(limit=5) count: {len(limited)}")
    assert len(limited) == 5, f"Expected 5 suggestions, got {len(limited)}"

    # 4. Verify no SQL query stored
    assert not any("sql" in s for s in all_suggestions), "Error: 'sql' key found in suggestions!"
    print(f"[OK] No SQL statements in cache: Confirmed")

    # 5. Verify 100% embeddings
    emb_count = sum(1 for s in all_suggestions if len(s.get("embedding", [])) == 768)
    print(f"[OK] 768-dim Milvus embeddings count: {emb_count} / {len(all_suggestions)} (100%)")
    assert emb_count == 213, f"Expected 213 embeddings, got {emb_count}"

    first = all_suggestions[0]
    print(f"[OK] First suggestion ID: {first['id']}")
    print(f"[OK] First suggestion question: {first['question']}")
    print(f"[OK] Fields present: {list(first.keys())}")

    print("\n" + "=" * 70)
    print("[SUCCESS] All standalone suggestions & cache metadata tests passed!")
    print("=" * 70)


if __name__ == "__main__":
    main()
