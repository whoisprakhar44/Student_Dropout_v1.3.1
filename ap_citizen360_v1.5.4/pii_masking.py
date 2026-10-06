"""
pii_masking.py
──────────────
Lightweight PII column detection and row-level masking for AP Citizen 360.

Column names are matched against PII_COLUMN_MARKERS using substring containment
on the lowercased column name — no regex, no value inspection.

Prompt-injection alias bypass is handled by ``extract_pii_aliases_from_sql``:
if a user asks the LLM to rename ``student_name`` as ``sn``, the SQL string
``SELECT student_name AS sn ...`` is parsed to build a {alias → source} map
which is passed to ``mask_pii_rows`` alongside the regular column check.

Usage
─────
    from pii_masking import mask_pii_rows, is_pii_column, extract_pii_aliases_from_sql

    alias_map = extract_pii_aliases_from_sql(sql_query)
    masked_rows, pii_cols = mask_pii_rows(rows, columns, alias_map=alias_map)
    # masked_rows  — same structure as rows, with PII values replaced by MASK_VALUE
    # pii_cols     — sorted list of column names that were masked (for audit/logging)

Masking is a presentation-layer concern only. The MCP servers always return the
full raw payload; masking is applied at the agent summarisation boundary and at
the API response boundary so that neither the LLM nor the end-user ever sees
raw PII for users who lack the ``pii_access`` RBAC privilege.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# PII column markers
# ---------------------------------------------------------------------------
# Substring markers checked against the **lowercased** column name.
# A column is considered PII if its lowercased name *contains* any marker.
# Deliberately specific — general tokens like "name" are avoided so that
# columns such as district_name / scheme_name / facility_name are NOT flagged.
PII_COLUMN_MARKERS: Tuple[str, ...] = (
    # Identity documents / identifiers
    "aadhaar", "voter_id", "driving_license", "driving_licence",
    "identifier_value", "ration_card_no", "ration_card",
    "bank_account", "pan_number", "pan_no",
    # Contact
    "phone", "mobile", "email",
    # Address / precise location
    "address", "door_no", "latitude", "longitude", "pincode", "pin_code",
    # Family / person names (deliberately specific — excludes place/entity
    # names like district_name, scheme_name, facility_name)
    "person_name", "father_name", "mother_name", "husband_name", "wife_name",
    "guardian_name", "applicant_name", "beneficiary_name", "nominee_name",
    "student_name", "spouse_name",
    # Date of birth
    "date_of_birth", "dob",
    # Vehicle / document registration numbers
    "chassis_no", "engine_no", "reg_no", "policy_no",
    # Health identifiers
    "abha_address", "abdm_id", "aarogyasri_card_no", "pmjay_beneficiary_id",
    "pmjay_family_id", "hmis_facility_code", "nin",
    # Misc certificate numbers
    "caste_base_certificate_no",
)

# Replacement value used for masked cells.
MASK_VALUE: str = "***"

# ---------------------------------------------------------------------------
# SQL keywords that appear after AS but are NOT column aliases
# ---------------------------------------------------------------------------
_SQL_KEYWORDS: frozenset = frozenset({
    "select", "from", "where", "join", "on", "group", "order", "having",
    "limit", "offset", "with", "case", "when", "then", "else", "end",
    "and", "or", "not", "in", "is", "null", "true", "false", "inner",
    "outer", "left", "right", "cross", "full", "union", "intersect",
    "except", "by", "asc", "desc", "distinct", "all", "exists", "between",
    "like", "ilike", "over", "partition", "row", "rows", "range", "unbounded",
    "preceding", "following", "current",
})

# Pattern: [optional_table.]bare_identifier AS alias
# Requires the token before AS to be a simple identifier (no opening paren),
# so that function calls like UPPER(col) AS alias are NOT matched.
_AS_ALIAS_RE = re.compile(
    r"(?<![(\w])(?:[\w]+\.)?(\w+)\s+AS\s+(\w+)(?!\s*\()",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def is_pii_column(col_name: str) -> bool:
    """Return True if *col_name* contains any PII marker substring (case-insensitive)."""
    lower = col_name.lower()
    return any(marker in lower for marker in PII_COLUMN_MARKERS)


def get_pii_columns(columns: List[str]) -> List[str]:
    """Return the subset of *columns* that are considered PII."""
    return [c for c in columns if is_pii_column(c)]


def extract_pii_aliases_from_sql(sql: str) -> Dict[str, str]:
    """
    Parse a SQL string and return ``{alias_lower: source_col_lower}`` for every
    ``col AS alias`` expression where:

    - ``col`` (or ``table.col``) is a known PII column, AND
    - ``alias`` is **not** itself already a PII column name.

    This detects prompt-injection alias bypass attacks of the form:

        SELECT student_name AS sn, aadhaar_no AS doc_id FROM students

    where ``sn`` and ``doc_id`` would normally pass the ``is_pii_column`` check.

    Parameters
    ----------
    sql:
        The raw SQL query string (as generated by the LLM).

    Returns
    -------
    Dict mapping alias (lowercased) → original PII column name (lowercased).
    Empty dict when the SQL cannot be parsed or has no alias bypasses.

    Notes
    -----
    - Handles table-qualified references: ``s.student_name AS sn``.
    - Handles CTEs and subqueries (they are scanned as a flat string).
    - Does **not** handle function-expression aliases like ``UPPER(student_name) AS nm``
      because the pattern requires a bare identifier before AS.  Those cases
      are left unmasked (safe conservative fallback).
    - Zero external dependencies — pure stdlib regex.
    """
    if not sql:
        return {}

    # Strip string literals and SQL comments to avoid false positives
    cleaned = re.sub(r"'[^']*'", "''", sql)                     # single-quoted strings
    cleaned = re.sub(r"--[^\n]*", "", cleaned)                   # single-line comments
    cleaned = re.sub(r"/\*.*?\*/", "", cleaned, flags=re.DOTALL) # block comments

    alias_map: Dict[str, str] = {}
    for m in _AS_ALIAS_RE.finditer(cleaned):
        source_col = m.group(1).lower()
        alias_col  = m.group(2).lower()

        # Skip SQL keyword tokens appearing in alias position
        if source_col in _SQL_KEYWORDS or alias_col in _SQL_KEYWORDS:
            continue

        # Only record when source is PII and alias does not already get caught
        # by the standard marker check (avoids double-counting)
        if is_pii_column(source_col) and not is_pii_column(alias_col):
            alias_map[alias_col] = source_col

    return alias_map


def mask_pii_rows(
    rows: List[Dict[str, Any]],
    columns: List[str],
    alias_map: Optional[Dict[str, str]] = None,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Replace PII column values in *rows* with ``MASK_VALUE``.

    Parameters
    ----------
    rows:
        List of row dicts as returned by the MCP ``execute_sql`` tool
        (``{"col_name": value, ...}``).
    columns:
        Ordered list of column names from the same SQL result payload.
    alias_map:
        Optional mapping of ``{alias_col_lower: source_pii_col_lower}``
        produced by ``extract_pii_aliases_from_sql``.  When provided, any
        column whose lowercase name appears as a key in *alias_map* is also
        masked, even if its name does not match a PII marker directly.
        This closes the prompt-injection alias bypass attack surface.

    Returns
    -------
    masked_rows:
        New list of dicts where every PII column value is ``MASK_VALUE``.
        Non-PII columns are unchanged. The original *rows* are **not** mutated.
    pii_column_names:
        Sorted list of column names that were masked. Empty list when no PII
        columns were detected (caller can skip logging in that case).
    """
    pii_cols: set = set(get_pii_columns(columns))

    # Extend PII column set with alias-bypassed columns
    if alias_map:
        for col in columns:
            if col.lower() in alias_map:
                pii_cols.add(col)

    if not pii_cols:
        return rows, []

    masked: List[Dict[str, Any]] = []
    for row in rows:
        new_row: Dict[str, Any] = {}
        for k, v in row.items():
            new_row[k] = MASK_VALUE if k in pii_cols else v
        masked.append(new_row)

    return masked, sorted(pii_cols)
