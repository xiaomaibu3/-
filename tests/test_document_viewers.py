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


def viewer_dispatch_fragments(source):
    fragments = []
    function_start = re.compile(
        r"(?:function\s+\w+\s*\([^)]*\)|(?:const|let|var)\s+\w+\s*=\s*(?:async\s*)?(?:\([^)]*\)|\w+)\s*=>)\s*\{",
        re.IGNORECASE,
    )
    for match in function_start.finditer(source):
        fragments.append(balanced_block(source, source.find("{", match.start())))
    # Also recognize concise object-map entries without requiring a map name.
    fragments.extend(re.findall(
        r"(?:['\"]?\w+['\"]?\s*:\s*(?:async\s*)?(?:\([^)]*\)|\w+)\s*=>\s*[^,}\n]*openFileViewer\s*\([^,}\n]*\))",
        source,
        re.IGNORECASE,
    ))
    return fragments


def extension_dispatch_fragment(source, extension):
    fragments = viewer_dispatch_fragments(source)
    for fragment in fragments:
        if re.search(rf"['\"]\.?{extension}['\"]", fragment, re.IGNORECASE) and re.search(r"openFileViewer\s*\(", fragment):
            return fragment
    raise AssertionError(f"no direct viewer dispatch fragment for .{extension}")


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
        source = runtime_source()
        for extension in ("pdf", "docx", "stp", "step"):
            extension_dispatch_fragment(source, extension)

    def test_dispatcher_cases_download_legacy_doc_and_xt_with_prompts(self):
        source = runtime_source()
        for extension in ("doc", "x_t", "x_b"):
            case = extension_dispatch_fragment(source, extension)
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
        selectors = (".file-viewer-modal", ".file-viewer-toolbar", ".pdf-viewer", ".word-viewer", ".cad-viewer")
        rules = {}
        for selector in selectors:
            matching_blocks = [block for block in blocks if selector in block]
            self.assertTrue(matching_blocks, f"{selector} is not in a max-width media block")
            rules[selector] = css_rule(matching_blocks[0], selector)
        cad_blocks = [block for block in blocks if ".cad-viewer canvas" in block]
        self.assertTrue(cad_blocks, ".cad-viewer canvas is not in a max-width media block")
        canvas = css_rule(cad_blocks[0], ".cad-viewer canvas")
        modal = rules[".file-viewer-modal"]
        toolbar = rules[".file-viewer-toolbar"]
        pdf = rules[".pdf-viewer"]
        word = rules[".word-viewer"]
        cad = rules[".cad-viewer"]
        self.assertRegex(modal, r"(?:min-height|height|aspect-ratio)\s*:")
        self.assertRegex(modal, r"overflow\s*:")
        self.assertRegex(toolbar, r"(?:min-height|height)\s*:")
        self.assertRegex(pdf, r"(?:min-height|height|aspect-ratio)\s*:")
        self.assertRegex(pdf, r"overflow\s*:")
        self.assertRegex(word, r"(?:min-height|height|aspect-ratio)\s*:")
        self.assertRegex(word, r"overflow\s*:")
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
