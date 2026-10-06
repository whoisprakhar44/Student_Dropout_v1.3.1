"""
End-to-End Integration Test for SSO Auto-Registration, Preset Default Role, and Dashboard Role Assignment.
"""
import ast
import base64
import json
import unittest
from pathlib import Path
from typing import Optional, Dict, Any

from fastapi import FastAPI, Request, HTTPException, Query
from starlette.testclient import TestClient

from database.rbac_manager import RBACManager
from auth_check import safe_decode_jwt

# Extract extract_jwt_payload_from_request from app.py
app_py = (Path(__file__).parent / "app.py").read_text(encoding="utf-8")
tree = ast.parse(app_py)
extract_func_ast = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "extract_jwt_payload_from_request"][0]
mod = ast.Module(body=[extract_func_ast], type_ignores=[])
ns = {"Request": Request, "Optional": Optional, "Dict": Dict, "Any": Any, "safe_decode_jwt": safe_decode_jwt}
exec(compile(mod, "app.py", "exec"), ns)
extract_jwt_payload_from_request = ns["extract_jwt_payload_from_request"]

# Create test FastAPI app with the exact same route handlers as app.py
test_app = FastAPI()
rbac = RBACManager()


@test_app.get("/api/sdui/config")
async def get_sdui_config(
    request: Request,
    username: Optional[str] = Query(default=None),
    userId: Optional[str] = Query(default=None),
    user_id: Optional[str] = Query(default=None),
):
    token_payload = extract_jwt_payload_from_request(request)
    resolved_user = username or userId or user_id
    if not resolved_user or resolved_user.lower() in ("user", "undefined", "null"):
        if token_payload:
            resolved_user = str(
                token_payload.get("preferred_username")
                or token_payload.get("userId")
                or token_payload.get("sub")
                or token_payload.get("cfms_id")
                or "user"
            ).strip()
        else:
            resolved_user = "user"
    return rbac.get_user_sdui_config(resolved_user, token_payload=token_payload)


@test_app.post("/ask")
async def ask_endpoint(request: Request):
    body = await request.json()
    action = body.get("action", "query")
    token_payload = extract_jwt_payload_from_request(request)
    resolved_user = body.get("username") or body.get("userId") or body.get("user_id")
    if not resolved_user or resolved_user.lower() in ("user", "undefined", "null"):
        if token_payload:
            resolved_user = str(
                token_payload.get("preferred_username")
                or token_payload.get("userId")
                or token_payload.get("sub")
                or token_payload.get("cfms_id")
                or "user"
            ).strip()
        else:
            resolved_user = "user"

    rbac.auto_register_or_update_user(resolved_user, token_payload=token_payload)
    if action == "sdui_config":
        return rbac.get_user_sdui_config(resolved_user, token_payload=token_payload)
    return {"status": "success", "username": resolved_user}


@test_app.get("/api/admin/users")
async def admin_get_users(search: Optional[str] = Query(default=None)):
    return rbac.get_users(search)


@test_app.put("/api/admin/users/{username}")
async def admin_update_user(username: str, request: Request):
    data = await request.json()
    if "role_id" in data:
        success, msg = rbac.update_user_role(username, int(data["role_id"]), "admin")
        if not success:
            raise HTTPException(status_code=400, detail=msg)
    return {"status": "success", "username": username}


import httpx


def create_mock_jwt(payload: dict) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    h_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
    p_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    sig_b64 = base64.urlsafe_b64encode(b"mock_signature_bytes").decode().rstrip("=")
    return f"{h_b64}.{p_b64}.{sig_b64}"


