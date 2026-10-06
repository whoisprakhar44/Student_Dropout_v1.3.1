# Role-Based Access Control (RBAC) & SDUI Governance Architecture
## AP Citizen 360 NL2SQL Intelligence Platform

> **Version:** 1.5.2 & 1.5.4  
> **Status:** Production Architecture & Specification  
> **Scope:** Enterprise Security, Role-Based Access Control, Universal Master Controls, Server-Driven UI (SDUI) Synchronization, and Dual-Layer API Enforcement.

---

## 1. Executive Summary & Goals

The AP Citizen 360 NL2SQL platform provides natural language access to 38+ tables of government data across citizen identity, welfare schemes, land, property, health, and education. To prevent unauthorized data exposure, control schema visibility, and govern analytical capabilities, this document defines the **Role-Based Access Control (RBAC)** architecture and **Server-Driven UI (SDUI)** contract.

### Core Objectives
1. **Universal Controls (Master Kill-Switch)**: Provide global toggles that allow administrators to instantly enable or disable any feature system-wide in an emergency or during maintenance. When a feature is disabled universally, no user or role can access it, regardless of their individual permissions.
2. **Role & Privilege Hierarchy**: Enable fine-grained role creation with modular privilege bundles, allowing granular privilege toggling, editing, and deletion.
3. **User Management & Role Assignment**: Assign roles to end-users with real-time status control (Active vs. Suspended), with automatic user discovery from chat history sessions.
4. **Dual-Layer Enforcement**:
   - **SDUI Layer**: Broadcasts real-time privilege states to the frontend widget to dynamically show/hide buttons, switch layers, toggle copy protection, and activate devtools guards.
   - **API Enforcement Layer**: Validates user and role privileges directly inside API endpoints (`/ask`, `/api/schema`, `/api/schema/meta`, and WebSocket `/ws/chat`), rejecting unauthorized actions even if the frontend UI is bypassed or manipulated.
5. **Admin Dashboard**: A secure, high-density, dark-first administration portal (`/dashboard`) rendered via Python templates, authenticated using JWT tokens with bcrypt password verification, styled with the official AP Citizen 360 navy and gold design system.

---

## 2. Privilege Matrix & Definitions

The system governs **6 Core Privileges** across the application:

| Privilege Key | Display Name | Category | Description | Default Universal State |
|---|---|---|---|:---:|
| `schema_layer` | Schema Layer Access | Data Access | Controls access to switch between Curated and Schema Chat mode and query underlying schema tables. | **Enabled** (`1`) |
| `about_section` | About & Canonical Reference | Documentation | Controls visibility and API access to canonical schema metadata, entity definitions, and data dictionary. | **Enabled** (`1`) |
| `allow_download` | Data Export (CSV & Excel) | Data Export | Allows downloading query results and data tables as CSV or Excel (.xlsx) files. | **Enabled** (`1`) |
| `allow_copy` | Copy Results & SQL | Clipboard | Allows users to copy tabular data, SQL statements, and AI answers to their clipboard. | **Enabled** (`1`) |
| `content_copy_protection` | Content Protection | Security Guard | Enforces frontend selection blocking, right-click context menu lock, and text copy suppression. | **Enabled** (`1`) |
| `devtools_protection` | DevTools Guard | Security Guard | Detects and blocks browser developer console shortcuts (`F12`, `Ctrl+Shift+I`, `Ctrl+U`). | **Enabled** (`1`) |

---

## 3. Hierarchy & Permission Evaluation Engine

Permission evaluation follows a strict **fail-safe hierarchical pipeline**:

