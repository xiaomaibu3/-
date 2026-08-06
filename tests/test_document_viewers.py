import re
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = (ROOT / "templates" / "dashboard.html").read_text(encoding="utf-8")
CSS = (ROOT / "static" / "css" / "style.css").read_text(encoding="utf-8")
APP = (ROOT / "app.py").read_text(encoding="utf-8")


def without_comments(source):
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)
    return re.sub(r"(^|\s)//[^\r\n]*", r"\1", source)


def runtime_sources():
    sources = [TEMPLATE, (ROOT / "static/js/app.js").read_text(encoding="utf-8")]
    viewer_script = ROOT / "static/js/file-viewers.js"
    if viewer_script.exists():
        sources.append(viewer_script.read_text(encoding="utf-8"))
    return "\n".join(without_comments(source) for source in sources)


def media_blocks(source):
    source = without_comments(source)
    blocks = []
    for match in re.finditer(r"@media\s*\([^)]*\)\s*\{", source):
        opening = source.find("{", match.start())
        depth = 0
        for index in range(opening, len(source)):
            if source[index] == "{":
                depth += 1
            elif source[index] == "}":
                depth -= 1
                if depth == 0:
                    blocks.append(source[match.start():index + 1])
                    break
    return blocks


class DocumentViewerContractTest(unittest.TestCase):
    def test_dashboard_declares_unified_viewer_shell(self):
        for marker in ("openFileViewer", "pdf-viewer", "word-viewer", "cad-viewer"):
            self.assertIn(marker, TEMPLATE)

    def test_each_supported_extension_is_near_a_real_viewer_call(self):
        source = runtime_sources()
        for extension in ("pdf", "docx", "stp", "step"):
            matches = list(re.finditer(rf"['\"]\.?{extension}['\"]", source, re.IGNORECASE))
            self.assertTrue(matches, f"missing supported extension: {extension}")
            self.assertTrue(
                any(
                    re.search(
                        r"openFileViewer\s*\(",
                        source[max(0, match.start() - 800):min(len(source), match.end() + 800)],
                    )
                    for match in matches
                ),
                f".{extension} is not routed to openFileViewer(",
            )

    def test_doc_has_explicit_fallback_and_real_download_entry(self):
        source = runtime_sources()
        self._assert_fallback_download(source, r"['\"]\.?doc['\"]", ".doc")

    def test_x_t_has_explicit_fallback_and_real_download_entry(self):
        self._assert_cad_fallback_download("x_t")

    def test_x_b_has_explicit_fallback_and_real_download_entry(self):
        self._assert_cad_fallback_download("x_b")

    def _assert_cad_fallback_download(self, extension):
        source = runtime_sources()
        self._assert_fallback_download(source, rf"['\"]\.?{extension}['\"]", f".{extension}")

    def _assert_fallback_download(self, source, extension_pattern, label):
        matches = list(re.finditer(extension_pattern, source, re.IGNORECASE))
        self.assertTrue(matches, f"missing {label} handling")
        fallback = r"fallback|unsupported|downloadFileViewerSource\s*\(|/download|\.download"
        download = r"downloadFileViewerSource\s*\(|/api/(?:files|drawings)/[^\s`'\"]+/download|href\s*=|location\.(?:href|assign)"
        self.assertTrue(
            any(re.search(fallback, source[max(0, match.start() - 1000):match.end() + 1000], re.IGNORECASE) for match in matches),
            f"missing explicit fallback for {label}",
        )
        self.assertTrue(
            any(re.search(download, source[max(0, match.start() - 1000):match.end() + 1000], re.IGNORECASE) for match in matches),
            f"missing real download entry for {label}",
        )

    def test_local_viewer_assets_exist_and_are_referenced_by_runtime(self):
        source = runtime_sources()
        paths = (
            "static/vendor/pdfjs/pdf.mjs",
            "static/vendor/pdfjs/pdf.worker.mjs",
            "static/vendor/docx-preview/docx-preview.min.js",
            "static/vendor/three/three.module.min.js",
            "static/vendor/three/examples/jsm/controls/OrbitControls.js",
            "static/vendor/occt-import-js/occt-import-js.js",
            "static/vendor/occt-import-js/occt-import-js.wasm",
        )
        for relative_path in paths:
            asset = ROOT / relative_path
            self.assertTrue(asset.is_file(), f"missing local viewer asset: {relative_path}")
            self.assertGreater(asset.stat().st_size, 0, f"empty local viewer asset: {relative_path}")
            self.assertIn("/" + relative_path.replace("\\", "/"), source)

    def test_runtime_viewer_loading_allows_local_import_but_has_no_external_dependency(self):
        source = runtime_sources()
        self.assertNotRegex(source, r"https?://", re.IGNORECASE)
        self.assertNotRegex(source, r"(?:cdn\.jsdelivr\.net|unpkg\.com|skypack\.dev|esm\.sh)", re.IGNORECASE)
        for match in re.finditer(r"(?:import|fetch)\s*\(\s*([\"'`])([^\"'`]+)\1", source):
            self.assertFalse(match.group(2).lower().startswith(("http://", "https://")), match.group(2))

    def test_viewer_rules_are_inside_mobile_media_blocks(self):
        blocks = media_blocks(CSS)
        self.assertTrue(blocks, "missing CSS media blocks")
        viewer_blocks = [
            block for block in blocks
            if any(selector in block for selector in (".file-viewer-modal", ".file-viewer-toolbar", ".pdf-viewer", ".word-viewer", ".cad-viewer"))
        ]
        self.assertTrue(viewer_blocks, "viewer rules are not inside a media block")
        mobile_css = "\n".join(viewer_blocks)
        for selector in (".file-viewer-modal", ".file-viewer-toolbar", ".pdf-viewer", ".word-viewer", ".cad-viewer"):
            self.assertIn(selector, mobile_css)
        self.assertRegex(mobile_css, r"(?:min-height|height|aspect-ratio)\s*:")
        self.assertRegex(mobile_css, r"overflow\s*:\s*(?:hidden|auto)")
        self.assertRegex(mobile_css, r"canvas[^{}]*\{[^}]*width\s*:\s*100%", re.DOTALL)
        self.assertRegex(mobile_css, r"touch-action\s*:")

    def test_each_file_preview_download_route_has_adjacent_login_decorator(self):
        lines = APP.splitlines()
        routes = (
            "/api/files/<int:fid>/download",
            "/api/files/<int:fid>/preview",
            "/api/drawings/<int:did>/download",
            "/api/drawings/<int:did>/preview",
        )
        for route in routes:
            route_line = next((index for index, line in enumerate(lines) if f"@app.route('{route}')" in line), None)
            self.assertIsNotNone(route_line, f"missing route: {route}")
            self.assertEqual(lines[route_line + 1].strip(), "@login_required", f"route is not protected: {route}")

    def test_release_expectations_are_bumped_for_viewers(self):
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        manifest = (ROOT / "android-xinggui" / "app" / "src" / "main" / "AndroidManifest.xml").read_text(encoding="utf-8")
        self.assertEqual(version, "1.0.6")
        self.assertIn('android:versionName="1.0.6"', manifest)
        self.assertIn('android:versionCode="7"', manifest)


if __name__ == "__main__":
    unittest.main()
