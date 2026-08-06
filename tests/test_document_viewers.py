import re
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = (ROOT / "templates" / "dashboard.html").read_text(encoding="utf-8")
CSS = (ROOT / "static" / "css" / "style.css").read_text(encoding="utf-8")
APP = (ROOT / "app.py").read_text(encoding="utf-8")


def function_source(source, name):
    start = source.index(f"function {name}(")
    end = source.find("\nfunction ", start + 1)
    return source[start:] if end == -1 else source[start:end]


def css_rule(source, selector):
    start = source.index(selector)
    opening = source.index("{", start)
    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start:index + 1]
    raise AssertionError(f"unterminated CSS rule: {selector}")


class DocumentViewerContractTest(unittest.TestCase):
    def test_dashboard_declares_unified_viewer_shell(self):
        for marker in ("openFileViewer", "pdf-viewer", "word-viewer", "cad-viewer"):
            self.assertIn(marker, TEMPLATE)

    def test_each_supported_extension_calls_viewer_in_file_branch(self):
        source = function_source(TEMPLATE, "previewFile")
        for extension in ("pdf", "docx", "stp", "step"):
            branch = re.search(
                rf"if\s*\(\s*ext\s*===\s*['\"]{extension}['\"]\s*\)\s*\{{(?P<body>.*?)\}}\s*else",
                source,
                re.DOTALL,
            )
            self.assertIsNotNone(branch, f"missing previewFile branch for .{extension}")
            self.assertIn("openFileViewer", branch.group("body"))

    def test_each_supported_extension_calls_viewer_in_drawing_branch(self):
        source = function_source(TEMPLATE, "previewDrawing")
        for extension in ("pdf", "docx", "stp", "step"):
            branch = re.search(
                rf"if\s*\(\s*ext\s*===\s*['\"]{extension}['\"]\s*\)\s*\{{(?P<body>.*?)\}}\s*else",
                source,
                re.DOTALL,
            )
            self.assertIsNotNone(branch, f"missing previewDrawing branch for .{extension}")
            self.assertIn("openFileViewer", branch.group("body"))

    def test_doc_has_download_fallback_and_legacy_word_prompt(self):
        source = function_source(TEMPLATE, "previewFile")
        branch = re.search(r"if\s*\(\s*ext\s*===\s*['\"]doc['\"]\s*\)\s*\{(?P<body>.*?)\}\s*else", source, re.DOTALL)
        self.assertIsNotNone(branch, "missing .doc fallback branch")
        self.assertRegex(branch.group("body"), r"download|fallback", re.IGNORECASE)
        self.assertRegex(branch.group("body"), r"旧版.?Word|Word.?暂不支持.?在线预览")

    def test_xt_has_download_fallback_and_unsupported_prompt(self):
        source = function_source(TEMPLATE, "previewDrawing")
        branch = re.search(
            r"(?:if|else if)\s*\([^)]*ext[^)]*(?:xt|x_t|x_b)[^)]*\)\s*\{(?P<body>.*?)\}\s*else",
            source,
            re.IGNORECASE | re.DOTALL,
        )
        self.assertIsNotNone(branch, "missing XT fallback branch")
        self.assertRegex(branch.group("body"), r"download|fallback", re.IGNORECASE)
        self.assertRegex(branch.group("body"), r"不支持.?XT|XT.?格式")

    def test_local_viewer_resource_files_exist_and_are_nonempty(self):
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
            self.assertIn("/" + relative_path.replace("\\", "/"), TEMPLATE)

    def test_runtime_viewer_loading_has_no_external_dependency(self):
        runtime_sources = [TEMPLATE, (ROOT / "static/js/app.js").read_text(encoding="utf-8")]
        viewer_script = ROOT / "static/js/file-viewers.js"
        if viewer_script.exists():
            runtime_sources.append(viewer_script.read_text(encoding="utf-8"))
        runtime = "\n".join(runtime_sources)
        self.assertNotRegex(runtime, r"(?:https?:)?//[^\"'`\s]+", re.IGNORECASE)
        self.assertNotRegex(runtime, r"(?:cdn\.jsdelivr\.net|unpkg\.com|skypack\.dev|esm\.sh)", re.IGNORECASE)
        self.assertNotIn("import(", runtime)
        for match in re.finditer(r"fetch\s*\(\s*([\"'`])([^\"'`]+)\1", runtime):
            self.assertTrue(match.group(2).startswith(("/api/", "/static/")), f"remote fetch dependency: {match.group(2)}")

    def test_viewer_css_mobile_rules_cover_toolbar_container_canvas_and_touch(self):
        for selector in (".file-viewer-modal", ".file-viewer-toolbar", ".pdf-viewer", ".word-viewer", ".cad-viewer"):
            self.assertIn(selector, CSS)
        self.assertRegex(CSS, r"@media\s*\(max-width:\s*768px\)[\s\S]*\.file-viewer-(?:modal|toolbar)")
        for selector in (".file-viewer-modal", ".file-viewer-toolbar", ".pdf-viewer", ".word-viewer", ".cad-viewer"):
            self.assertRegex(css_rule(CSS, selector), r"(?:min-height|height|aspect-ratio)")
        self.assertRegex(css_rule(CSS, ".cad-viewer"), r"overflow\s*:\s*hidden")
        self.assertRegex(css_rule(CSS, ".cad-viewer"), r"touch-action\s*:")
        self.assertRegex(CSS, r"\.cad-viewer\s+canvas[^{}]*\{[^}]*width\s*:\s*100%[^}]*height\s*:\s*100%", re.DOTALL)

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
