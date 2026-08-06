import tempfile
from pathlib import Path
import unittest

import database
from database import close_connection, get_db, init_db


class ProjectDeletionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.tmp.name) / "database.db")
        init_db(self.db_path)

    def tearDown(self):
        close_connection(self.db_path)
        self.tmp.cleanup()

    def test_delete_project_tree_removes_dependent_records(self):
        with get_db(self.db_path) as conn:
            user_id = conn.execute("SELECT id FROM users WHERE username='admin'").fetchone()["id"]
            conn.execute(
                "INSERT INTO projects (project_number, project_name, manager_id) VALUES (?,?,?)",
                ("RD-2608-001", "demo", user_id),
            )
            project_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

            conn.execute(
                "INSERT INTO project_files (project_id, file_name, file_path, uploader_id) VALUES (?,?,?,?)",
                (project_id, "file.pdf", "files/file.pdf", user_id),
            )
            conn.execute(
                "INSERT INTO requirements (project_id, req_id, title, created_by) VALUES (?,?,?,?)",
                (project_id, "REQ-1", "parent", user_id),
            )
            parent_req_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                "INSERT INTO requirements (project_id, req_id, title, parent_req_id, created_by) VALUES (?,?,?,?,?)",
                (project_id, "REQ-2", "child", parent_req_id, user_id),
            )
            child_req_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                "INSERT INTO req_changes (req_id, applicant_id) VALUES (?,?)",
                (parent_req_id, user_id),
            )
            req_change_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

            conn.execute(
                "INSERT INTO drawings (project_id, drawing_number, drawing_name, created_by) VALUES (?,?,?,?)",
                (project_id, "DWG-1", "drawing", user_id),
            )
            drawing_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                "INSERT INTO drawing_ecos (drawing_id, applicant_id) VALUES (?,?)",
                (drawing_id, user_id),
            )
            drawing_eco_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

            conn.execute("INSERT INTO boms (project_id, version) VALUES (?,?)", (project_id, "V1.0"))
            bom_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                "INSERT INTO bom_items (bom_id, name, drawing_id, req_id) VALUES (?,?,?,?)",
                (bom_id, "parent item", drawing_id, child_req_id),
            )
            parent_item_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                "INSERT INTO bom_items (bom_id, parent_item_id, name, drawing_id, req_id) VALUES (?,?,?,?,?)",
                (bom_id, parent_item_id, "child item", drawing_id, parent_req_id),
            )

            for target_type, target_id in (
                ("project", project_id),
                ("requirement", parent_req_id),
                ("req_change", req_change_id),
                ("drawing", drawing_id),
                ("drawing_eco", drawing_eco_id),
                ("bom", bom_id),
            ):
                conn.execute(
                    "INSERT INTO approval_records (target_type, target_id, approver_id, decision) VALUES (?,?,?,?)",
                    (target_type, target_id, user_id, "通过"),
                )

        with get_db(self.db_path) as conn:
            deleted = database.delete_project_tree(conn, project_id)

        self.assertTrue(deleted)
        with get_db(self.db_path) as conn:
            for table in (
                "projects",
                "project_files",
                "requirements",
                "req_changes",
                "drawings",
                "drawing_ecos",
                "boms",
                "bom_items",
                "approval_records",
            ):
                count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                self.assertEqual(count, 0, table)

    def test_project_delete_endpoint_uses_cascade_delete(self):
        app_py = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")
        endpoint = app_py[app_py.index("def api_projects_delete"):app_py.index("@app.route('/api/projects/generate-number'")]

        self.assertIn("delete_project_tree(conn, pid)", endpoint)
        self.assertNotIn('conn.execute("DELETE FROM projects WHERE id=?"', endpoint)


if __name__ == "__main__":
    unittest.main()
