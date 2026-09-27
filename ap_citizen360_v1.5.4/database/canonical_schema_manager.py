"""
Canonical Schema Reference & Metadata Manager (ap_citizen360_v1.5.4)
===================================================================
Loads and sanitizes the canonical Iceberg data model schema from
citizen360_canonical_schema.json, stripping all internal/confidential metadata
(such as source SQL paths, DDL references, internal IDs, steward notes), and
provides cached version metadata and schema payloads for the frontend About view.
"""

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("canonical_schema_manager")

CURRENT_DIR = Path(__file__).resolve().parent
APP_ROOT = CURRENT_DIR.parent

_SCHEMA_CACHE: dict[str, Any] | None = None
_META_CACHE: dict[str, Any] | None = None


def _find_schema_file() -> Path | None:
    """Finds canonical schema JSON file across known candidate locations."""
    candidates = [
        APP_ROOT / "citizen360_canonical_schema (1).json",
        APP_ROOT / "citizen360_canonical_schema.json",
        APP_ROOT.parent / "citizen360_canonical_schema (1).json",
        APP_ROOT.parent / "citizen360_canonical_schema.json",
        CURRENT_DIR / "citizen360_canonical_schema (1).json",
        CURRENT_DIR / "citizen360_canonical_schema.json",
    ]
    for p in candidates:
        if p.is_file():
            return p.resolve()
    return None


def load_and_sanitize_schema() -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Parses the canonical schema JSON, strips internal/sensitive information,
    and returns (clean_schema_dict, metadata_dict).
    """
    global _SCHEMA_CACHE, _META_CACHE

    if _SCHEMA_CACHE is not None and _META_CACHE is not None:
        return _SCHEMA_CACHE, _META_CACHE

    schema_file = _find_schema_file()
    if not schema_file:
        logger.warning("Canonical schema file not found; providing fallback structure.")
        clean_fallback = {
            "title": "AP Citizen 360° Data Model",
            "description": "Canonical data model reference for AP Citizen 360° platform.",
            "version": "3.0.0",
            "effectiveDate": "2026-08-13",
            "databaseName": "ap_citizen360",
            "tableCount": 0,
            "totalFieldCount": 0,
            "groups": [],
            "tables": {},
        }
        meta_fallback = {
            "status": "success",
            "version": "3.0.0",
            "database_name": "ap_citizen360",
            "table_count": 0,
            "total_field_count": 0,
            "groups_count": 0,
            "effective_date": "2026-08-13",
            "updated_at": "2026-08-13",
        }
        _SCHEMA_CACHE = clean_fallback
        _META_CACHE = meta_fallback
        return _SCHEMA_CACHE, _META_CACHE

    try:
        with open(schema_file, "r", encoding="utf-8") as f:
            raw = json.load(f)

        # Build clean schema dict without confidential info (no sourceDdl, $schema, $id, etc.)
        groups = raw.get("groups") or []
        tables_raw = raw.get("tables") or {}

        clean_tables = {}
        for tbl_name, tbl_data in tables_raw.items():
            fields_raw = tbl_data.get("fields") or {}
            clean_fields = {}
            for f_name, f_info in fields_raw.items():
                clean_fields[f_name] = {
                    "type": f_info.get("type", "STRING"),
                    "description": f_info.get("description", ""),
                }

            clean_tables[tbl_name] = {
                "group": tbl_data.get("group", "OTHER"),
                "tableType": tbl_data.get("tableType", "dimension"),
                "primaryKey": tbl_data.get("primaryKey"),
                "partitionedBy": tbl_data.get("partitionedBy"),
                "description": tbl_data.get("description", ""),
                "fieldCount": tbl_data.get("fieldCount", len(clean_fields)),
                "fields": clean_fields,
            }

        version = raw.get("version", "3.0.0")
        effective_date = raw.get("effectiveDate", "2026-08-13")
        database_name = raw.get("databaseName", "ap_citizen360")
        table_count = raw.get("tableCount", len(clean_tables))
        total_field_count = raw.get("totalFieldCount", sum(t["fieldCount"] for t in clean_tables.values()))

        clean_schema = {
            "title": "AP Citizen 360° Canonical Data Model",
            "description": "Comprehensive canonical data model reference for the AP Citizen 360° platform. Every field carries a plain-language description of what it holds and how it is used.",
            "version": version,
            "effectiveDate": effective_date,
            "databaseName": database_name,
            "tableCount": table_count,
            "totalFieldCount": total_field_count,
            "groups": groups,
            "tables": clean_tables,
        }

        meta = {
            "status": "success",
            "version": version,
            "database_name": database_name,
            "table_count": table_count,
            "total_field_count": total_field_count,
            "groups_count": len(groups),
            "effective_date": effective_date,
            "updated_at": effective_date,
        }

        _SCHEMA_CACHE = clean_schema
        _META_CACHE = meta
        logger.info(f"Loaded canonical schema: {table_count} tables, {total_field_count} fields, version {version}")
        return _SCHEMA_CACHE, _META_CACHE

    except Exception as e:
        logger.error(f"Error reading canonical schema from {schema_file}: {e}")
        raise


def get_schema_metadata() -> dict[str, Any]:
    """Returns database version and schema metadata."""
    _, meta = load_and_sanitize_schema()
    return meta


def get_canonical_schema() -> dict[str, Any]:
    """Returns full sanitized canonical schema."""
    schema, _ = load_and_sanitize_schema()
    return schema
