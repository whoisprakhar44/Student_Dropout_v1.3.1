import os
import yaml
import logging
from typing import List, Dict, Any

logger = logging.getLogger("guardrails.egress")

# Load PII policy
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "pii_columns.yaml")

_pii_policy = {}
if os.path.exists(CONFIG_PATH):
    with open(CONFIG_PATH, "r") as f:
        _policy = yaml.safe_load(f)
        _pii_policy = _policy.get("columns", {})
else:
    logger.warning(f"Egress guardrails config not found at {CONFIG_PATH}. Skipping egress masking.")


def get_user_role(username: str) -> str:
    """
    Mock function to get the user's role.
    In a real system, you would query a user DB or pass it in the JWT token.
    For demonstration, we assign 'admin' to 'prakhar', and 'teacher' to others.
    """
    if not username:
        return "public"
    
    username_lower = username.lower()
    if username_lower == "prakhar" or username_lower == "admin":
        return "admin"
    if username_lower == "principal":
        return "school_principal"
    
    return "public"


def _mask_value(value: Any, pattern: str) -> str:
    """Mask a string value according to the pattern."""
    if value is None:
        return None
    val_str = str(value)
    if not val_str:
        return val_str
    
    if pattern == "REDACTED":
        return "REDACTED"
    
    if "{last4}" in pattern:
        last4 = val_str[-4:] if len(val_str) >= 4 else val_str
        return pattern.replace("{last4}", last4)
    
    return pattern


def mask_egress_rows(rows: List[Dict[str, Any]], username: str) -> List[Dict[str, Any]]:
    """
    Masks sensitive columns in the result rows based on user role and policy.
    Modifies the rows in-place or creates a new masked list.
    """
    if not rows or not _pii_policy:
        return rows

    role = get_user_role(username)
    
    # Fast path: if the role is admin and admin is allowed for all, we can optimize.
    # But for safety, we'll check column by column.
    
    masked_rows = []
    
    for row in rows:
        masked_row = {}
        for col_name, value in row.items():
            # Check if column is governed by policy
            policy = _pii_policy.get(col_name)
            
            if policy:
                allowed_roles = policy.get("allowed_roles", [])
                if role not in allowed_roles:
                    # Apply masking
                    pattern = policy.get("mask_pattern", "REDACTED")
                    masked_row[col_name] = _mask_value(value, pattern)
                else:
                    # User is allowed to see the raw value
                    masked_row[col_name] = value
            else:
                # Fallback heuristics for unclassified columns
                # E.g., if column name contains 'aadhaar' but isn't strictly 'aadhaar_number'
                if "aadhaar" in col_name.lower():
                    if role not in ["admin", "state_level_officer"]:
                        masked_row[col_name] = _mask_value(value, "XXXX-XXXX-{last4}")
                    else:
                        masked_row[col_name] = value
                else:
                    # Safe column
                    masked_row[col_name] = value
                    
        masked_rows.append(masked_row)
        
    return masked_rows