```
                  ┌─────────────────────────────────────┐
                  │    Incoming Request / SDUI Fetch    │
                  │        (username, privilege)        │
                  └──────────────────┬──────────────────┘
                                     │
                                     ▼
                  ┌─────────────────────────────────────┐
                  │   1. Universal Control Active?      │
                  │      (Global Master Kill-Switch)    │
                  └──────────┬──────────────────────────┘
                             │
                     No ─────┴───── Yes
                     │              │
                     ▼              ▼
           ┌────────────────┐ ┌─────────────────────────────────────┐
           │ DENIED / FALSE │ │      2. User Exists & Active?       │
           └────────────────┘ └──────────────┬──────────────────────┘
                                             │
                                     No ─────┴───── Yes
                                     │              │
                                     ▼              ▼
                           ┌────────────────┐ ┌─────────────────────────────────────┐
                           │ DENIED / FALSE │ │      3. Role Exists & Active?       │
                           └────────────────┘ └──────────────┬──────────────────────┘
                                                             │
                                                     No ─────┴───── Yes
                                                     │              │
                                                     ▼              ▼
                                           ┌────────────────┐ ┌─────────────────────────────────────┐
                                           │ DENIED / FALSE │ │ 4. Role Has Privilege Enabled?      │
                                           └────────────────┘ └──────────────┬──────────────────────┘
                                                                             │
                                                                     No ─────┴───── Yes
                                                                     │              │
                                                                     ▼              ▼
                                                           ┌────────────────┐ ┌───────────────────┐
                                                           │ DENIED / FALSE │ │  GRANTED / TRUE   │
                                                           └────────────────┘ └───────────────────┘
```

### Mathematical Formulation
For any user $U$, role $R = \text{Role}(U)$, and privilege $P$:

$$\text{EffectivePrivilege}(U, P) = \text{UniversalControl}(P) \land \text{IsActive}(U) \land \text{IsActive}(R) \land \text{RolePrivilege}(R, P)$$

> [!IMPORTANT]
> If $\text{UniversalControl}(P) = \text{False}$, then $\text{EffectivePrivilege}(U, P) = \text{False}$ **under all circumstances**, even for Super Admins. This guarantees immediate incident containment across production.

---

## 4. Default Seeded Roles

The database is pre-seeded with 4 standard roles:

| Role Name | System Role | Schema Layer | About Section | Allow Download | Allow Copy | Content Protection | DevTools Protection | Intended Audience |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|---|
| **Super Admin** | Yes (Locked) |  Yes |  Yes |  Yes |  Yes | ❌ No | ❌ No | Lead Data Engineers & DBAs |
| **Data Analyst** | No |  Yes |  Yes |  Yes |  Yes | ❌ No | ❌ No | Analytics & BI teams |
| **Department Officer** | No | ❌ No |  Yes |  Yes |  Yes |  Yes |  Yes | Secretariat & District Officers |
| **Citizen Viewer** | No | ❌ No | ❌ No | ❌ No | ❌ No |  Yes |  Yes | Public or unauthenticated users |

---

## 5. Server-Driven UI (SDUI) Contract

The frontend chat widget queries SDUI settings upon initialization:
- **HTTP**: `POST /ask` with `action: "sdui_config"` or `GET /api/sdui/config?username=...`
- **WebSocket**: Action frame `ws_sdui_config`

### JSON Response Payload
```json
{
  "status": "success",
  "username": "analyst_john",
  "role": "Data Analyst",
  "is_active": true,
  "isSchemaEnabled": true,
  "showAboutSection": true,
  "allowTableExport": true,
  "allowCsvExport": true,
  "allowExcelExport": true,
  "allowCopyTable": true,
  "copyProtection": false,
  "devToolsProtection": false,
  "universal_overrides": {
    "schema_layer": true,
    "about_section": true,
    "allow_download": true,
    "allow_copy": true,
    "content_copy_protection": true,
    "devtools_protection": true
  }
}
```

---

## 6. Backend API-Level Enforcement

In addition to frontend SDUI rendering restrictions, the backend strictly intercepts and enforces privilege checks:

1. **User Active Check**:
   - If a user or their assigned role is suspended/inactive, all `/ask` requests and `/ws/chat` messages are immediately rejected with `403 Forbidden` (`status: "forbidden"`).
