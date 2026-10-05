"""
AP Citizen 360 — Role-Based Access Control (RBAC) & SDUI Governance Manager
Provides SQLite database initialization, JWT authentication, role management,
universal master kill-switches, audit logging, and privilege resolution.
"""

from __future__ import annotations

import os
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import bcrypt
import jwt

# Paths & Settings
DB_DIR = Path(__file__).resolve().parent
RBAC_DB_PATH = DB_DIR / "rbac.db"
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "ap-citizen360-rbac-super-secret-key-2026")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

_lock = threading.Lock()

# Standard Privileges Specification
CORE_PRIVILEGES = [
    {
        "key": "schema_layer",
        "name": "Schema Layer Access",
        "category": "Data Access",
        "description": "Allows switching between Curated and Schema Chat mode and querying underlying canonical tables.",
        "default_enabled": 1,
    },
    {
        "key": "about_section",
        "name": "About & Canonical Reference",
        "category": "Documentation",
        "description": "Controls visibility and API access to canonical schema metadata, entity definitions, and data dictionary.",
        "default_enabled": 1,
    },
    {
        "key": "allow_download",
        "name": "Data Export (CSV & Excel)",
        "category": "Data Export",
        "description": "Allows downloading query results and data tables as CSV or Excel (.xlsx) files.",
        "default_enabled": 1,
    },
    {
        "key": "allow_copy",
        "name": "Copy Results & SQL",
        "category": "Clipboard",
        "description": "Allows users to copy tabular data, SQL statements, and AI answers to their clipboard.",
        "default_enabled": 1,
    },
    {
        "key": "content_copy_protection",
        "name": "Content Copy Protection",
        "category": "Security Guard",
        "description": "Enforces frontend text selection blocking, right-click context menu lock, and text copy suppression.",
        "default_enabled": 1,
    },
    {
        "key": "devtools_protection",
        "name": "Developer Tools Protection",
        "category": "Security Guard",
        "description": "Detects and blocks browser developer console shortcuts (F12, Ctrl+Shift+I, Ctrl+U).",
        "default_enabled": 1,
    },
]

# Standard Seeded Roles
DEFAULT_ROLES = [
    {
        "name": "Super Admin",
        "description": "Unrestricted administrative role with access to all data layers, tools, and configurations.",
        "is_system": 1,
        "is_active": 1,
        "privileges": {
            "schema_layer": 1,
            "about_section": 1,
            "allow_download": 1,
            "allow_copy": 1,
            "content_copy_protection": 0,
            "devtools_protection": 0,
        },
    },
    {
        "name": "Data Analyst",
        "description": "Authorized analytics role with full query capabilities, schema exploration, and data export.",
        "is_system": 0,
        "is_active": 1,
        "privileges": {
            "schema_layer": 1,
            "about_section": 1,
            "allow_download": 1,
            "allow_copy": 1,
            "content_copy_protection": 0,
            "devtools_protection": 0,
        },
    },
    {
        "name": "Department Officer",
        "description": "Executive/Secretariat user with curated query and reporting access. Protected interface.",
        "is_system": 0,
        "is_active": 1,
        "privileges": {
            "schema_layer": 0,
            "about_section": 1,
            "allow_download": 1,
            "allow_copy": 1,
            "content_copy_protection": 1,
            "devtools_protection": 1,
        },
    },
    {
        "name": "Citizen Viewer",
        "description": "Restricted public viewer. Curated questions only, strictly prohibited from downloading or copying.",
        "is_system": 0,
        "is_active": 1,
        "privileges": {
            "schema_layer": 0,
            "about_section": 0,
            "allow_download": 0,
            "allow_copy": 0,
            "content_copy_protection": 1,
            "devtools_protection": 1,
        },
    },
]


