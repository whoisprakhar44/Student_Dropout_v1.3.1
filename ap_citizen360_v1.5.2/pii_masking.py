"""
pii_masking.py
──────────────
Lightweight PII column detection and row-level masking for AP Citizen 360.

Column names are matched against PII_COLUMN_MARKERS using substring containment
on the lowercased column name — no regex, no value inspection.

Usage
─────
    from pii_masking import mask_pii_rows, is_pii_column

    masked_rows, pii_cols = mask_pii_rows(rows, columns)
    # masked_rows  — same structure as rows, with PII values replaced by MASK_VALUE
    # pii_cols     — sorted list of column names that were masked (for audit/logging)

Masking is a presentation-layer concern only. The MCP servers always return the
full raw payload; masking is applied at the agent summarisation boundary and at
the API response boundary so that neither the LLM nor the end-user ever sees
raw PII for users who lack the ``pii_access`` RBAC privilege.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

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
# Public API
# ---------------------------------------------------------------------------

def is_pii_column(col_name: str) -> bool:
    """Return True if *col_name* contains any PII marker substring (case-insensitive)."""
    lower = col_name.lower()
    return any(marker in lower for marker in PII_COLUMN_MARKERS)


def get_pii_columns(columns: List[str]) -> List[str]:
    """Return the subset of *columns* that are considered PII."""
    return [c for c in columns if is_pii_column(c)]


def mask_pii_rows(
    rows: List[Dict[str, Any]],
    columns: List[str],
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

    Returns
    -------
    masked_rows:
        New list of dicts where every PII column value is ``MASK_VALUE``.
        Non-PII columns are unchanged. The original *rows* are **not** mutated.
    pii_column_names:
        Sorted list of column names that were masked. Empty list when no PII
        columns were detected (caller can skip logging in that case).
    """
    pii_cols: set[str] = set(get_pii_columns(columns))
    if not pii_cols:
        return rows, []

    masked: List[Dict[str, Any]] = []
    for row in rows:
        new_row: Dict[str, Any] = {}
        for k, v in row.items():
            new_row[k] = MASK_VALUE if k in pii_cols else v
        masked.append(new_row)

    return masked, sorted(pii_cols)
