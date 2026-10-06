"""
Comprehensive Test Suite for Subpath Routing & Reverse Proxy Adaptation.
Tests:
1. get_base_path() with env variables (APP_SUBPATH, BASE_PATH, ROOT_PATH, SUBPATH)
2. get_base_path() with X-Forwarded-Prefix header and ASGI root_path
3. render_template_with_base_path() token replacement and script injection
4. Verification of templates ensuring all endpoints use BASE_PATH
"""

import os
import unittest
from pathlib import Path
from unittest.mock import MagicMock


class TestSubpathRouting(unittest.TestCase):
    def setUp(self):
        # Save original env
        self.original_env = {
            "APP_SUBPATH": os.environ.get("APP_SUBPATH"),
            "BASE_PATH": os.environ.get("BASE_PATH"),
            "ROOT_PATH": os.environ.get("ROOT_PATH"),
            "SUBPATH": os.environ.get("SUBPATH"),
        }
        # Clear env vars for clean testing
        for k in self.original_env:
            os.environ.pop(k, None)

    def tearDown(self):
        # Restore original env
        for k, v in self.original_env.items():
            if v is not None:
                os.environ[k] = v
            else:
                os.environ.pop(k, None)

    def _get_helper(self):
        # Extract the exact get_base_path and render_template_with_base_path definitions directly from app.py
        import ast
        from typing import Optional, Any
        app_path = Path(__file__).parent / "app.py"
        code = app_path.read_text(encoding="utf-8")
        tree = ast.parse(code)
        funcs = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in ('get_base_path', 'render_template_with_base_path')]
        mod = ast.Module(body=funcs, type_ignores=[])
        ns = {"Optional": Optional, "Request": Any, "os": os}
        exec(compile(mod, "app.py", "exec"), ns)
        return ns["get_base_path"], ns["render_template_with_base_path"]

    def test_01_env_app_subpath_normalization(self):
        """Test that get_base_path correctly normalizes various env values."""
        get_base_path, _ = self._get_helper()

        # Leading slash
        os.environ["APP_SUBPATH"] = "/some_path"
        self.assertEqual(get_base_path(), "/some_path")

        # Trailing slash stripped
        os.environ["APP_SUBPATH"] = "/some_path/"
        self.assertEqual(get_base_path(), "/some_path")

        # Missing leading slash added
        os.environ["APP_SUBPATH"] = "some_path"
        self.assertEqual(get_base_path(), "/some_path")

        # Deep subpath
        os.environ["APP_SUBPATH"] = "/org/app/v1"
        self.assertEqual(get_base_path(), "/org/app/v1")

        # Root slash resolves to empty string
        os.environ["APP_SUBPATH"] = "/"
        self.assertEqual(get_base_path(), "")

        # Empty string resolves to empty string
        os.environ["APP_SUBPATH"] = ""
        self.assertEqual(get_base_path(), "")

    def test_02_env_variable_fallbacks(self):
        """Test fallback across BASE_PATH, ROOT_PATH, and SUBPATH."""
        get_base_path, _ = self._get_helper()

        os.environ["BASE_PATH"] = "/base_test"
        self.assertEqual(get_base_path(), "/base_test")
        os.environ.pop("BASE_PATH")

        os.environ["ROOT_PATH"] = "/root_test"
        self.assertEqual(get_base_path(), "/root_test")
        os.environ.pop("ROOT_PATH")

        os.environ["SUBPATH"] = "/sub_test"
        self.assertEqual(get_base_path(), "/sub_test")
        os.environ.pop("SUBPATH")

    def test_03_x_forwarded_prefix_header(self):
        """Test dynamic extraction from X-Forwarded-Prefix header when env is not set."""
        get_base_path, _ = self._get_helper()

        # Mock request with header
        mock_req = MagicMock()
        mock_req.headers = {"x-forwarded-prefix": "/reverse_proxy"}
        mock_req.scope = {}
        self.assertEqual(get_base_path(mock_req), "/reverse_proxy")

        # Header with trailing slash
        mock_req.headers = {"x-forwarded-prefix": "/reverse_proxy/"}
        self.assertEqual(get_base_path(mock_req), "/reverse_proxy")

        # Header without leading slash
        mock_req.headers = {"x-forwarded-prefix": "reverse_proxy"}
        self.assertEqual(get_base_path(mock_req), "/reverse_proxy")

    def test_04_asgi_root_path_fallback(self):
        """Test fallback to ASGI root_path scope."""
        get_base_path, _ = self._get_helper()

        mock_req = MagicMock()
        mock_req.headers = {}
        mock_req.scope = {"root_path": "/asgi_root"}
        self.assertEqual(get_base_path(mock_req), "/asgi_root")

    def test_05_render_template_with_base_path(self):
        """Test template rendering replaces {{BASE_PATH}} and injects window.__BASE_PATH__."""
        _, render_template_with_base_path = self._get_helper()

        sample_html = """<!DOCTYPE html>
<html>
<head>
  <title>Test Page</title>
</head>
<body>
  <a href="{{BASE_PATH}}/dashboard">Go</a>
</body>
</html>"""

        rendered = render_template_with_base_path(sample_html, "/subpath")
        self.assertIn("window.__BASE_PATH__ = '/subpath';", rendered)
        self.assertIn('href="/subpath/dashboard"', rendered)
        self.assertNotIn("{{BASE_PATH}}", rendered)

    def test_06_dashboard_templates_contain_base_path(self):
        """Verify that dashboard.html and dashboard_login.html have getBasePath and no hardcoded /api/admin calls."""
        templates_dir = Path(__file__).parent / "templates"
        
        login_html = (templates_dir / "dashboard_login.html").read_text(encoding="utf-8")
        self.assertIn("getBasePath", login_html)
        self.assertIn("BASE_PATH", login_html)
        self.assertIn("${BASE_PATH}/dashboard/login", login_html)

        dash_html = (templates_dir / "dashboard.html").read_text(encoding="utf-8")
        self.assertIn("getBasePath", dash_html)
        self.assertIn("BASE_PATH", dash_html)
        self.assertIn("${BASE_PATH}/api/admin/overview", dash_html)
        self.assertIn("${BASE_PATH}/api/admin/universal", dash_html)
        self.assertIn("${BASE_PATH}/api/admin/roles", dash_html)
        self.assertIn("${BASE_PATH}/api/admin/users", dash_html)
        self.assertIn("${BASE_PATH}/dashboard/logout", dash_html)
        self.assertIn("${BASE_PATH}/dashboard/login", dash_html)

        # Make sure no raw fetch('/api/admin/ exists
        self.assertNotIn("fetch('/api/admin/", dash_html)
        self.assertNotIn('fetch("/api/admin/', dash_html)

    def test_07_index_and_logs_templates_contain_base_path(self):
        """Verify that index.html and logs.html are subpath adaptive."""
        templates_dir = Path(__file__).parent / "templates"

        index_html = (templates_dir / "index.html").read_text(encoding="utf-8")
        self.assertIn("getBasePath", index_html)
        self.assertIn("BASE_PATH", index_html)
        self.assertIn("${BASE_PATH}/suggestions/meta", index_html)
        self.assertIn("${BASE_PATH}/ask", index_html)
        self.assertNotIn("fetch('/ask'", index_html)

        logs_html = (templates_dir / "logs.html").read_text(encoding="utf-8")
        self.assertIn("window.__BASE_PATH__", logs_html)


if __name__ == "__main__":
    unittest.main()
