import re
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = (ROOT / "templates" / "dashboard.html").read_text(encoding="utf-8")
CSS = (ROOT / "static" / "css" / "style.css").read_text(encoding="utf-8")
APP = (ROOT / "app.py").read_text(encoding="utf-8")


class DocumentViewerContractTest(unittest.TestCase):
    def test_dashboard_declares_unified_viewer_shell(self):
        for marker in ("openFileViewer", "pdf-viewer", "word-viewer", "cad-viewer"):
            self.assertIn(marker, TEMPLATE)

    def test_supported_file_extensions_route_to_unified_viewer(self):
        supported = ("pdf", "docx", "stp", "step")
        self.assertRegex(
            TEMPLATE,
            r"(?:pdf|docx|stp|step).*openFileViewer|openFileViewer.*(?:pdf|docx|stp|step)",
        )
        for extension in supported:
            self.assertRegex(
                TEMPLATE,
                rf"(?:['\"]\.{extension}['\"]|['\"]{extension}['\"]|{extension})",
            )
        self.assertGreaterEqual(TEMPLATE.count("openFileViewer"), 4)

    def test_legacy_doc_and_xt_use_download_fallback(self):
        self.assertRegex(TEMPLATE, r"\.doc|['\"]doc['\"]")
        self.assertRegex(TEMPLATE, r"\.x_t|\.x_b|['\"]xt['\"]|['\"]x_t['\"]|['\"]x_b['\"]")
        self.assertRegex(TEMPLATE, r"(?:doc|x_t|x_b|xt).{0,500}(?:download|fallback)", re.IGNORECASE | re.DOTALL)

    def test_dashboard_uses_only_local_viewer_assets(self):
        asset_paths = (
            "/static/vendor/pdfjs/",
            "/static/vendor/docx-preview/",
            "/static/vendor/three/",
            "/static/vendor/occt-import-js/",
        )
        for asset_path in asset_paths:
            self.assertIn(asset_path, TEMPLATE)

        script_sources = re.findall(r'<script[^>]+src=["\']([^"\']+)', TEMPLATE, re.IGNORECASE)
        viewer_sources = [src for src in script_sources if any(path in src for path in asset_paths)]
        self.assertEqual(len(viewer_sources), 4)
        self.assertTrue(all(src.startswith("/static/") for src in viewer_sources))
        self.assertNotRegex(TEMPLATE, r"(?:https?:)?//[^\"']*(?:pdf|docx|three|occt|viewer)", re.IGNORECASE)

    def test_viewer_css_is_responsive_and_touch_safe(self):
        for selector in (
            ".file-viewer-modal",
            ".file-viewer-toolbar",
            ".pdf-viewer",
            ".word-viewer",
            ".cad-viewer",
        ):
            self.assertIn(selector, CSS)
        self.assertIn("@media (max-width: 768px)", CSS)
        self.assertRegex(CSS, r"\.cad-viewer[^{}]*\{[^}]*overflow:\s*hidden", re.DOTALL)
        self.assertRegex(CSS, r"canvas[^{}]*\{[^}]*max-width:\s*100%", re.DOTALL)
        self.assertIn("touch-action", CSS)
        self.assertIn("aspect-ratio", CSS)

    def test_file_preview_and_download_routes_remain_login_protected(self):
        routes = (
            r"@app\.route\('/api/files/<int:fid>/download'\).*?@login_required",
            r"@app\.route\('/api/files/<int:fid>/preview'\).*?@login_required",
            r"@app\.route\('/api/drawings/<int:did>/download'\).*?@login_required",
            r"@app\.route\('/api/drawings/<int:did>/preview'\).*?@login_required",
        )
        for route in routes:
            self.assertRegex(APP, route, re.DOTALL)

    def test_release_expectations_are_bumped_for_viewers(self):
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        manifest = (ROOT / "android-xinggui" / "app" / "src" / "main" / "AndroidManifest.xml").read_text(encoding="utf-8")
        self.assertEqual(version, "1.0.6")
        self.assertIn('android:versionName="1.0.6"', manifest)
        self.assertIn('android:versionCode="7"', manifest)


if __name__ == "__main__":
    unittest.main()
