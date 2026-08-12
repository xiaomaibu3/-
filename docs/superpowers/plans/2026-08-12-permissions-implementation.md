# 用户权限实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为系统补齐“角色 + 功能权限”控制，让菜单、按钮和后端接口都按管理员、项目经理、普通成员、只读访客四类角色一致生效。

**Architecture:** 以现有 `session.role` 和数据库 `users.role` 为基础，新增一层统一权限定义，后端用装饰器/检查函数拦截写操作和敏感读取，前端根据同一份权限定义渲染菜单与动作按钮。权限规则默认内置在代码中，先做稳定的矩阵控制，不引入可编辑权限后台，保证实现小而稳。

**Tech Stack:** Flask, SQLite, Jinja2, vanilla JavaScript, CSS, unittest.

---

### Task 1: 定义权限模型和后端检查入口

**Files:**
- Modify: `app.py`
- Modify: `database.py`（如需补充默认角色说明）
- Test: `tests/test_permissions.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
app_py = (ROOT / "app.py").read_text(encoding="utf-8")

def test_permission_helpers_and_role_names_exist():
    assert "PERMISSIONS" in app_py
    assert "has_permission" in app_py
    assert "permission_required" in app_py
    assert "管理员" in app_py
    assert "项目经理" in app_py
    assert "普通成员" in app_py
    assert "只读访客" in app_py
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_permissions -v`

Expected: FAIL because the permission map and helpers do not exist yet.

- [ ] **Step 3: Write minimal implementation**

Add a centralized permission map in `app.py`, for example:

```python
PERMISSIONS = {
    '管理员': {'dashboard.view', 'projects.view', 'projects.create', 'projects.edit', 'projects.delete', 'files.view', 'files.upload', 'files.download', 'files.preview', 'requirements.view', 'requirements.create', 'requirements.edit', 'requirements.delete', 'drawings.view', 'drawings.create', 'drawings.edit', 'drawings.delete', 'boms.view', 'boms.create', 'boms.edit', 'boms.delete', 'approvals.view', 'approvals.act', 'users.view', 'users.create', 'users.edit', 'users.delete', 'settings.view', 'settings.edit', 'audit.view'},
    '项目经理': {...},
    '普通成员': {...},
    '只读访客': {'dashboard.view', 'projects.view', 'files.view', 'files.preview', 'requirements.view', 'drawings.view', 'boms.view', 'approvals.view', 'audit.view'},
}

def has_permission(role, permission):
    return permission in PERMISSIONS.get(role, set())

def permission_required(permission):
    ...
```

Use this helper in route guards without removing existing `login_required`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_permissions -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app.py database.py tests/test_permissions.py
git commit -m "feat: add permission model"
```

### Task 2: Protect sensitive API routes with permissions

**Files:**
- Modify: `app.py`
- Test: `tests/test_permissions.py`

- [ ] **Step 1: Extend the failing tests**

Add assertions that route source contains permission guards around:
`/api/projects` write routes, `/api/files/<fid>/delete`, `/api/users`, `/api/requirements`, `/api/drawings`, `/api/boms`, `/api/approvals`, `/api/settings/config`, `/api/settings/backup`, `/api/settings/restore`, `/api/approval-flows`.

- [ ] **Step 2: Run the focused test and confirm it fails**

Run: `python -m unittest tests.test_permissions -v`

Expected: FAIL until route guards are added.

- [ ] **Step 3: Implement route guards**

Apply `@permission_required(...)` to the sensitive routes, for example:
- project create/edit/delete -> `projects.create`, `projects.edit`, `projects.delete`
- file upload/delete -> `files.upload`, `files.delete`
- requirements CRUD -> `requirements.create`, `requirements.edit`, `requirements.delete`
- drawings CRUD -> `drawings.create`, `drawings.edit`, `drawings.delete`
- BOM CRUD/import/export -> `boms.create`, `boms.edit`, `boms.delete`, `boms.import`, `boms.export`
- approvals action -> `approvals.act`
- users CRUD -> `users.create`, `users.edit`, `users.delete`
- settings/config/backup/restore/approval-flows -> `settings.edit`

- [ ] **Step 4: Re-run the test**

Run: `python -m unittest tests.test_permissions -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app.py tests/test_permissions.py
git commit -m "feat: guard sensitive routes by permission"
```

### Task 3: Render menus and action buttons by role on the frontend

**Files:**
- Modify: `templates/dashboard.html`
- Modify: `static/js/app.js`
- Modify: `static/css/style.css`
- Test: `tests/test_permissions.py`

- [ ] **Step 1: Write the failing DOM contract tests**

Add tests that assert the dashboard template exposes the current role to JS, and that the UI includes permission-aware hooks such as hidden/disabled action groups for user management, system settings, delete buttons, and create buttons.

- [ ] **Step 2: Run tests and verify they fail**

Run: `python -m unittest tests.test_permissions -v`

Expected: FAIL until the frontend reads role permissions.

- [ ] **Step 3: Implement frontend permission wiring**

In `dashboard.html`, expose a compact `window.APP_PERMISSIONS` or `data-role` payload.
In `app.js`, add helper functions like `can(permission)` and hide/disable nav items and action buttons based on role permissions.
In `style.css`, add styles for disabled actions and permission-hidden sections.

- [ ] **Step 4: Re-run the tests**

Run: `python -m unittest tests.test_permissions -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add templates/dashboard.html static/js/app.js static/css/style.css tests/test_permissions.py
git commit -m "feat: hide UI by permission"
```

### Task 4: Add role visibility and permission summary in system settings

**Files:**
- Modify: `static/js/app.js`
- Modify: `templates/dashboard.html`
- Modify: `app.py`

- [ ] **Step 1: Add a small test for role summary output**

Assert the settings page shows current role, allowed actions, and denied actions.

- [ ] **Step 2: Implement the summary panel**

Render a permissions summary panel on the settings page so admins can quickly confirm what each role can do.

- [ ] **Step 3: Verify manually with existing tests**

Run: `python -m unittest discover -s tests -v`

Expected: existing suite still passes.

- [ ] **Step 4: Commit**

```bash
git add app.py templates/dashboard.html static/js/app.js tests/test_permissions.py
git commit -m "feat: show role permission summary"
```

### Task 5: Verify release behavior and clean up

**Files:**
- Modify: `tests/test_permissions.py`
- Possibly modify: `tests/test_xinggui_mobile_app.py`

- [ ] **Step 1: Run the full test suite**

Run: `python -m unittest discover -s tests -v`

Expected: PASS.

- [ ] **Step 2: Check diff hygiene**

Run: `git diff --check`

Expected: no whitespace errors.

- [ ] **Step 3: Review role coverage**

Confirm administrator, project manager, regular member, and read-only visitor all map to distinct visible UI and API abilities.

- [ ] **Step 4: Commit final adjustments**

```bash
git add .
git commit -m "feat: complete role permission controls"
```
