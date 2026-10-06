"""
Unit and integration tests for PII masking and RBAC pii_access governance.
"""

import json
from langchain_core.messages import AIMessage, ToolMessage
from pii_masking import (
    PII_COLUMN_MARKERS,
    MASK_VALUE,
    is_pii_column,
    get_pii_columns,
    mask_pii_rows,
    extract_pii_aliases_from_sql,
)
from my_agent.utils.nodes import (
    _apply_pii_mask_to_payload,
    _summarize_sql_result,
    _result_table_str,
)
from app import _extract_sql_and_result
from database.rbac_manager import RBACManager


def test_is_pii_column():
    # Positive matches
    assert is_pii_column("student_name") is True
    assert is_pii_column("father_name") is True
    assert is_pii_column("mother_name") is True
    assert is_pii_column("aadhaar_no") is True
    assert is_pii_column("AADHAAR") is True
    assert is_pii_column("mobile_number") is True
    assert is_pii_column("phone_no") is True
    assert is_pii_column("email_id") is True
    assert is_pii_column("door_no") is True
    assert is_pii_column("date_of_birth") is True
    assert is_pii_column("dob") is True
    assert is_pii_column("pan_number") is True
    assert is_pii_column("voter_id") is True
    assert is_pii_column("bank_account_no") is True

    # Negative matches (entity/place/aggregate names)
    assert is_pii_column("district_name") is False
    assert is_pii_column("scheme_name") is False
    assert is_pii_column("facility_name") is False
    assert is_pii_column("mandal_name") is False
    assert is_pii_column("school_name") is False
    assert is_pii_column("total_students") is False
    assert is_pii_column("student_count") is False
    assert is_pii_column("dropout_rate") is False
    assert is_pii_column("academic_year") is False
    assert is_pii_column("status") is False


def test_mask_pii_rows():
    rows = [
        {
            "student_name": "Ravi Kumar",
            "district_name": "Nellore",
            "aadhaar_no": "1234-5678-9012",
            "phone": "9876543210",
            "marks": 95,
        },
        {
            "student_name": "Priya Sharma",
            "district_name": "Guntur",
            "aadhaar_no": "9876-5432-1098",
            "phone": "9123456780",
            "marks": 88,
        },
    ]
    columns = ["student_name", "district_name", "aadhaar_no", "phone", "marks"]

    masked, pii_cols = mask_pii_rows(rows, columns)

    # Verify return types and masked column list
    assert sorted(pii_cols) == ["aadhaar_no", "phone", "student_name"]

    # Verify PII fields are masked
    for row in masked:
        assert row["student_name"] == MASK_VALUE
        assert row["aadhaar_no"] == MASK_VALUE
        assert row["phone"] == MASK_VALUE
        # Non-PII fields remain intact
        assert row["district_name"] in ("Nellore", "Guntur")
        assert row["marks"] in (95, 88)

    # Verify original rows were not mutated
    assert rows[0]["student_name"] == "Ravi Kumar"
    assert rows[0]["aadhaar_no"] == "1234-5678-9012"


def test_mask_pii_rows_no_pii():
    rows = [{"district_name": "Kurnool", "student_count": 1500}]
    cols = ["district_name", "student_count"]
    masked, pii_cols = mask_pii_rows(rows, cols)
    assert masked == rows
    assert pii_cols == []


def test_nodes_apply_pii_mask_to_payload():
    payload = {
        "status": "success",
        "columns": ["student_name", "phone", "district_name"],
        "rows": [
            {"student_name": "John Doe", "phone": "9999999999", "district_name": "Krishna"}
        ],
    }
    raw_str = json.dumps(payload)

    # pii_access=True: untouched
    res_true = _apply_pii_mask_to_payload(raw_str, pii_access=True)
    assert res_true == raw_str

    # pii_access=False: masked
    res_false = _apply_pii_mask_to_payload(raw_str, pii_access=False)
    parsed = json.loads(res_false)
    assert parsed["rows"][0]["student_name"] == MASK_VALUE
    assert parsed["rows"][0]["phone"] == MASK_VALUE
    assert parsed["rows"][0]["district_name"] == "Krishna"


def test_nodes_summarize_sql_result_masking():
    payload = {
        "status": "success",
        "columns": ["student_name", "phone", "district_name"],
        "rows": [
            {"student_name": "Secret Person", "phone": "9988776655", "district_name": "Chittoor"}
        ],
    }
    raw_str = json.dumps(payload)

    # When pii_access=False, summary must NOT contain raw name or phone
    summary_masked = _summarize_sql_result("show student", raw_str, pii_access=False)
    assert summary_masked is not None
    assert "Secret Person" not in summary_masked
    assert "9988776655" not in summary_masked
    assert MASK_VALUE in summary_masked
    assert "Chittoor" in summary_masked

    # When pii_access=True, summary contains raw data
    summary_raw = _summarize_sql_result("show student", raw_str, pii_access=True)
    assert summary_raw is not None
    assert "Secret Person" in summary_raw
    assert "9988776655" in summary_raw