class RBACManager:
    """Singleton manager for Role-Based Access Control, Universal Controls, and Audit Logs."""

    _instance: Optional[RBACManager] = None

    def __new__(cls, db_path: Optional[Path] = None) -> RBACManager:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._db_path = db_path or RBAC_DB_PATH
            cls._instance._init_db()
        return cls._instance

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path), timeout=20.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    def _init_db(self) -> None:
        """Create tables and seed default admin, roles, and privileges if not already present."""
        os.makedirs(self._db_path.parent, exist_ok=True)
        with _lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # 1. Admin Users Table (for dashboard login)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS admin_users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT UNIQUE NOT NULL,
                        password_hash TEXT NOT NULL,
                        full_name TEXT,
                        role TEXT DEFAULT 'admin',
                        is_active INTEGER DEFAULT 1,
                        created_at TEXT NOT NULL,
                        last_login TEXT
                    );
                """)

                # 2. Universal Controls Table (Master Kill-Switch)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS universal_controls (
                        privilege_key TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        category TEXT NOT NULL,
                        description TEXT,
                        is_enabled INTEGER DEFAULT 1,
                        updated_at TEXT NOT NULL,
                        updated_by TEXT DEFAULT 'admin'
                    );
                """)

                # 3. Roles Table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS roles (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT UNIQUE NOT NULL,
                        description TEXT,
                        is_system INTEGER DEFAULT 0,
                        is_active INTEGER DEFAULT 1,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );
                """)

                # 4. Role Privileges Mapping Table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS role_privileges (
                        role_id INTEGER NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
                        privilege_key TEXT NOT NULL REFERENCES universal_controls(privilege_key) ON DELETE CASCADE,
                        is_enabled INTEGER DEFAULT 1,
                        PRIMARY KEY (role_id, privilege_key)
                    );
                """)

                # 5. End Users & Assigned Roles
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        username TEXT PRIMARY KEY,
                        display_name TEXT,
                        email TEXT,
                        role_id INTEGER NOT NULL REFERENCES roles(id),
                        is_active INTEGER DEFAULT 1,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );
                """)

                # 6. Audit Logs Table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS audit_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        admin_username TEXT NOT NULL,
                        action TEXT NOT NULL,
                        target_type TEXT NOT NULL,
                        target_id TEXT,
                        details TEXT
                    );
                """)

                conn.commit()

                # Seed Default Admin (admin / admin)
                cursor.execute("SELECT id FROM admin_users WHERE username = 'admin'")
                if not cursor.fetchone():
                    admin_hash = bcrypt.hashpw(b"admin", bcrypt.gensalt()).decode("utf-8")
                    now = datetime.now(timezone.utc).isoformat()
                    cursor.execute(
                        """
                        INSERT INTO admin_users (username, password_hash, full_name, role, is_active, created_at)
                        VALUES (?, ?, ?, ?, 1, ?)
                        """,
                        ("admin", admin_hash, "System Administrator", "admin", now),
                    )

                # Seed Universal Controls
                now = datetime.now(timezone.utc).isoformat()
                for priv in CORE_PRIVILEGES:
                    cursor.execute("SELECT privilege_key FROM universal_controls WHERE privilege_key = ?", (priv["key"],))
                    if not cursor.fetchone():
                        cursor.execute(
                            """
                            INSERT INTO universal_controls (privilege_key, name, category, description, is_enabled, updated_at, updated_by)
                            VALUES (?, ?, ?, ?, ?, ?, 'system')
                            """,
                            (priv["key"], priv["name"], priv["category"], priv["description"], priv["default_enabled"], now),
                        )

                # Seed Default Roles and Privileges
                for role_data in DEFAULT_ROLES:
                    cursor.execute("SELECT id FROM roles WHERE name = ?", (role_data["name"],))
                    row = cursor.fetchone()
                    if not row:
                        cursor.execute(
                            """
                            INSERT INTO roles (name, description, is_system, is_active, created_at, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?)
                            """,
                            (role_data["name"], role_data["description"], role_data["is_system"], role_data["is_active"], now, now),
                        )
                        role_id = cursor.lastrowid
                        for priv_key, is_en in role_data["privileges"].items():
                            cursor.execute(
                                """
                                INSERT INTO role_privileges (role_id, privilege_key, is_enabled)
                                VALUES (?, ?, ?)
                                """,
                                (role_id, priv_key, is_en),
                            )

                # Seed standard sample end users if users table is empty
                cursor.execute("SELECT COUNT(*) FROM users")
                if cursor.fetchone()[0] == 0:
                    cursor.execute("SELECT id, name FROM roles")
                    role_map = {r["name"]: r["id"] for r in cursor.fetchall()}

                    sample_users = [
                        ("super_admin", "Super Admin User", "admin@ap.gov.in", role_map.get("Super Admin", 1)),
                        ("analyst", "Senior Analytics Officer", "analyst@ap.gov.in", role_map.get("Data Analyst", 2)),
                        ("officer", "District Collectorate Officer", "officer@ap.gov.in", role_map.get("Department Officer", 3)),
                        ("citizen", "Public Portal Citizen", "citizen@ap.gov.in", role_map.get("Citizen Viewer", 4)),
                        ("test_user", "Integration Test User", "test@ap.gov.in", role_map.get("Data Analyst", 2)),
                    ]

                    for u_name, d_name, email, r_id in sample_users:
                        cursor.execute(
                            """
                            INSERT INTO users (username, display_name, email, role_id, is_active, created_at, updated_at)
                            VALUES (?, ?, ?, ?, 1, ?, ?)
                            """,
                            (u_name, d_name, email, r_id, now, now),
                        )

                conn.commit()

    # =========================================================================
    # Admin Authentication & JWT Security
    # =========================================================================

    def verify_admin_credentials(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """Verify admin login credentials using bcrypt. Returns user dict on success, None on failure."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, username, password_hash, full_name, role, is_active FROM admin_users WHERE username = ?",
                (username.strip(),),
            )
            row = cursor.fetchone()
            if not row:
                return None
            if not row["is_active"]:
                return None

            pw_bytes = password.encode("utf-8")
            hash_bytes = row["password_hash"].encode("utf-8")
            if bcrypt.checkpw(pw_bytes, hash_bytes):
                # Update last login
                now = datetime.now(timezone.utc).isoformat()
                cursor.execute("UPDATE admin_users SET last_login = ? WHERE id = ?", (now, row["id"]))
                conn.commit()
                return {
                    "id": row["id"],
                    "username": row["username"],
                    "full_name": row["full_name"],
                    "role": row["role"],
                }
        return None

    def change_admin_password(self, username: str, old_password: str, new_password: str) -> Tuple[bool, str]:
        """Change admin password securely with verification."""
        user = self.verify_admin_credentials(username, old_password)
        if not user:
            return False, "Current password is incorrect or user is inactive."

        new_hash = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        with self._get_connection() as conn:
            conn.execute("UPDATE admin_users SET password_hash = ? WHERE username = ?", (new_hash, username))
            conn.commit()
            self.log_audit_event(username, "CHANGE_ADMIN_PASSWORD", "admin_users", username, "Password updated successfully")
        return True, "Password updated successfully."

    def create_jwt_token(self, username: str, full_name: Optional[str] = None, role: str = "admin") -> str:
        """Create an HS256 JWT access token with 24-hour expiration."""
        now = datetime.now(timezone.utc)
        payload = {
            "sub": username,
            "name": full_name or username,
            "role": role,
            "iat": now,
            "exp": now + timedelta(hours=JWT_EXPIRATION_HOURS),
        }
        return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

    def verify_jwt_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Validate an admin JWT token. Returns payload dict if valid, None if expired/invalid."""
        try:
            payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
            return payload
        except Exception:
            return None

    # =========================================================================
    # Universal Master Controls (Global Kill-Switch)
    # =========================================================================

    def get_universal_controls(self) -> List[Dict[str, Any]]:
        """Fetch all universal privilege controls with their current states."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT privilege_key, name, category, description, is_enabled, updated_at, updated_by FROM universal_controls ORDER BY category, name"
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_universal_status(self, privilege_key: str) -> bool:
        """Return True if universal control allows this privilege, False if globally restricted."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT is_enabled FROM universal_controls WHERE privilege_key = ?", (privilege_key,))
            row = cursor.fetchone()
            if row is not None:
                return bool(row["is_enabled"])
            return True

    def toggle_universal_control(self, privilege_key: str, is_enabled: bool, admin_username: str = "admin") -> bool:
        """Toggle a universal master control on or off and log the audit trail."""
        now = datetime.now(timezone.utc).isoformat()
        with _lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE universal_controls
                    SET is_enabled = ?, updated_at = ?, updated_by = ?
                    WHERE privilege_key = ?
                    """,
                    (1 if is_enabled else 0, now, admin_username, privilege_key),
                )
                affected = cursor.rowcount
                conn.commit()

        if affected > 0:
            action_desc = "ENABLE_UNIVERSAL_CONTROL" if is_enabled else "DISABLE_UNIVERSAL_CONTROL"
            self.log_audit_event(
                admin_username,
                action_desc,
                "universal_controls",
                privilege_key,
                f"Universal control '{privilege_key}' set to {is_enabled}",
            )
            return True
        return False

    # =========================================================================
    # Roles Management & Privileges Matrix
    # =========================================================================

    def get_roles(self) -> List[Dict[str, Any]]:
        """Return list of all roles with their assigned privileges and assigned user count."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    r.id, r.name, r.description, r.is_system, r.is_active, r.created_at, r.updated_at,
                    COUNT(u.username) AS user_count
                FROM roles r
                LEFT JOIN users u ON u.role_id = r.id
                GROUP BY r.id
                ORDER BY r.is_system DESC, r.id ASC
            """)
            roles_list = []
            for row in cursor.fetchall():
                role_dict = dict(row)
                # Fetch privileges for this role
                cursor.execute(
                    "SELECT privilege_key, is_enabled FROM role_privileges WHERE role_id = ?",
                    (role_dict["id"],),
                )
                role_dict["privileges"] = {p["privilege_key"]: bool(p["is_enabled"]) for p in cursor.fetchall()}
                roles_list.append(role_dict)
            return roles_list

    def get_role(self, role_id: int) -> Optional[Dict[str, Any]]:
        """Get single role details by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, name, description, is_system, is_active, created_at, updated_at FROM roles WHERE id = ?",
                (role_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            role_dict = dict(row)
            cursor.execute(
                "SELECT privilege_key, is_enabled FROM role_privileges WHERE role_id = ?",
                (role_id,),
            )
            role_dict["privileges"] = {p["privilege_key"]: bool(p["is_enabled"]) for p in cursor.fetchall()}
            return role_dict

    def create_role(
        self,
        name: str,
        description: str,
        privileges: Dict[str, bool],
        admin_username: str = "admin",
    ) -> Tuple[bool, str, Optional[int]]:
        """Create a new role with assigned privileges."""
        name = name.strip()
        if not name:
            return False, "Role name cannot be empty.", None

        now = datetime.now(timezone.utc).isoformat()
        with _lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM roles WHERE name = ?", (name,))
                if cursor.fetchone():
                    return False, f"Role with name '{name}' already exists.", None

                cursor.execute(
                    """
                    INSERT INTO roles (name, description, is_system, is_active, created_at, updated_at)
                    VALUES (?, ?, 0, 1, ?, ?)
                    """,
                    (name, description, now, now),
                )
                role_id = cursor.lastrowid

                # Insert privilege mappings
                for priv in CORE_PRIVILEGES:
                    priv_key = priv["key"]
                    is_en = 1 if privileges.get(priv_key, False) else 0
                    cursor.execute(
                        """
                        INSERT INTO role_privileges (role_id, privilege_key, is_enabled)
                        VALUES (?, ?, ?)
                        """,
                        (role_id, priv_key, is_en),
                    )

                conn.commit()

        self.log_audit_event(
            admin_username,
            "CREATE_ROLE",
            "roles",
            str(role_id),
            f"Created role '{name}' with privileges: {privileges}",
        )
        return True, f"Role '{name}' created successfully.", role_id

    def update_role(
        self,
        role_id: int,
        name: str,
        description: str,
        is_active: bool,
        privileges: Dict[str, bool],
        admin_username: str = "admin",
    ) -> Tuple[bool, str]:
        """Update an existing role's metadata and privileges."""
        name = name.strip()
        now = datetime.now(timezone.utc).isoformat()
        with _lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, is_system, name FROM roles WHERE id = ?", (role_id,))
                role = cursor.fetchone()
                if not role:
                    return False, "Role not found."

                # Cannot rename system role
                final_name = role["name"] if role["is_system"] else name
                cursor.execute(
                    """
                    UPDATE roles
                    SET name = ?, description = ?, is_active = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (final_name, description, 1 if is_active else 0, now, role_id),
                )

                # Update privileges
                for priv in CORE_PRIVILEGES:
                    priv_key = priv["key"]
                    if priv_key in privileges:
                        is_en = 1 if privileges[priv_key] else 0
                        cursor.execute(
                            """
                            INSERT INTO role_privileges (role_id, privilege_key, is_enabled)
                            VALUES (?, ?, ?)
                            ON CONFLICT(role_id, privilege_key) DO UPDATE SET is_enabled = ?
                            """,
                            (role_id, priv_key, is_en, is_en),
                        )

                conn.commit()

        self.log_audit_event(
            admin_username,
            "UPDATE_ROLE",
            "roles",
            str(role_id),
            f"Updated role '{final_name}' (active={is_active})",
        )
        return True, f"Role '{final_name}' updated successfully."

    def toggle_role_privilege(
        self, role_id: int, privilege_key: str, is_enabled: bool, admin_username: str = "admin"
    ) -> bool:
        """Toggle an individual privilege in a role."""
        with _lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO role_privileges (role_id, privilege_key, is_enabled)
                    VALUES (?, ?, ?)
                    ON CONFLICT(role_id, privilege_key) DO UPDATE SET is_enabled = ?
                    """,
                    (role_id, privilege_key, 1 if is_enabled else 0, 1 if is_enabled else 0),
                )
                now = datetime.now(timezone.utc).isoformat()
                cursor.execute("UPDATE roles SET updated_at = ? WHERE id = ?", (now, role_id))
                conn.commit()

        self.log_audit_event(
            admin_username,
            "TOGGLE_ROLE_PRIVILEGE",
            "role_privileges",
            f"{role_id}:{privilege_key}",
            f"Role {role_id} privilege '{privilege_key}' set to {is_enabled}",
        )
        return True

    def delete_role(self, role_id: int, admin_username: str = "admin") -> Tuple[bool, str]:
        """Delete a custom role. System roles and roles with assigned users cannot be deleted."""
        with _lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, name, is_system FROM roles WHERE id = ?", (role_id,))
                role = cursor.fetchone()
                if not role:
                    return False, "Role not found."
                if role["is_system"]:
                    return False, f"Role '{role['name']}' is a protected system role and cannot be deleted."

                # Check if any users have this role
                cursor.execute("SELECT COUNT(*) FROM users WHERE role_id = ?", (role_id,))
                user_count = cursor.fetchone()[0]
                if user_count > 0:
                    return False, f"Cannot delete role '{role['name']}' because {user_count} user(s) are assigned to it. Reassign users first."

                cursor.execute("DELETE FROM roles WHERE id = ?", (role_id,))
                conn.commit()

        self.log_audit_event(
            admin_username,
            "DELETE_ROLE",
            "roles",
            str(role_id),
            f"Deleted role '{role['name']}'",
        )
        return True, f"Role '{role['name']}' deleted successfully."

    # =========================================================================
    # Users Management & Role Assignment
    # =========================================================================

    def get_users(self, search: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return list of managed users with their assigned role and effective privileges."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = """
                SELECT 
                    u.username, u.display_name, u.email, u.is_active, u.created_at, u.updated_at,
                    r.id AS role_id, r.name AS role_name, r.is_active AS role_active
                FROM users u
                JOIN roles r ON r.id = u.role_id
            """
            params: List[Any] = []
            if search:
                query += " WHERE u.username LIKE ? OR u.display_name LIKE ? OR u.email LIKE ?"
                like_term = f"%{search.strip()}%"
                params = [like_term, like_term, like_term]

            query += " ORDER BY u.created_at DESC"
            cursor.execute(query, params)

            users_list = []
            for row in cursor.fetchall():
                user_dict = dict(row)
                # Compute effective privileges
                user_dict["effective_privileges"] = self.get_user_effective_privileges(user_dict["username"])
                users_list.append(user_dict)
            return users_list

    def get_user(self, username: str) -> Optional[Dict[str, Any]]:
        """Get single user information by username."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT 
                    u.username, u.display_name, u.email, u.is_active, u.created_at, u.updated_at,
                    r.id AS role_id, r.name AS role_name, r.is_active AS role_active
                FROM users u
                JOIN roles r ON r.id = u.role_id
                WHERE u.username = ?
                """,
                (username,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return dict(row)

    def create_or_update_user(
        self,
        username: str,
        display_name: str,
        email: str,
        role_id: int,
        is_active: bool = True,
        admin_username: str = "admin",
    ) -> Tuple[bool, str]:
        """Create or update an end user and assign their role."""
        username = username.strip()
        if not username:
            return False, "Username cannot be empty."

        now = datetime.now(timezone.utc).isoformat()
        with _lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                # Verify role exists
                cursor.execute("SELECT id, name FROM roles WHERE id = ?", (role_id,))
                role_row = cursor.fetchone()
                if not role_row:
                    return False, f"Role ID {role_id} does not exist."

                cursor.execute(
                    """
                    INSERT INTO users (username, display_name, email, role_id, is_active, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(username) DO UPDATE SET
                        display_name = excluded.display_name,
                        email = excluded.email,
                        role_id = excluded.role_id,
                        is_active = excluded.is_active,
                        updated_at = excluded.updated_at
                    """,
                    (username, display_name, email, role_id, 1 if is_active else 0, now, now),
                )
                conn.commit()

        self.log_audit_event(
            admin_username,
            "UPSERT_USER",
            "users",
            username,
            f"Assigned role '{role_row['name']}' to '{username}' (active={is_active})",
        )
        return True, f"User '{username}' saved successfully."

    def update_user_role(self, username: str, role_id: int, admin_username: str = "admin") -> Tuple[bool, str]:
        """Reassign an existing user to another role."""
        now = datetime.now(timezone.utc).isoformat()
        with _lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM roles WHERE id = ?", (role_id,))
                r_row = cursor.fetchone()
                if not r_row:
                    return False, "Role does not exist."

                cursor.execute(
                    "UPDATE users SET role_id = ?, updated_at = ? WHERE username = ?",
                    (role_id, now, username),
                )
                if cursor.rowcount == 0:
                    return False, f"User '{username}' not found."
                conn.commit()

        self.log_audit_event(
            admin_username,
            "ASSIGN_USER_ROLE",
            "users",
            username,
            f"Reassigned '{username}' to role '{r_row['name']}'",
        )
        return True, f"User '{username}' assigned to '{r_row['name']}'."

    def toggle_user_active(self, username: str, is_active: bool, admin_username: str = "admin") -> Tuple[bool, str]:
        """Activate or suspend a user account."""
        now = datetime.now(timezone.utc).isoformat()
        with _lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE users SET is_active = ?, updated_at = ? WHERE username = ?",
                    (1 if is_active else 0, now, username),
                )
                if cursor.rowcount == 0:
                    return False, f"User '{username}' not found."
                conn.commit()

        action_desc = "ACTIVATE_USER" if is_active else "SUSPEND_USER"
        self.log_audit_event(
            admin_username,
            action_desc,
            "users",
            username,
            f"User '{username}' status set to {'Active' if is_active else 'Suspended'}",
        )
        return True, f"User '{username}' status updated."

    def sync_users_from_chat_history(
        self, chat_history_db_path: Path, default_role_name: str = "Department Officer"
    ) -> int:
        """Scan sessions table in chat_history.db and automatically register any new users into RBAC."""
        if not chat_history_db_path.exists():
            return 0

        synced_count = 0
        try:
            h_conn = sqlite3.connect(str(chat_history_db_path))
            h_cursor = h_conn.cursor()
            h_cursor.execute("SELECT DISTINCT username FROM sessions WHERE username IS NOT NULL AND TRIM(username) != ''")
            session_users = [r[0].strip() for r in h_cursor.fetchall() if r[0]]
            h_conn.close()

            if not session_users:
                return 0

            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM roles WHERE name = ?", (default_role_name,))
                role_row = cursor.fetchone()
                default_role_id = role_row["id"] if role_row else 3

                now = datetime.now(timezone.utc).isoformat()
                for u in session_users:
                    cursor.execute("SELECT username FROM users WHERE username = ?", (u,))
                    if not cursor.fetchone():
                        cursor.execute(
                            """
                            INSERT INTO users (username, display_name, email, role_id, is_active, created_at, updated_at)
                            VALUES (?, ?, ?, ?, 1, ?, ?)
                            """,
                            (u, u.capitalize(), f"{u}@ap.gov.in", default_role_id, now, now),
                        )
                        synced_count += 1
                conn.commit()

            if synced_count > 0:
                self.log_audit_event(
                    "system",
                    "SYNC_USERS_FROM_HISTORY",
                    "users",
                    f"{synced_count} users",
                    f"Auto-discovered and registered {synced_count} user(s) from chat history",
                )
        except Exception as e:
            print(f"[RBAC] Error syncing users from chat history: {e}")

        return synced_count

    # =========================================================================
    # Privilege Resolution Engine & SDUI Synchronization
    # =========================================================================

    def check_user_privilege(self, username: str, privilege_key: str) -> bool:
        """
        Evaluate if a user has access to a specific privilege.
        Hierarchy:
          1. Universal Control (Master Kill-Switch): If disabled universally, ALWAYS False.
          2. User active state: If user is suspended, ALWAYS False.
          3. Role active state: If role is suspended, ALWAYS False.
          4. Role privilege mapping: Returns mapped value.
        """
        # Step 1: Universal Control Check
        if not self.get_universal_status(privilege_key):
            return False

        # Step 2 & 3 & 4: User & Role Resolution
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT 
                    u.is_active AS user_active,
                    r.is_active AS role_active,
                    rp.is_enabled AS priv_enabled
                FROM users u
                JOIN roles r ON r.id = u.role_id
                LEFT JOIN role_privileges rp ON rp.role_id = r.id AND rp.privilege_key = ?
                WHERE u.username = ?
                """,
                (privilege_key, username),
            )
            row = cursor.fetchone()
            if not row:
                # If user is not explicitly registered, fallback to check default viewer permissions
                cursor.execute(
                    """
                    SELECT rp.is_enabled 
                    FROM roles r
                    JOIN role_privileges rp ON rp.role_id = r.id
                    WHERE r.name = 'Citizen Viewer' AND r.is_active = 1 AND rp.privilege_key = ?
                    """,
                    (privilege_key,),
                )
                fallback = cursor.fetchone()
                return bool(fallback["is_enabled"]) if fallback else False

            if not row["user_active"] or not row["role_active"]:
                return False

            return bool(row["priv_enabled"])

    def get_user_effective_privileges(self, username: str) -> Dict[str, bool]:
        """Compute all effective privileges for a user across all core privileges."""
        return {priv["key"]: self.check_user_privilege(username, priv["key"]) for priv in CORE_PRIVILEGES}

    def get_user_sdui_config(self, username: str) -> Dict[str, Any]:
        """
        Construct the complete Server-Driven UI (SDUI) configuration payload
        strictly aligned with Frontend `DEFAULT_SDUI_PRIVILEGES` and `chatbotApi.js`.
        """
        user_info = self.get_user(username)
        effective = self.get_user_effective_privileges(username)

        # Universal control states for telemetry
        universal_states = {p["privilege_key"]: bool(p["is_enabled"]) for p in self.get_universal_controls()}

        role_name = user_info["role_name"] if user_info else "Citizen Viewer"
        is_active = user_info["is_active"] if user_info else True

        return {
            "status": "success",
            "username": username,
            "role": role_name,
            "is_active": is_active,
            # SDUI Gating Flags matching Frontend exactly:
            "isSchemaEnabled": effective.get("schema_layer", False),
            "showAboutSection": effective.get("about_section", False),
            "allowTableExport": effective.get("allow_download", False),
            "allowCsvExport": effective.get("allow_download", False),
            "allowExcelExport": effective.get("allow_download", False),
            "allowCopyTable": effective.get("allow_copy", False),
            "copyProtection": effective.get("content_copy_protection", True),
            "devToolsProtection": effective.get("devtools_protection", True),
            "universal_overrides": universal_states,
        }

    # =========================================================================
    # Audit Logs & Overview Metrics
    # =========================================================================

    def log_audit_event(
        self,
        admin_username: str,
        action: str,
        target_type: str,
        target_id: Optional[str] = None,
        details: Optional[str] = None,
    ) -> None:
        """Record an administrative audit event."""
        now = datetime.now(timezone.utc).isoformat()
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO audit_logs (timestamp, admin_username, action, target_type, target_id, details)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (now, admin_username, action, target_type, target_id or "", details or ""),
                )
                conn.commit()
        except Exception as e:
            print(f"[RBAC Audit Error]: {e}")

    def get_audit_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Retrieve recent audit logs in descending chronological order."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, timestamp, admin_username, action, target_type, target_id, details
                FROM audit_logs
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_dashboard_metrics(self) -> Dict[str, Any]:
        """Aggregate statistical metrics for the dashboard header cards."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM users")
            total_users = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM users WHERE is_active = 1")
            active_users = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM roles")
            total_roles = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM universal_controls WHERE is_enabled = 1")
            active_universal = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM universal_controls")
            total_universal = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM audit_logs")
            total_audits = cursor.fetchone()[0]

            return {
                "total_users": total_users,
                "active_users": active_users,
                "total_roles": total_roles,
                "active_universal": active_universal,
                "total_universal": total_universal,
                "universal_all_green": (active_universal == total_universal),
                "total_audits": total_audits,
            }
