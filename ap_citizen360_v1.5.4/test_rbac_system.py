"""
Comprehensive Verification Suite for AP Citizen 360 RBAC, Dashboard & SDUI Governance
Tests:
- Admin Authentication & JWT token issuing
- Universal Control Kill-Switch overrides
- Role creation, privilege matrix toggles, deletion
- User role assignment, suspension, and sync
- SDUI config generation matching frontend contract
- API-level enforcement of schema and about sections
"""

import sys
import time
import unittest
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from database.rbac_manager import RBACManager, CORE_PRIVILEGES


class TestRBACGovernance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mgr = RBACManager()

    def test_01_admin_default_login(self):
        """Admin user should authenticate successfully with default credentials admin/admin."""
        admin = self.mgr.verify_admin_credentials("admin", "admin")
        self.assertIsNotNone(admin, "Default admin/admin credentials must authenticate")
        self.assertEqual(admin["username"], "admin")

        # Wrong password should fail
        wrong = self.mgr.verify_admin_credentials("admin", "incorrect_pass")
        self.assertIsNone(wrong, "Wrong password must fail")

        # Invalid username should fail
        unknown = self.mgr.verify_admin_credentials("ghost_user", "admin")
        self.assertIsNone(unknown, "Unknown admin username must fail")

    def test_02_jwt_generation_and_verification(self):
        """JWT token generation, signature validation, and payload extraction."""
        token = self.mgr.create_jwt_token("admin", "Administrator", "admin")
        self.assertIsInstance(token, str)

        payload = self.mgr.verify_jwt_token(token)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["sub"], "admin")
        self.assertEqual(payload["role"], "admin")

        # Corrupted token should fail
        corrupted = token + "xyz"
        self.assertIsNone(self.mgr.verify_jwt_token(corrupted))

    def test_03_universal_controls_and_kill_switch(self):
        """Universal controls must exist and act as global master kill-switches."""
        controls = self.mgr.get_universal_controls()
        self.assertGreaterEqual(len(controls), 6)
        keys = [c["privilege_key"] for c in controls]
        for expected in ["schema_layer", "about_section", "allow_download", "allow_copy", "content_copy_protection", "devtools_protection"]:
            self.assertIn(expected, keys)

        # Analyst user normally has schema_layer enabled
        analyst_sdui = self.mgr.get_user_sdui_config("analyst")
        self.assertTrue(analyst_sdui["isSchemaEnabled"], "Data Analyst should normally have schema_layer enabled")

        # ENGAGE UNIVERSAL KILL-SWITCH for schema_layer
        success = self.mgr.toggle_universal_control("schema_layer", False, "test_suite")
        self.assertTrue(success)
        self.assertFalse(self.mgr.get_universal_status("schema_layer"))

        # Effective privilege for analyst must now be FALSE
        self.assertFalse(self.mgr.check_user_privilege("analyst", "schema_layer"), "Kill-switch must override analyst privilege")
        sdui_overridden = self.mgr.get_user_sdui_config("analyst")
        self.assertFalse(sdui_overridden["isSchemaEnabled"], "SDUI config must reflect universal kill-switch")

        # RESTORE UNIVERSAL CONTROL
        self.mgr.toggle_universal_control("schema_layer", True, "test_suite")
        self.assertTrue(self.mgr.check_user_privilege("analyst", "schema_layer"), "Restoring universal control restores analyst access")

    def test_04_roles_crud_and_privileges_matrix(self):
        """Roles creation, privilege assignment, privilege toggling, and deletion."""
        # Create Custom Role
        custom_privs = {
            "schema_layer": False,
            "about_section": True,
            "allow_download": True,
            "allow_copy": False,
            "content_copy_protection": True,
            "devtools_protection": True,
        }
        ok, msg, role_id = self.mgr.create_role("Test Inspector Role", "Role for automated testing", custom_privs, "test_suite")
        self.assertTrue(ok, f"Role creation failed: {msg}")
        self.assertIsNotNone(role_id)

        # Verify fetched role
        role = self.mgr.get_role(role_id)
        self.assertEqual(role["name"], "Test Inspector Role")
        self.assertFalse(role["privileges"]["schema_layer"])
        self.assertTrue(role["privileges"]["allow_download"])

        # Toggle individual privilege within role
        toggle_ok = self.mgr.toggle_role_privilege(role_id, "schema_layer", True, "test_suite")
        self.assertTrue(toggle_ok)
        role_updated = self.mgr.get_role(role_id)
        self.assertTrue(role_updated["privileges"]["schema_layer"])

        # Delete Custom Role
        del_ok, del_msg = self.mgr.delete_role(role_id, "test_suite")
        self.assertTrue(del_ok, f"Role deletion failed: {del_msg}")

        # System role deletion should be rejected
        roles = self.mgr.get_roles()
        super_admin_role = next(r for r in roles if r["name"] == "Super Admin")
        sys_del_ok, _ = self.mgr.delete_role(super_admin_role["id"], "test_suite")
        self.assertFalse(sys_del_ok, "Protected system roles must NOT be deletable")

    def test_05_user_management_and_effective_privileges(self):
        """User creation, role assignment, active/suspended status toggle."""
        # Create test user
        roles = self.mgr.get_roles()
        analyst_role = next(r for r in roles if r["name"] == "Data Analyst")
        viewer_role = next(r for r in roles if r["name"] == "Citizen Viewer")

        ok, msg = self.mgr.create_or_update_user("test_governance_user", "Governance Officer", "gov@ap.gov.in", analyst_role["id"], True, "test_suite")
        self.assertTrue(ok)

        # Check effective permissions (Analyst: download=True)
        self.assertTrue(self.mgr.check_user_privilege("test_governance_user", "allow_download"))

        # Reassign to Citizen Viewer (Download=False)
        reassign_ok, _ = self.mgr.update_user_role("test_governance_user", viewer_role["id"], "test_suite")
        self.assertTrue(reassign_ok)
        self.assertFalse(self.mgr.check_user_privilege("test_governance_user", "allow_download"))

        # Reassign back to Analyst and Suspend User
        self.mgr.update_user_role("test_governance_user", analyst_role["id"], "test_suite")
        self.mgr.toggle_user_active("test_governance_user", False, "test_suite")
        # Suspended user must have NO privileges
        self.assertFalse(self.mgr.check_user_privilege("test_governance_user", "allow_download"))
        self.assertFalse(self.mgr.check_user_privilege("test_governance_user", "schema_layer"))

        # Reactivate User
        self.mgr.toggle_user_active("test_governance_user", True, "test_suite")
        self.assertTrue(self.mgr.check_user_privilege("test_governance_user", "allow_download"))

    def test_06_sdui_config_contract(self):
        """SDUI config payload must contain all frontend required fields."""
        sdui = self.mgr.get_user_sdui_config("analyst")
        required_fields = [
            "status", "username", "role", "is_active",
            "isSchemaEnabled", "showAboutSection", "allowTableExport",
            "allowCsvExport", "allowExcelExport", "allowCopyTable",
            "copyProtection", "devToolsProtection", "universal_overrides"
        ]
        for f in required_fields:
            self.assertIn(f, sdui, f"SDUI payload missing required key '{f}'")

    def test_07_audit_trail_logging(self):
        """Administrative audit events must be logged and retrievable."""
        unique_id = "audit_check_" + str(int(time.time() * 1000))
        self.mgr.log_audit_event("admin", "TEST_SECURITY_EVENT", "test_target", unique_id, "Automated security test entry")
        new_audits = self.mgr.get_audit_logs(limit=50)
        matching = [a for a in new_audits if a.get("target_id") == unique_id]
        self.assertTrue(len(matching) > 0, "Newly created audit log must be present in retrieved logs")
        self.assertEqual(matching[0]["action"], "TEST_SECURITY_EVENT")
    def test_08_sso_auto_registration_and_default_role(self):
        """
        Verify:
        - New user is automatically registered with 'Default Role'
        - Default role matches the exact preset configuration:
            is_active: 1
            isSchemaEnabled: false
            showAboutSection: false
            allowTableExport: false
            allowCsvExport: false
            allowExcelExport: false
            allowCopyTable: false
            copyProtection: true
            devToolsProtection: true
            piiAccess: false
        - All decoded SSO token claims are stored as props and values
        - Admin can see the user in get_users() with all token_props
        - Admin can assign a new role to them
        - Subsequent requests preserve the assigned role
        """
        sample_sso_payload = {
            "userId": "DL_ROLE8_TEST",
            "userName": "District Officer Testing",
            "userRole": "8",
            "deptId": "All",
            "distId": "All",
            "passwordstatus": "1",
            "jti": "6F3D0DEC-307A-453A-9D9B-A4616-TEST",
            "exp": 1787294530,
            "iss": "YourIssuer",
            "aud": "YourAudience",
        }

        with self.mgr._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM users WHERE username = 'DL_ROLE8_TEST'")
            conn.commit()

        # 1. Fetch SDUI config for a brand new user with SSO claims
        sdui = self.mgr.get_user_sdui_config("DL_ROLE8_TEST", token_payload=sample_sso_payload)

        # Verify exact preset config:
        self.assertEqual(sdui["is_active"], 1)
        self.assertFalse(sdui["isSchemaEnabled"])
        self.assertFalse(sdui["showAboutSection"])
        self.assertFalse(sdui["allowTableExport"])
        self.assertFalse(sdui["allowCsvExport"])
        self.assertFalse(sdui["allowExcelExport"])
        self.assertFalse(sdui["allowCopyTable"])
        self.assertTrue(sdui["copyProtection"])
        self.assertTrue(sdui["devToolsProtection"])
        self.assertFalse(sdui["piiAccess"])
        self.assertEqual(sdui["role"], "Default Role")

        # Verify all SSO claims stored as props & values
        self.assertIn("token_props", sdui)
        self.assertEqual(sdui["token_props"]["userId"], "DL_ROLE8_TEST")
        self.assertEqual(sdui["token_props"]["userRole"], "8")
        self.assertEqual(sdui["token_props"]["deptId"], "All")
        self.assertEqual(sdui["token_props"]["distId"], "All")
        self.assertEqual(sdui["token_props"]["passwordstatus"], "1")
        self.assertEqual(sdui["token_props"]["jti"], "6F3D0DEC-307A-453A-9D9B-A4616-TEST")

        # 2. Check get_users() in dashboard/admin view
        all_users = self.mgr.get_users("DL_ROLE8_TEST")
        matching = [u for u in all_users if u["username"] == "DL_ROLE8_TEST"]
        self.assertEqual(len(matching), 1)
        user_record = matching[0]
        self.assertEqual(user_record["role_name"], "Default Role")
        self.assertEqual(user_record["token_props"]["userRole"], "8")

        # 3. Admin reassigns role to Data Analyst
        analyst_role = next(r for r in self.mgr.get_roles() if r["name"] == "Data Analyst")
        reassign_ok, _ = self.mgr.update_user_role("DL_ROLE8_TEST", analyst_role["id"], "admin")
        self.assertTrue(reassign_ok)

        # 4. Subsequent requests from user preserve the assigned role
        sdui_after = self.mgr.get_user_sdui_config("DL_ROLE8_TEST", token_payload=sample_sso_payload)
        self.assertEqual(sdui_after["role"], "Data Analyst")
        self.assertTrue(sdui_after["allowTableExport"])
    def test_09_chatbot_privilege_governance_3_tiers(self):
        """
        Verify complete 3-tier Show Chatbot (allow_chatbot_access / allowChatbotAccess) governance:
        1. Universal Control (Master Kill-Switch): When OFF, denies all users worldwide.
        2. Role Privileges: Role setting governs default permissions.
        3. User Privileges: Per-user override supersedes Role setting, but obeys Universal Kill-Switch.
        4. SDUI config: Returns allowChatbotAccess, canAccessChatbot, showChatbot matching frontend contract.
        5. Key normalization: CamelCase, snake_case, and aliases all normalize accurately.
        """
        # A. Normalization Check
        self.assertTrue(self.mgr.check_user_privilege("analyst", "allow_chatbot_access"))
        self.assertTrue(self.mgr.check_user_privilege("analyst", "allowChatbotAccess"))
        self.assertTrue(self.mgr.check_user_privilege("analyst", "canAccessChatbot"))
        self.assertTrue(self.mgr.check_user_privilege("analyst", "showChatbot"))

        # B. SDUI Config Payload Check
        sdui = self.mgr.get_user_sdui_config("analyst")
        self.assertIn("allowChatbotAccess", sdui)
        self.assertIn("canAccessChatbot", sdui)
        self.assertIn("showChatbot", sdui)
        self.assertTrue(sdui["allowChatbotAccess"])
        self.assertTrue(sdui["canAccessChatbot"])
        self.assertTrue(sdui["showChatbot"])

        # C. Tier 1: Universal Kill-Switch Master Override
        ok = self.mgr.toggle_universal_control("allow_chatbot_access", False, "test_suite")
        self.assertTrue(ok)
        self.assertFalse(self.mgr.get_universal_status("allow_chatbot_access"))
        self.assertFalse(self.mgr.check_user_privilege("analyst", "allow_chatbot_access"))
        self.assertFalse(self.mgr.check_user_privilege("super_admin", "allow_chatbot_access"))
        sdui_killed = self.mgr.get_user_sdui_config("analyst")
        self.assertFalse(sdui_killed["allowChatbotAccess"])
        self.assertFalse(sdui_killed["canAccessChatbot"])
        self.assertFalse(sdui_killed["showChatbot"])

        # Restore Universal Control
        self.mgr.toggle_universal_control("allow_chatbot_access", True, "test_suite")
        self.assertTrue(self.mgr.get_universal_status("allow_chatbot_access"))
        self.assertTrue(self.mgr.check_user_privilege("analyst", "allow_chatbot_access"))

        # D. Tier 2: Role Level Governance
        # Create role with chatbot access disabled
        no_chat_role_privs = {
            "allow_chatbot_access": False,
            "schema_layer": False,
            "about_section": False,
            "allow_download": False,
            "allow_copy": False,
            "content_copy_protection": True,
            "devtools_protection": True,
            "pii_access": False,
        }
        ok, _, role_id = self.mgr.create_role("No Chat Role", "Role without chatbot access", no_chat_role_privs, "test_suite")
        self.assertTrue(ok)

        # Register user with this restricted role
        test_user = "chat_tiered_test_user"
        self.mgr.create_or_update_user(test_user, "Tiered Test User", f"{test_user}@ap.gov.in", role_id)
        self.assertFalse(self.mgr.check_user_privilege(test_user, "allow_chatbot_access"))
        sdui_user = self.mgr.get_user_sdui_config(test_user)
        self.assertFalse(sdui_user["allowChatbotAccess"])

        # E. Tier 3: Per-User Privilege Override
        # Admin grants chatbot access specifically to this user (overriding role)
        ok, msg = self.mgr.set_user_privilege_override(test_user, "allow_chatbot_access", True, "admin")
        self.assertTrue(ok)
        overrides = self.mgr.get_user_privilege_overrides(test_user)
        self.assertEqual(overrides.get("allow_chatbot_access"), True)

        # User now HAS chatbot access despite role having it disabled!
        self.assertTrue(self.mgr.check_user_privilege(test_user, "allow_chatbot_access"))
        sdui_overridden = self.mgr.get_user_sdui_config(test_user)
        self.assertTrue(sdui_overridden["allowChatbotAccess"])
        self.assertTrue(sdui_overridden["canAccessChatbot"])
        self.assertEqual(sdui_overridden["user_overrides"].get("allow_chatbot_access"), True)

        # But Universal Kill-Switch still beats the user-level override!
        self.mgr.toggle_universal_control("allow_chatbot_access", False, "test_suite")
        self.assertFalse(self.mgr.check_user_privilege(test_user, "allow_chatbot_access"))
        self.mgr.toggle_universal_control("allow_chatbot_access", True, "test_suite")
        self.assertTrue(self.mgr.check_user_privilege(test_user, "allow_chatbot_access"))

        # Revert override (set to None -> inherits from role again)
        ok, msg = self.mgr.set_user_privilege_override(test_user, "allow_chatbot_access", None, "admin")
        self.assertTrue(ok)
        self.assertNotIn("allow_chatbot_access", self.mgr.get_user_privilege_overrides(test_user))
        self.assertFalse(self.mgr.check_user_privilege(test_user, "allow_chatbot_access"))

        # Clean up test role & user
        with self.mgr._get_connection() as conn:
            conn.execute("DELETE FROM users WHERE username = ?", (test_user,))
            conn.execute("DELETE FROM roles WHERE id = ?", (role_id,))
            conn.commit()

    def test_10_api_enforcement_chatbot_access(self):
        """Verify API /ask rejects queries when allow_chatbot_access is revoked."""
        from fastapi.testclient import TestClient
        from app import app

        client = TestClient(app)

        username = "chat_api_test_user"
        with self.mgr._get_connection() as conn:
            conn.execute("DELETE FROM user_privileges WHERE username = ?", (username,))
            conn.execute("DELETE FROM users WHERE username = ?", (username,))
            conn.commit()

        try:
            # 1. User with chatbot access enabled -> ask query does not get 403 / chatbot denied
            self.mgr.auto_register_or_update_user(username)
            self.assertTrue(self.mgr.check_user_privilege(username, "allow_chatbot_access"))

            # 2. Revoke chatbot access via user override
            self.mgr.set_user_privilege_override(username, "allow_chatbot_access", False, "admin")
            self.assertFalse(self.mgr.check_user_privilege(username, "allow_chatbot_access"))

            import jwt
            token = jwt.encode({"iss": "ap-citizen360-web", "sub": username, "preferred_username": username}, "secret", algorithm="HS256")
            headers = {"Authorization": f"Bearer {token}"}

            resp = client.post(
                "/ask",
                json={"question": "What is the total count?", "action": "ask", "username": username},
                headers=headers
            )
            self.assertEqual(resp.status_code, 200)
            body = resp.text
            self.assertIn("Chatbot access privilege is not granted", body)

            # 3. Restore chatbot access
            self.mgr.set_user_privilege_override(username, "allow_chatbot_access", None, "admin")
            self.assertTrue(self.mgr.check_user_privilege(username, "allow_chatbot_access"))
        finally:
            with self.mgr._get_connection() as conn:
                conn.execute("DELETE FROM user_privileges WHERE username = ?", (username,))
                conn.execute("DELETE FROM users WHERE username = ?", (username,))
                conn.commit()

        # Clean up
        with self.mgr._get_connection() as conn:
            conn.execute("DELETE FROM users WHERE username = ?", (username,))
            conn.commit()


if __name__ == "__main__":
    unittest.main()
