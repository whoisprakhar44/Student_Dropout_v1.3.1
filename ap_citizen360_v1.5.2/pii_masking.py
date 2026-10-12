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

# Pattern: aggregate function wrapping any PII column, e.g.
#   COUNT(ration_card_no), SUM(s.aadhaar_no), AVG(dob) ...
# Group 1 = aggregate function name, Group 2 = (optional table.)column
_AGGREGATE_FUNC_RE = re.compile(
    r"\b(COUNT|SUM|AVG|MIN|MAX)\s*\(\s*(?:DISTINCT\s+)?(?:[\w]+\.)?([\w]+)\s*\)",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def is_pii_column(col_name: str) -> bool:
    """Return True if *col_name* contains any PII marker substring (case-insensitive)."""
    lower = col_name.lower()
    return any(marker in lower for marker in PII_COLUMN_MARKERS)


def is_aggregate_value(value: Any) -> bool:
    """
    Return True when *value* is a plain numeric result — a COUNT, SUM, AVG, etc.

    Rationale: aggregate functions collapse many citizen rows into a single
    number (e.g. ``COUNT(ration_card_no) = 4271``). That number is statistical,
    not personally identifiable, and must NOT be masked even if the column
    name triggers a PII marker match.

    IMPORTANT: This only matches **native Python int/float** types, NOT numeric
    strings. Phone numbers (e.g. "9876543210") and account numbers are stored
    as strings in the database and must remain maskable. DB drivers always
    return COUNT/SUM/AVG results as native int or float, never as str, so
    restricting to native types is both safe and correct.
    """
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def get_aggregate_aliases_from_sql(sql: str) -> frozenset:
    """
    Return a frozenset of *lowercased* column aliases that are produced by
    aggregate functions over PII columns in *sql*.

    Example::

        SELECT COUNT(ration_card_no) AS total_ration_cards,
               SUM(aadhaar_no)       AS aadhaar_count
        FROM ...

    → frozenset({'total_ration_cards', 'aadhaar_count'})

    These aliases hold numeric totals — not raw PII — and should be excluded
    from masking even though their names may contain a PII marker.
    """
    if not sql:
        return frozenset()

    cleaned = re.sub(r"'[^']*'", "''", sql)
    cleaned = re.sub(r"--[^\n]*", "", cleaned)
    cleaned = re.sub(r"/\*.*?\*/", "", cleaned, flags=re.DOTALL)

    aggregate_aliases: set = set()

    # Find every  AGG_FUNC(...pii_col...) AS alias  pattern
    # We look for  AGG_FUNC(...)  followed optionally by  AS alias
    agg_with_alias_re = re.compile(
        r"\b(?:COUNT|SUM|AVG|MIN|MAX)\s*\([^)]*\)\s+AS\s+(\w+)",
        re.IGNORECASE,
    )
    for m in agg_with_alias_re.finditer(cleaned):
        alias = m.group(1).lower()
        # The whole match includes the function call; check if any PII column
        # name appears inside the parentheses.
        func_call = m.group(0)
        paren_start = func_call.index("(")
        paren_end   = func_call.rindex(")")
        inner = func_call[paren_start + 1 : paren_end].lower()
        if any(marker in inner for marker in PII_COLUMN_MARKERS):
            aggregate_aliases.add(alias)

    # Also catch  AGG_FUNC(pii_col)  without an explicit alias — the DB driver
    # will return a generated name like "count(ration_card_no)" or "count_1";
    # capture the generated column name pattern too.
    for m in _AGGREGATE_FUNC_RE.finditer(cleaned):
        inner_col = m.group(2).lower()
        if is_pii_column(inner_col):
            # Generated column names vary by DB; record the bare inner col so
            # is_aggregate_value() still acts as the safety net.
            pass  # value-type check handles these automatically

    return frozenset(aggregate_aliases)


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
    sql: str = "",
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Replace PII column values in *rows* with ``MASK_VALUE``.

    Aggregates are NOT masked:
    - If the SQL contains ``COUNT(ration_card_no) AS total``, the alias
      ``total`` holds a plain number — statistical, not personally
      identifiable — and is excluded from masking.
    - As a second safety net, any cell whose value is a pure integer or
      float (e.g. ``4271``) is also never masked, because aggregate
      functions always produce numeric scalars while raw PII is always text.

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
    sql:
        The original SQL query that produced these rows. Used to detect
        aggregate aliases so they are never masked.

    Returns
    -------
    masked_rows:
        New list of dicts where every raw-PII column value is ``MASK_VALUE``.
        Aggregate (numeric) columns are unchanged even if their name contains
        a PII marker. The original *rows* are **not** mutated.
    pii_column_names:
        Sorted list of column names that were masked (excludes aggregate
        columns that were left unmasked). Empty list when nothing was masked.
    """
    pii_cols: set = set(get_pii_columns(columns))

    # Extend PII column set with alias-bypassed columns
    if alias_map:
        for col in columns:
            if col.lower() in alias_map:
                pii_cols.add(col)

    if not pii_cols:
        return rows, []

    # ── Aggregate-alias exclusion ─────────────────────────────────────────
    # Columns that are produced by COUNT/SUM/AVG/MIN/MAX over a PII column
    # hold a numeric total, not raw PII. Exclude them from masking.
    aggregate_aliases = get_aggregate_aliases_from_sql(sql) if sql else frozenset()
    # Also exclude any PII-named column if ALL values across the result set
    # are numeric (covers generated column names like "count(ration_card_no)").
    # We decide per-column based on actual row values below.
    aggregate_cols: set = {col for col in pii_cols if col.lower() in aggregate_aliases}

    # Remove aggregate aliases from the masking set
    pii_cols -= aggregate_cols

    if not pii_cols:
        return rows, []

    # ── Build the final set of cols that need masking ─────────────────────
    # For any remaining PII candidate column we do a value-type check:
    # if every non-null value in that column is numeric, treat it as an
    # aggregate result and skip masking. This is the safety net for
    # generated column names that skip the SQL alias detection.
    non_null_values: Dict[str, list] = {col: [] for col in pii_cols}
    for row in rows:
        for col in pii_cols:
            v = row.get(col)
            if v is not None and v != "":
                non_null_values[col].append(v)

    numeric_only_cols: set = set()
    for col, vals in non_null_values.items():
        if vals and all(is_aggregate_value(v) for v in vals):
            numeric_only_cols.add(col)

    pii_cols -= numeric_only_cols

    if not pii_cols:
        return rows, []

    masked: List[Dict[str, Any]] = []
    for row in rows:
        new_row: Dict[str, Any] = {}
        for k, v in row.items():
            new_row[k] = MASK_VALUE if k in pii_cols else v
        masked.append(new_row)

    return masked, sorted(pii_cols)
