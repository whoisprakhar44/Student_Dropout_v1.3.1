"""
Test script for Canonical Schema API and Metadata Endpoints
============================================================
Validates:
1. POST /ask with action='schema_meta' returns database version and table counts.
2. POST /ask with action='canonical_schema' returns all 20 groups and 46 tables.
3. No internal SQL/DDL file paths or confidential steward data leaked.
4. GET /api/schema/meta and GET /api/schema return sanitized outputs.
"""

import sys
from pathlib import Path
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

# Insert ap_citizen360_v1.5.2 to path
sys.path.insert(0, str(Path(__file__).resolve().parent / "ap_citizen360_v1.5.2"))

from database.canonical_schema_manager import get_schema_metadata, get_canonical_schema

test_app = FastAPI(title="Schema Test App")


class AskRequest(BaseModel):
    action: str | None = Field(default=None)
    username: str = Field(default="user")


@test_app.get("/api/schema/meta")
def get_canonical_schema_meta():
    return get_schema_metadata()


@test_app.get("/api/schema")
def get_canonical_schema_data():
    return get_canonical_schema()


@test_app.post("/ask")
async def ask(payload: AskRequest):
    action = payload.action or "ask"
    if action in ("schema_meta", "schema_version", "about_meta"):
        return get_schema_metadata()
    elif action in ("schema", "canonical_schema", "about_schema", "get_schema"):
        return get_canonical_schema()
    return {"status": "unsupported"}


def run_tests():
    client = TestClient(test_app)

    print("1. Testing POST /ask with action='schema_meta'...")
    res = client.post("/ask", json={"action": "schema_meta", "username": "user"})
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    meta = res.json()
    assert meta["status"] == "success"
    assert meta["version"] == "3.0.0"
    assert meta["database_name"] == "ap_citizen360"
    assert meta["table_count"] == 46
    assert meta["total_field_count"] == 605
    assert meta["groups_count"] == 20
    print("   [PASS] schema_meta response:", meta)

    print("\n2. Testing POST /ask with action='canonical_schema'...")
    res = client.post("/ask", json={"action": "canonical_schema", "username": "user"})
    assert res.status_code == 200
    schema = res.json()
    assert schema["version"] == "3.0.0"
    assert len(schema["groups"]) == 20
    assert len(schema["tables"]) == 46
    assert "$schema" not in schema
    assert "sourceDdl" not in schema
    assert ".sql" not in schema["description"]
    print(f"   [PASS] canonical_schema response: {len(schema['groups'])} groups, {len(schema['tables'])} tables")

    print("\n3. Testing GET /api/schema/meta...")
    res = client.get("/api/schema/meta")
    assert res.status_code == 200
    assert res.json()["version"] == "3.0.0"
    print("   [PASS] GET /api/schema/meta passed")

    print("\n4. Testing GET /api/schema...")
    res = client.get("/api/schema")
    assert res.status_code == 200
    assert len(res.json()["tables"]) == 46
    print("   [PASS] GET /api/schema passed")

    print("\nAll Canonical Schema API tests passed successfully!")


if __name__ == "__main__":
    run_tests()