def test_nodes_result_table_str_masking():
    payload = {
        "status": "success",
        "columns": ["student_name", "mobile"],
        "rows": [{"student_name": "Alice", "mobile": "9000000000"}],
    }
    raw_str = json.dumps(payload)

    table_masked = _result_table_str(raw_str, pii_access=False)
    assert "Alice" not in table_masked
    assert "9000000000" not in table_masked
    assert MASK_VALUE in table_masked

    table_unmasked = _result_table_str(raw_str, pii_access=True)
    assert "Alice" in table_unmasked
    assert "9000000000" in table_unmasked


def test_app_extract_sql_and_result_masking():
    payload = {
        "status": "success",
        "columns": ["student_name", "email", "district_name"],
        "rows": [
            {"student_name": "Bob", "email": "bob@example.com", "district_name": "Visakhapatnam"}
        ],
    }
    messages = [
        AIMessage(content="Running SQL query", tool_calls=[{"id": "call_1", "name": "execute_sql", "args": {"query": "SELECT * FROM students"}}]),
        ToolMessage(content=json.dumps(payload), tool_call_id="call_1", name="execute_sql"),
    ]

    # pii_access=False: masked in AskResponse.result
    resp_masked = _extract_sql_and_result(messages, username="viewer", pii_access=False)
    assert resp_masked.result[0]["student_name"] == MASK_VALUE
    assert resp_masked.result[0]["email"] == MASK_VALUE
    assert resp_masked.result[0]["district_name"] == "Visakhapatnam"

    # pii_access=True: unmasked in AskResponse.result
    resp_unmasked = _extract_sql_and_result(messages, username="admin", pii_access=True)
    assert resp_unmasked.result[0]["student_name"] == "Bob"
    assert resp_unmasked.result[0]["email"] == "bob@example.com"
    assert resp_unmasked.result[0]["district_name"] == "Visakhapatnam"


def test_rbac_default_pii_access_denied():
    mgr = RBACManager()
    # All users should have pii_access=False by default
    assert mgr.check_user_privilege("admin", "pii_access") is False
    assert mgr.check_user_privilege("analyst", "pii_access") is False
    assert mgr.check_user_privilege("viewer_user", "pii_access") is False

    # SDUI config reflects piiAccess: False
    sdui = mgr.get_user_sdui_config("viewer_user")
    assert sdui.get("piiAccess") is False


def test_extract_pii_aliases_from_sql():
    sql = "SELECT student_name AS sn, aadhaar_no AS doc_id, phone AS contact, district_name FROM students"
    result = extract_pii_aliases_from_sql(sql)
    assert result == {"sn": "student_name", "doc_id": "aadhaar_no", "contact": "phone"}


def test_extract_pii_aliases_table_qualified():
    sql = "SELECT s.student_name AS nm, s.phone AS ph, s.district_name AS dn FROM students s"
    result = extract_pii_aliases_from_sql(sql)
    assert result.get("nm") == "student_name"
    assert result.get("ph") == "phone"
    assert "dn" not in result  # district_name is not PII


def test_mask_pii_rows_with_alias_bypass():
    sql = "SELECT student_name AS sn, district_name FROM students"
    alias_map = extract_pii_aliases_from_sql(sql)
    rows = [{"sn": "Ravi Kumar", "district_name": "Nellore"}]
    cols = ["sn", "district_name"]
    masked, pii_cols = mask_pii_rows(rows, cols, alias_map=alias_map)
    assert masked[0]["sn"] == MASK_VALUE
    assert masked[0]["district_name"] == "Nellore"
    assert "sn" in pii_cols


def test_no_false_positive_on_cte_and_functions():
    # CTE "AS" should not match as PII column alias
    sql_cte = "WITH dropout_cte AS (SELECT student_name FROM students) SELECT * FROM dropout_cte"
    assert "dropout_cte" not in extract_pii_aliases_from_sql(sql_cte)

    # Function call alias UPPER(student_name) AS nm - safe fallback: not matched
    sql_func = "SELECT UPPER(student_name) AS nm, COUNT(*) AS cnt FROM students"
    res_func = extract_pii_aliases_from_sql(sql_func)
    assert "nm" not in res_func
    assert "cnt" not in res_func


def test_nodes_apply_pii_mask_with_alias_sql():
    payload = {
        "status": "success",
        "columns": ["sn", "contact", "mandal_name"],
        "rows": [{"sn": "John Doe", "contact": "9999999999", "mandal_name": "Kavali"}],
    }
    raw_str = json.dumps(payload)
    sql = "SELECT student_name AS sn, phone AS contact, mandal_name FROM students"

    # pii_access=False: alias-bypassed columns must be masked
    res_false = _apply_pii_mask_to_payload(raw_str, pii_access=False, sql=sql)
    parsed = json.loads(res_false)
    assert parsed["rows"][0]["sn"] == MASK_VALUE
    assert parsed["rows"][0]["contact"] == MASK_VALUE
    assert parsed["rows"][0]["mandal_name"] == "Kavali"

    # pii_access=True: untouched
    res_true = _apply_pii_mask_to_payload(raw_str, pii_access=True, sql=sql)
    assert res_true == raw_str


