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
        initial_audits = len(self.mgr.get_audit_logs(limit=200))
        self.mgr.log_audit_event("admin", "TEST_SECURITY_EVENT", "test_target", "test_id_101", "Automated security test entry")
        new_audits = self.mgr.get_audit_logs(limit=200)
        self.assertGreater(len(new_audits), initial_audits)
        latest = new_audits[0]
        self.assertEqual(latest["action"], "TEST_SECURITY_EVENT")
        self.assertEqual(latest["target_id"], "test_id_101")


if __name__ == "__main__":
    unittest.main()
