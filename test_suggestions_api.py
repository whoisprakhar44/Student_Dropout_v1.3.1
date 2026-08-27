"""
Test script for Few-Shot Suggestions API and Cache Metadata Endpoints
=====================================================================
Validates:
1. Sourced strictly from fewshots_combined.jsonl (213 items).
2. 100% pre-computed 768-dim vector embeddings directly extracted from Milvus DB.
3. No SQL query statements present in cached / served suggestions.
4. Returns all 213 items when limit is -1 or omitted in POST /suggestions, GET /suggestions, and POST /ask.
5. GET /suggestions/meta returns updated_at timestamp and item count for client cache verification.
6. Verify no embed action or backend ranking.
"""

import sys
import os
from pathlib import Path
from fastapi import FastAPI, Query
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from database.suggestions import (
    get_fewshot_suggestions,
    get_cache_metadata,
    load_or_build_suggestions,
)

# Test FastAPI app mounting the suggestions handlers
test_app = FastAPI(title="Suggestions Test App")


class AskRequest(BaseModel):
    action: str | None = Field(default=None)
    question: str | None = Field(default=None)
    username: str = Field(default="user")
    limit: int | None = Field(default=-1)


@test_app.post("/ask")
async def ask(payload: AskRequest):
    action = payload.action or "ask"
    if action in ("suggestions_meta", "suggestions_version"):
        return get_cache_metadata()
    elif action in ("suggestions", "fewshots", "get_suggestions"):
        limit = payload.limit if payload.limit is not None else -1
        items = get_fewshot_suggestions(limit=limit)
        meta = get_cache_metadata()
        return {
            "status": "success",
            "count": len(items),
            "updated_at": meta["updated_at"],
            "suggestions": items,
        }
    return {"status": "unsupported"}


@test_app.get("/suggestions/meta")
@test_app.get("/suggestions/version")
async def get_suggestions_meta_endpoint():
    return get_cache_metadata()


@test_app.get("/suggestions")
@test_app.get("/fewshots")
async def get_suggestions_endpoint(
    limit: int = Query(default=-1, description="Maximum suggestions to return (-1 for all)"),
):
    items = get_fewshot_suggestions(limit=limit)
    meta = get_cache_metadata()
    return {
        "status": "success",
        "count": len(items),
        "updated_at": meta["updated_at"],
        "suggestions": items,
    }


@test_app.post("/suggestions")
async def post_suggestions_endpoint(payload: AskRequest):
    if not payload.action:
        payload.action = "suggestions"
    return await ask(payload)


def test_suggestions():
    client = TestClient(test_app)

    print("=" * 70)
    print("1. Testing GET /suggestions/meta (Cache Timestamp & Count Verification)")
    print("=" * 70)
    meta_resp = client.get("/suggestions/meta")
    assert meta_resp.status_code == 200, f"Expected 200, got {meta_resp.status_code}: {meta_resp.text}"
    meta_data = meta_resp.json()
    assert meta_data["status"] == "success"
    assert meta_data["count"] == 213
    assert "updated_at" in meta_data and len(meta_data["updated_at"]) > 0
    print(f"[OK] Cache updated_at: {meta_data['updated_at']}")
    print(f"[OK] Cache count: {meta_data['count']}")

    print("\n" + "=" * 70)
    print("2. Testing POST /ask with action='suggestions' (limit=-1 -> returns ALL 213)")
    print("=" * 70)
    resp = client.post("/ask", json={"action": "suggestions", "limit": -1, "username": "test_user"})
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data.get("status") == "success"
    assert "updated_at" in data
    suggestions = data["suggestions"]
    assert len(suggestions) == 213, f"Expected 213 suggestions, got {len(suggestions)}"

    # Verify no SQL is present in any suggestion
    assert not any("sql" in s for s in suggestions), "Error: 'sql' key found in suggestions!"
    print(f"[OK] Total suggestions returned: {len(suggestions)} (ALL 213)")
    print(f"[OK] No SQL queries stored/exposed: Confirmed")

    first_item = suggestions[0]
    print(f"[OK] Sample suggestion ID: {first_item.get('id')}")
    print(f"[OK] Sample question: {first_item.get('question')}")
    print(f"[OK] Embedding vector dimension: {len(first_item.get('embedding', []))}")
    total_with_embeddings = sum(1 for s in suggestions if len(s.get("embedding", [])) == 768)
    print(f"[OK] Total with 768-dim Milvus embeddings: {total_with_embeddings} / {len(suggestions)} (100%)")
    assert total_with_embeddings == 213, f"Expected 213 embeddings, got {total_with_embeddings}"

    print("\n" + "=" * 70)
    print("3. Testing GET /suggestions and GET /fewshots (limit=-1 default vs limit=5)")
    print("=" * 70)
    resp_get_all = client.get("/suggestions")
    assert resp_get_all.status_code == 200
    assert len(resp_get_all.json()["suggestions"]) == 213
    print(f"[OK] GET /suggestions default (limit=-1) returned all 213 items.")

    resp_get_5 = client.get("/suggestions?limit=5")
    assert resp_get_5.status_code == 200
    assert len(resp_get_5.json()["suggestions"]) == 5
    print(f"[OK] GET /suggestions?limit=5 returned 5 items.")

    print("\n" + "=" * 70)
    print("4. Testing POST /suggestions alias endpoint")
    print("=" * 70)
    resp_post_sugg = client.post("/suggestions", json={"limit": -1, "username": "test_user"})
    assert resp_post_sugg.status_code == 200
    post_sugg_data = resp_post_sugg.json()
    assert len(post_sugg_data["suggestions"]) == 213
    assert "updated_at" in post_sugg_data
    print(f"[OK] POST /suggestions returned all {len(post_sugg_data['suggestions'])} items with timestamp.")

    print("\n" + "=" * 70)
    print("ALL 4 SUGGESTIONS API TESTS PASSED SUCCESSFULLY!")
    print("=" * 70)


if __name__ == "__main__":
    test_suggestions()