def test_nodes_summarize_sql_result_alias_masking():
    payload = {
        "status": "success",
        "columns": ["sn", "contact"],
        "rows": [{"sn": "Secret Student", "contact": "9988776655"}],
    }
    raw_str = json.dumps(payload)
    sql = "SELECT student_name AS sn, mobile AS contact FROM students"

    summary = _summarize_sql_result("show student", raw_str, pii_access=False, sql=sql)
    assert summary is not None
    assert "Secret Student" not in summary
    assert "9988776655" not in summary
    assert MASK_VALUE in summary


def test_nodes_result_table_str_alias_masking():
    payload = {
        "status": "success",
        "columns": ["sn", "ph"],
        "rows": [{"sn": "Alice", "ph": "9000000000"}],
    }
    raw_str = json.dumps(payload)
    sql = "SELECT student_name AS sn, phone AS ph FROM students"

    table_masked = _result_table_str(raw_str, pii_access=False, sql=sql)
    assert "Alice" not in table_masked
    assert "9000000000" not in table_masked
    assert MASK_VALUE in table_masked


def test_app_extract_sql_and_result_alias_masking():
    payload = {
        "status": "success",
        "columns": ["sn", "doc_id", "district_name"],
        "rows": [{"sn": "Bob", "doc_id": "1234-5678-9012", "district_name": "Visakhapatnam"}],
    }
    sql = "SELECT student_name AS sn, aadhaar_no AS doc_id, district_name FROM students"
    messages = [
        AIMessage(content="Running SQL", tool_calls=[{"id": "call_2", "name": "execute_sql", "args": {"query": sql}}]),
        ToolMessage(content=json.dumps(payload), tool_call_id="call_2", name="execute_sql"),
    ]

    # pii_access=False: aliased columns masked
    resp_masked = _extract_sql_and_result(messages, username="viewer", pii_access=False)
    assert resp_masked.result[0]["sn"] == MASK_VALUE
    assert resp_masked.result[0]["doc_id"] == MASK_VALUE
    assert resp_masked.result[0]["district_name"] == "Visakhapatnam"

    # pii_access=True: unmasked
    resp_unmasked = _extract_sql_and_result(messages, username="admin", pii_access=True)
    assert resp_unmasked.result[0]["sn"] == "Bob"
    assert resp_unmasked.result[0]["doc_id"] == "1234-5678-9012"
    assert resp_unmasked.result[0]["district_name"] == "Visakhapatnam"


if __name__ == "__main__":
    print("Running test_is_pii_column...")
    test_is_pii_column()
    print("Running test_mask_pii_rows...")
    test_mask_pii_rows()
    print("Running test_mask_pii_rows_no_pii...")
    test_mask_pii_rows_no_pii()
    print("Running test_nodes_apply_pii_mask_to_payload...")
    test_nodes_apply_pii_mask_to_payload()
    print("Running test_nodes_summarize_sql_result_masking...")
    test_nodes_summarize_sql_result_masking()
    print("Running test_nodes_result_table_str_masking...")
    test_nodes_result_table_str_masking()
    print("Running test_app_extract_sql_and_result_masking...")
    test_app_extract_sql_and_result_masking()
    print("Running test_rbac_default_pii_access_denied...")
    test_rbac_default_pii_access_denied()
    print("Running test_extract_pii_aliases_from_sql...")
    test_extract_pii_aliases_from_sql()
    print("Running test_extract_pii_aliases_table_qualified...")
    test_extract_pii_aliases_table_qualified()
    print("Running test_mask_pii_rows_with_alias_bypass...")
    test_mask_pii_rows_with_alias_bypass()
    print("Running test_no_false_positive_on_cte_and_functions...")
    test_no_false_positive_on_cte_and_functions()
    print("Running test_nodes_apply_pii_mask_with_alias_sql...")
    test_nodes_apply_pii_mask_with_alias_sql()
    print("Running test_nodes_summarize_sql_result_alias_masking...")
    test_nodes_summarize_sql_result_alias_masking()
    print("Running test_nodes_result_table_str_alias_masking...")
    test_nodes_result_table_str_alias_masking()
    print("Running test_app_extract_sql_and_result_alias_masking...")
    test_app_extract_sql_and_result_alias_masking()
    print("\n[PASS] ALL PII MASKING & RBAC TESTS (INCLUDING ALIAS BYPASS) PASSED SUCCESSFULLY!")