class TestSSOAutoRegistrationE2E(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=test_app), base_url="http://testserver")
        with rbac._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM users WHERE username IN ('DL_ROLE8_E2E', 'DL_ROLE9_E2E', 'admin_rtgs_prod')")
            conn.commit()

    async def asyncTearDown(self):
        await self.client.aclose()

    async def test_e2e_sso_new_user_default_role_and_props(self):
        sso_payload = {
            "userId": "DL_ROLE8_E2E",
            "userName": "Officer Prakhar",
            "userRole": "8",
            "deptId": "School Education",
            "distId": "Guntur",
            "passwordstatus": "1",
            "jti": "6F3D0DEC-307A-453A-9D9B-A4616",
            "exp": 1787294530,
            "iss": "YourIssuer",
            "aud": "YourAudience",
        }
        token = create_mock_jwt(sso_payload)

        # 1. User arrives at GET /api/sdui/config with Bearer token
        res = await self.client.get(
            "/api/sdui/config?username=DL_ROLE8_E2E",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(res.status_code, 200)
        config = res.json()

        # Verify preset default config matching exact prompt specifications:
        self.assertEqual(config["is_active"], 1)
        self.assertFalse(config["isSchemaEnabled"])
        self.assertFalse(config["showAboutSection"])
        self.assertFalse(config["allowTableExport"])
        self.assertFalse(config["allowCsvExport"])
        self.assertFalse(config["allowExcelExport"])
        self.assertFalse(config["allowCopyTable"])
        self.assertTrue(config["copyProtection"])
        self.assertTrue(config["devToolsProtection"])
        self.assertFalse(config["piiAccess"])
        self.assertEqual(config["role"], "Default Role")

        # Verify token_props contains all decoded claims
        props = config.get("token_props", {})
        self.assertEqual(props.get("userId"), "DL_ROLE8_E2E")
        self.assertEqual(props.get("deptId"), "School Education")
        self.assertEqual(props.get("distId"), "Guntur")
        self.assertEqual(props.get("userRole"), "8")
        self.assertEqual(props.get("passwordstatus"), "1")
        self.assertEqual(props.get("iss"), "YourIssuer")

        # 2. Administrator visits dashboard: GET /api/admin/users
        res_admin = await self.client.get("/api/admin/users?search=DL_ROLE8_E2E")
        self.assertEqual(res_admin.status_code, 200)
        users = res_admin.json()
        matching = [u for u in users if u["username"] == "DL_ROLE8_E2E"]
        self.assertEqual(len(matching), 1)
        u_rec = matching[0]
        self.assertEqual(u_rec["role_name"], "Default Role")
        self.assertEqual(u_rec["token_props"]["distId"], "Guntur")
        self.assertEqual(u_rec["token_props"]["userRole"], "8")

        # 3. Administrator reassigns DL_ROLE8_E2E to Data Analyst
        roles = rbac.get_roles()
        analyst_role = next(r for r in roles if r["name"] == "Data Analyst")
        res_reassign = await self.client.put(
            f"/api/admin/users/DL_ROLE8_E2E",
            json={"role_id": analyst_role["id"]},
        )
        self.assertEqual(res_reassign.status_code, 200)

        # 4. User queries SDUI config again - now has Data Analyst privileges
        res2 = await self.client.get(
            "/api/sdui/config?username=DL_ROLE8_E2E",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(res2.status_code, 200)
        config2 = res2.json()
        self.assertEqual(config2["role"], "Data Analyst")
        self.assertTrue(config2["allowTableExport"])
        self.assertTrue(config2["isSchemaEnabled"])
        self.assertEqual(config2["token_props"]["deptId"], "School Education")

    async def test_e2e_post_ask_sdui_config_auto_registration(self):
        sso_payload = {
            "userId": "DL_ROLE9_E2E",
            "userName": "Officer Krishna",
            "userRole": "9",
            "deptId": "Revenue",
            "distId": "Krishna",
            "iss": "YourIssuer",
        }
        token = create_mock_jwt(sso_payload)

        res = await self.client.post(
            "/ask",
            json={"action": "sdui_config", "username": "DL_ROLE9_E2E"},
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["is_active"], 1)
        self.assertEqual(data["role"], "Default Role")
        self.assertFalse(data["isSchemaEnabled"])
        self.assertFalse(data["piiAccess"])
        self.assertTrue(data["copyProtection"])
        self.assertTrue(data["devToolsProtection"])
        self.assertEqual(data["token_props"]["deptId"], "Revenue")

    async def test_e2e_prod_token_structure_preferred_username_and_details(self):
        prod_payload = {
            "iss": "ap-citizen360-web",
            "aud": "apdl-web-api",
            "sub": "admin",
            "preferred_username": "admin_rtgs_prod",
            "role": "Administrator",
            "department": "RTGS",
            "dept_id": "RTGS",
            "cfms_id": "admin_cfms_123",
            "iat": 1790317517,
            "exp": 1790346317,
            "jti": "696ed6ba-67be-453f-a034-73f7abd40ed6"
        }
        token = create_mock_jwt(prod_payload)

        # 1. User arrives at GET /api/sdui/config without passing username in query (or passing preferred_username)
        res = await self.client.get(
            "/api/sdui/config",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(res.status_code, 200)
        config = res.json()
        self.assertEqual(config["is_active"], 1)
        self.assertEqual(config["role"], "Default Role")
        self.assertFalse(config["isSchemaEnabled"])
        self.assertEqual(config["token_props"]["preferred_username"], "admin_rtgs_prod")
        self.assertEqual(config["token_props"]["department"], "RTGS")
        self.assertEqual(config["token_props"]["role"], "Administrator")
        self.assertEqual(config["token_props"]["cfms_id"], "admin_cfms_123")

        # 2. Check admin directory GET /api/admin/users
        res_admin = await self.client.get("/api/admin/users?search=admin_rtgs_prod")
        self.assertEqual(res_admin.status_code, 200)
        users = res_admin.json()
        matching = [u for u in users if u["username"] == "admin_rtgs_prod"]
        self.assertEqual(len(matching), 1)
        u_rec = matching[0]
        self.assertEqual(u_rec["preferred_username"], "admin_rtgs_prod")
        self.assertEqual(u_rec["department"], "RTGS")
        self.assertEqual(u_rec["token_role"], "Administrator")
        self.assertEqual(u_rec["cfms_id"], "admin_cfms_123")
        self.assertEqual(u_rec["role_name"], "Default Role")

        # 3. Check roles endpoint GET /api/admin/roles contains user in assigned_users
        roles = rbac.get_roles()
        default_role = next(r for r in roles if r["name"] == "Default Role")
        assigned_user = next(u for u in default_role["assigned_users"] if u["username"] == "admin_rtgs_prod")
        self.assertEqual(assigned_user["preferred_username"], "admin_rtgs_prod")
        self.assertEqual(assigned_user["department"], "RTGS")
        self.assertEqual(assigned_user["token_role"], "Administrator")
        self.assertEqual(assigned_user["cfms_id"], "admin_cfms_123")


if __name__ == "__main__":
    unittest.main()