2. **Schema Layer Enforcement**:
   - If a user sends a query with `layer: "schema"` or requests schema table DDLs while `schema_layer` is disabled, the agent rejects query execution and returns:
     ```json
     {
       "sql": "",
       "result": [{ "error": "Access Denied: Schema layer querying is restricted for your role.", "status": "forbidden" }],
       "summary": "I cannot query the schema layer because your account or role does not have permission.",
       "username": "citizen_user"
     }
     ```
3. **About Section & Canonical Schema Enforcement**:
   - Endpoints `GET /api/schema`, `GET /api/schema/meta`, and `/ask` actions `schema`, `canonical_schema`, `schema_meta`, `about_schema`, `about_meta` check `EffectivePrivilege(username, 'about_section')`.
   - If restricted, returns `403 Forbidden` with `"Access Denied: Canonical Schema and About documentation is restricted."`
4. **Data Export & Download Enforcement**:
   - If `allow_download` is restricted, any export action is rejected on the API level.

---

## 7. Database Architecture (`database/rbac.db`)

All RBAC tables are stored in `database/rbac.db` using SQLite with WAL (Write-Ahead Logging) for high concurrency and isolation from vector databases and chat history.

### Relational Schema

```sql
-- Admin Users for Dashboard Login
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

-- Universal Controls (Master Kill-Switch)
CREATE TABLE IF NOT EXISTS universal_controls (
    privilege_key TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    description TEXT,
    is_enabled INTEGER DEFAULT 1,
    updated_at TEXT NOT NULL,
    updated_by TEXT DEFAULT 'admin'
);

-- Defined Roles
CREATE TABLE IF NOT EXISTS roles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    is_system INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Role Privileges Mapping
CREATE TABLE IF NOT EXISTS role_privileges (
    role_id INTEGER NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    privilege_key TEXT NOT NULL REFERENCES universal_controls(privilege_key) ON DELETE CASCADE,
    is_enabled INTEGER DEFAULT 1,
    PRIMARY KEY (role_id, privilege_key)
);

-- End Users & Role Assignments
CREATE TABLE IF NOT EXISTS users (
    username TEXT PRIMARY KEY,
    display_name TEXT,
    email TEXT,
    role_id INTEGER NOT NULL REFERENCES roles(id),
    is_active INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Administrative Audit Logs
CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    admin_username TEXT NOT NULL,
    action TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT,
    details TEXT
);
```

---

## 8. Admin Security & Authentication

- **Initial Admin Credentials**: Username: `admin`, Password: `admin` (pre-hashed with `bcrypt`).
- **Session Security**: Authenticated sessions issue an `admin_access_token` signed with `HS256` and stored in an `HttpOnly`, `SameSite=Lax` cookie with an expiration of 24 hours.
- **Protected Paths**: All `/dashboard` routes (except `/dashboard/login`) and all `/api/admin/*` endpoints strictly require a valid JWT token.
- **Audit Trail**: Every administrative action (toggling a universal control, creating/editing a role, reassigning a user, deleting a role) is immutably logged into `audit_logs`.

---

## 9. Visual Design System

The Admin Dashboard is built upon the **AP Citizen 360 Official Design Language** and adheres to the `frontend-dashboard` skill guidelines:
- **Dark Mode Palette**: Deep Navy background (`#09090b` / `#0b0f19`), Surface Card (`#111827`), Dark Border (`#1f2937`), Accent Navy (`#0b2545`), Gold Accent (`#d97706`), Gold Glow (`#f59e0b`), Emerald Success (`#15803d`).
- **Light Mode Palette**: Canvas (`#f8fafc`), Card (`#ffffff`), Border (`#cbd5e1`), Primary text (`#0f172a`), Muted text (`#475569`).
- **Zero-Dependency Architecture**: Embedded SVGs, modern Vanilla CSS variables, and native JavaScript for instantaneous rendering and complete offline functionality on enterprise RHEL/CentOS intranet servers.

---

## 10. Reverse Proxy & Subpath Deployment Architecture (`APP_SUBPATH`)

When deployed behind enterprise reverse proxies (such as NGINX, Traefik, HAProxy, AWS ALB, or Kubernetes Ingress) where subpath rewriting/routing is configured:

