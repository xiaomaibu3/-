import unittest
from pathlib import Path

import app as project_app

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / 'app.py').read_text(encoding='utf-8')
TEMPLATE = (ROOT / 'templates' / 'dashboard.html').read_text(encoding='utf-8')
JS = (ROOT / 'static' / 'js' / 'app.js').read_text(encoding='utf-8')


class PermissionModelContractTest(unittest.TestCase):
    def test_permission_matrix_and_helpers_exist(self):
        self.assertIn('PERMISSIONS', APP)
        self.assertIn('has_permission', APP)
        self.assertIn('permission_required', APP)
        self.assertIn('管理员', APP)
        self.assertIn('项目经理', APP)
        self.assertIn('普通成员', APP)
        self.assertIn('只读访客', APP)

    def test_permission_matrix_enforces_role_abilities(self):
        self.assertTrue(project_app.has_permission('管理员', 'projects.delete'))
        self.assertTrue(project_app.has_permission('项目管理员', 'projects.delete'))
        self.assertTrue(project_app.has_permission('设计工程师', 'files.upload'))
        self.assertFalse(project_app.has_permission('只读访客', 'projects.delete'))
        self.assertFalse(project_app.has_permission('普通成员', 'settings.edit'))

    def test_sensitive_routes_use_permission_guards(self):
        for token in (
            '@permission_required(',
            'projects.create',
            'projects.edit',
            'projects.delete',
            'files.upload',
            'files.delete',
            'requirements.create',
            'requirements.edit',
            'requirements.delete',
            'drawings.create',
            'drawings.edit',
            'drawings.delete',
            'boms.create',
            'boms.edit',
            'boms.delete',
            'boms.import',
            'boms.export',
            'approvals.act',
            'users.create',
            'users.edit',
            'users.delete',
            'settings.edit',
        ):
            self.assertIn(token, APP)

    def test_dashboard_exposes_current_role_and_permission_hooks(self):
        for token in (
            'session.role',
            'window.APP_CONTEXT',
            'can(',
            'hasPermission(',
            'permission-hidden',
            'data-permission',
            'role-permissions',
        ):
            self.assertIn(token, TEMPLATE + JS)

    def test_user_and_settings_pages_have_permission_hooks(self):
        for token in (
            'showCreateUser',
            'showEditUser',
            'saveSettings',
            'saveApprovalSettings',
            'btn-danger',
            'nav-item',
        ):
            self.assertIn(token, TEMPLATE + JS)

    def test_user_forms_offer_standard_permission_roles(self):
        self.assertIn("const roles = ['管理员', '项目经理', '普通成员', '只读访客'];", TEMPLATE)
        for legacy_role in ('设计工程师', '需求工程师', '文控/质量'):
            self.assertNotIn(legacy_role, TEMPLATE)


if __name__ == '__main__':
    unittest.main()
