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


def runtime_source():
    sources = [TEMPLATE]
    viewer_script = ROOT / "static/js/file-viewers.js"
    if viewer_script.exists():
        sources.append(viewer_script.read_text(encoding="utf-8"))
    return without_comments("\n".join(sources))


def balanced_block(source, opening):
    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[opening + 1:index]
    raise AssertionError("unbalanced JavaScript/CSS block")


def dispatcher_body(source):
    match = re.search(r"function\s+dispatchFileViewer\s*\([^)]*\)\s*\{", source)
    if not match:
        raise AssertionError("missing dispatchFileViewer function")
    return balanced_block(source, source.find("{", match.start()))


def switch_case(body, extension):
    match = re.search(rf"case\s+['\"]{extension}['\"]\s*:", body, re.IGNORECASE)
    if not match:
        raise AssertionError(f"missing dispatcher case: {extension}")
    end = re.search(r"\bcase\s+['\"]|\bdefault\s*:", body[match.end():], re.IGNORECASE)
    return body[match.end(): match.end() + end.start() if end else len(body)]


def media_blocks(source):
    source = without_comments(source)
    blocks = []
    for match in re.finditer(r"@media\s*\((?P<header>[^)]*max-width[^)]*)\)\s*\{", source, re.IGNORECASE):
        opening = source.find("{", match.start())
        blocks.append((match.group("header"), balanced_block(source, opening)))
    return blocks


def css_rule(block, selector):
    match = re.search(rf"(?m)^[ \t]*{re.escape(selector)}[^{{]*\{{", block)
    if not match:
        raise AssertionError(f"missing CSS rule in media block: {selector}")
    return balanced_block(block, block.find("{", match.start()))


class DocumentViewerContractTest(unittest.TestCase):
    def test_dashboard_declares_unified_viewer_shell(self):
        for marker in ("openFileViewer", "pdf-viewer", "word-viewer", "cad-viewer"):
            self.assertIn(marker, TEMPLATE)

    def test_dispatcher_cases_call_open_file_viewer_for_supported_extensions(self):
        body = dispatcher_body(runtime_source())
        self.assertRegex(body, r"switch\s*\(\s*extension\s*\)")
        for extension in ("pdf", "docx", "stp", "step"):
            self.assertRegex(switch_case(body, extension), r"openFileViewer\s*\(")

    def test_dispatcher_cases_download_legacy_doc_and_xt_with_prompts(self):
        body = dispatcher_body(runtime_source())
        for extension in ("doc", "x_t", "x_b"):
            case = switch_case(body, extension)
            self.assertRegex(case, r"downloadFileViewerSource\s*\(")
            self.assertRegex(case, r"fallback|unsupported|旧版|不支持", re.IGNORECASE)

    def test_local_viewer_assets_exist_and_runtime_references_are_local(self):
        source = runtime_source()
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
        self.assertNotRegex(source, r"https?://", re.IGNORECASE)

    def test_viewer_rules_are_inside_max_width_media_blocks(self):
        blocks = [body for header, body in media_blocks(CSS)]
        self.assertTrue(blocks, "missing max-width media block")
        viewer_blocks = [
            block for block in blocks
            if all(selector in block for selector in (".file-viewer-modal", ".file-viewer-toolbar", ".cad-viewer"))
        ]
        self.assertTrue(viewer_blocks, "viewer rules are not in one max-width media block")
        block = viewer_blocks[0]
        modal = css_rule(block, ".file-viewer-modal")
        toolbar = css_rule(block, ".file-viewer-toolbar")
        cad = css_rule(block, ".cad-viewer")
        canvas = css_rule(block, ".cad-viewer canvas")
        self.assertRegex(modal, r"(?:min-height|height|aspect-ratio)\s*:")
        self.assertRegex(modal, r"overflow\s*:")
        self.assertRegex(toolbar, r"(?:min-height|height)\s*:")
        self.assertRegex(cad, r"overflow\s*:\s*(?:hidden|auto)")
        self.assertRegex(canvas, r"width\s*:\s*100%")
        self.assertRegex(canvas, r"height\s*:\s*100%")
        self.assertRegex(canvas, r"touch-action\s*:")

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