```
External User Request:   https://domain.com/some_path/dashboard
Reverse Proxy Mapping:   http://localhost:8001/dashboard  (proxied to local port)
```

### 10.1 The Subpath Routing Problem
When the application is mapped to a subpath like `/some_path/`:
1. **Server Redirects**: Standard FastAPI redirects like `RedirectResponse(url="/dashboard/login?next=/dashboard")` instruct the browser to navigate to `https://domain.com/dashboard/login`, stripping the reverse-proxy `/some_path/` prefix and resulting in 404 Not Found errors or infinite login loops.
2. **Client Fetch Calls**: Hardcoded frontend calls like `fetch('/api/admin/roles')` or `fetch('/dashboard/login')` hit the domain root `https://domain.com/api/...`, bypassing the proxy route.
3. **Form Submissions**: Hardcoded `<form action="/dashboard/login">` bypasses the subpath prefix on submission.

### 10.2 Dual-Layer Adaptive Solution

The platform implements a comprehensive dual-layer subpath adaptation architecture:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        Incoming HTTP Request                           │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
         ┌──────────────────────────┴──────────────────────────┐
         ▼                                                     ▼
┌─────────────────────────────────┐           ┌──────────────────────────────────┐
│  1. Server-Side Normalization   │           │ 2. Template Injection & Client   │
│  - APP_SUBPATH / BASE_PATH env  │           │    Autonomous Detection          │
│  - X-Forwarded-Prefix fallback  │           │ - window.__BASE_PATH__ injected  │
│  - FastAPI root_path configured │           │ - Dynamic fallback from pathname │
│  - RedirectResponse rewritten   │           │ - All fetch & form URLs prefixed │
└─────────────────────────────────┘           └──────────────────────────────────┘
```

1. **Server-Side Subpath Normalization (`get_base_path`)**:
   - Reads environment variables `APP_SUBPATH`, `BASE_PATH`, `ROOT_PATH`, or `SUBPATH`.
   - If not set in `.env`, automatically inspects the standard `X-Forwarded-Prefix` HTTP header and ASGI `root_path`.
   - Guarantees normalized format: `/some_path` (leading slash, no trailing slash, or `""` for root).
   - FastAPI is initialized with `root_path=get_base_path()`.
   - All server-side redirects dynamically prepend `base_path`:
     - `RedirectResponse(url=f"{base_path}/dashboard/login?next={base_path}/dashboard", status_code=302)`
     - `RedirectResponse(url=f"{base_path}/dashboard", status_code=302)`
     - `RedirectResponse(url=f"{base_path}/dashboard/login", status_code=302)`

2. **Template Injection (`render_template_with_base_path`)**:
   - Replaces all `{{BASE_PATH}}` tokens in HTML templates.
   - Automatically injects `<script>window.__BASE_PATH__ = '{base_path}';</script>` into the `<head>` of all rendered pages (`dashboard.html`, `dashboard_login.html`, `index.html`, `logs.html`, `logs_login.html`).

3. **Autonomous Client-Side Resolution (`getBasePath`)**:
   - Every template implements `getBasePath()`:
     ```javascript
     const getBasePath = () => {
       if (typeof window.__BASE_PATH__ === 'string') {
         return window.__BASE_PATH__.replace(/\/+$/, '');
       }
       const pathname = window.location.pathname;
       const idx = pathname.indexOf('/dashboard');
       if (idx > 0) {
         return pathname.substring(0, idx).replace(/\/+$/, '');
       }
       return '';
     };
     const BASE_PATH = getBasePath();
     ```
   - All AJAX/Fetch calls, form submissions, and redirects prepend `${BASE_PATH}`:
     - `fetch(`${BASE_PATH}/api/admin/overview`)`
     - `fetch(`${BASE_PATH}/dashboard/login`)`
     - `fetch(`${BASE_PATH}/ask`, ...)`
     - `<form id="loginForm" method="POST" action="">` (empty action posts to current URL preserving subpath)
     - `window.location.href = `${BASE_PATH}/dashboard/login``

