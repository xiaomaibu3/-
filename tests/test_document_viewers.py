import os
from html.parser import HTMLParser
from pathlib import Path
import re
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = (ROOT / "templates" / "dashboard.html").read_text(encoding="utf-8")
CSS = (ROOT / "static" / "css" / "style.css").read_text(encoding="utf-8")
APP = (ROOT / "app.py").read_text(encoding="utf-8")


def node_executable():
    candidates = [os.environ.get("NODE_EXE"), shutil.which("node")]
    bundled = Path.home() / ".cache" / "codex-runtimes" / "codex-primary-runtime" / "dependencies" / "node" / "bin" / "node.exe"
    candidates.append(str(bundled))
    return next((Path(value) for value in candidates if value and Path(value).is_file()), None)


class DashboardParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.elements = []
        self.scripts = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        self.elements.append((tag, attributes))
        if tag == "script":
            self.scripts.append(attributes)


def strip_css_comments(source):
    return re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)


def strip_javascript_comments(source):
    result = []
    index = 0
    quote = None
    while index < len(source):
        char = source[index]
        following = source[index + 1] if index + 1 < len(source) else ""
        if quote:
            result.append(char)
            if char == "\\" and following:
                result.append(following)
                index += 2
                continue
            if char == quote:
                quote = None
        elif char in "\"'`":
            quote = char
            result.append(char)
        elif char == "/" and following == "*":
            end = source.find("*/", index + 2)
            index = len(source) if end < 0 else end + 2
            continue
        elif char == "/" and following == "/":
            end = source.find("\n", index + 2)
            index = len(source) if end < 0 else end
            continue
        else:
            result.append(char)
        index += 1
    return "".join(result)


def matching_brace(source, opening):
    depth = 0
    quote = None
    index = opening
    while index < len(source):
        char = source[index]
        if quote:
            if char == "\\":
                index += 2
                continue
            if char == quote:
                quote = None
        elif char in "\"'":
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[opening + 1:index]
        index += 1
    raise AssertionError("unbalanced CSS block")


def media_blocks(source):
    source = strip_css_comments(source)
    blocks = []
    for match in re.finditer(r"@media\s*\(([^)]*\bmax-width\b[^)]*)\)\s*\{", source, re.I):
        opening = source.find("{", match.start())
        blocks.append((match.group(1), matching_brace(source, opening)))
    return blocks


def css_rule(block, selector):
    cursor = 0
    while True:
        opening = block.find("{", cursor)
        if opening < 0:
            break
        selectors = [item.strip() for item in block[cursor:opening].split(",")]
        body = matching_brace(block, opening)
        if selector in selectors:
            return body
        cursor = opening + len(body) + 2
    raise AssertionError(f"missing CSS rule: {selector}")


def has_css_rule(block, selector):
    try:
        css_rule(block, selector)
    except AssertionError:
        return False
    return True


def runtime_source():
    viewer_script = ROOT / "static" / "js" / "file-viewers.js"
    source = viewer_script.read_text(encoding="utf-8") if viewer_script.exists() else ""
    return strip_javascript_comments(source)


class DocumentViewerContractTest(unittest.TestCase):
    def test_dashboard_declares_viewer_dom_and_local_script(self):
        parser = DashboardParser()
        parser.feed(TEMPLATE)
        ids = {attrs.get("id") for _, attrs in parser.elements}
        classes = {
            class_name
            for _, attrs in parser.elements
            for class_name in attrs.get("class", "").split()
        }
        for required_id in ("file-viewer-modal", "pdf-viewer", "word-viewer", "cad-viewer"):
            self.assertIn(required_id, ids, f"missing viewer root: {required_id}")
        self.assertIn("file-viewer-toolbar", classes, "missing viewer toolbar")
        scripts = [attrs.get("src", "") for attrs in parser.scripts]
        self.assertTrue(
            any(re.fullmatch(r"/static/js/file-viewers\.js(?:[?#].*)?", src) for src in scripts),
            "missing local file-viewers.js script",
        )

    def test_open_file_viewer_routes_extensions_by_public_behavior(self):
        node = node_executable()
        self.assertIsNotNone(node, "Node runtime missing; set NODE_EXE or install node")
        viewer_script = ROOT / "static" / "js" / "file-viewers.js"
        self.assertTrue(viewer_script.is_file(), "openFileViewer source missing")
        harness = r"""
const fs = require('fs'), vm = require('vm'), assert = require('assert');
const elements = new Map(), navigations = [], downloads = [];
function element(id, tag = 'div') {
  return elements.get(id) || elements.set(id, {
    id, tagName: tag.toUpperCase(), dataset: {}, style: {}, hidden: false,
    textContent: '', innerHTML: '', href: '', onclick: null, listeners: {},
    addEventListener(type, fn) { (this.listeners[type] ||= []).push(fn); },
    click() { for (const fn of this.listeners.click || []) fn({preventDefault(){}}); if (this.onclick) this.onclick({preventDefault(){}}); },
  }).get(id);
}
const document = {
  getElementById: element,
  querySelector: selector => element(selector.replace(/^#/, '')),
  createElement: tag => element(`${tag}-${elements.size}`, tag),
};
const hooks = {
  setViewerState: state => Object.assign(element('file-viewer-modal').dataset, state),
  setViewerContent: (type, file) => { element(`${type}-viewer`).dataset.fileName = file.fileName || file.name; element(`${type}-viewer`).dataset.previewUrl = file.previewUrl; },
  setFallback: (message, file) => { element('file-viewer-status').textContent = message; element('file-viewer-download').href = file.downloadUrl; },
  downloadFileViewerSource: (...args) => downloads.push(args),
};
const context = { console, module: {exports:{}}, exports: {}, window: {XingguiViewerTestHooks: hooks}, document, globalThis: null,
  location: {assign: url => navigations.push(url), replace: url => navigations.push(url)}, URL, setTimeout, clearTimeout };
context.globalThis = context; context.window.location = context.location;
context.window.open = url => navigations.push(url);
vm.createContext(context);
vm.runInContext(fs.readFileSync(process.argv[1], 'utf8'), context);
vm.runInContext("globalThis.__openFileViewer = typeof openFileViewer === 'function' ? openFileViewer : undefined", context);
const api = context.module.exports.openFileViewer || context.__openFileViewer || context.window.openFileViewer;
assert.strictEqual(typeof api, 'function', 'openFileViewer API missing');
const files = Object.fromEntries(['pdf','docx','stp','step','doc','x_t','x_b'].map((ext, i) => [ext, {
  name: `file-${ext}.${ext}`, fileName: `file-${ext}.${ext}`, extension: ext,
  previewUrl: `/preview/${i}`, downloadUrl: `/download/${i}`,
}]));
(async () => {
  for (const [ext, type] of [['pdf','pdf'],['docx','word'],['stp','cad'],['step','cad']]) {
    await api(files[ext]);
    assert.strictEqual(element('file-viewer-modal').dataset.viewerType, type, `${ext}: wrong viewer type`);
    assert.strictEqual(element(`${type}-viewer`).dataset.previewUrl, files[ext].previewUrl, `${ext}: missing preview URL`);
  }
  for (const ext of ['doc','x_t','x_b']) {
    await api(files[ext]);
    assert.match(element('file-viewer-status').textContent, /unsupported|not\s+supported|暂不支持|不支持/i, `${ext}: missing unsupported message`);
    const download = element('file-viewer-download'); download.click();
    assert.ok(download.href === files[ext].downloadUrl || navigations.includes(files[ext].downloadUrl) || downloads.some(args => args.includes(files[ext]) || args.includes(files[ext].downloadUrl)), `${ext}: wrong download target`);
  }
})().catch(error => { console.error(`openFileViewer: ${error.message}`); process.exitCode = 1; });
"""
        result = subprocess.run([str(node), "-e", harness, str(viewer_script)], cwd=ROOT, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr or "openFileViewer behavior failed")

    def test_local_viewer_assets_and_dependencies(self):
        source = runtime_source()
        paths = (
            "static/vendor/pdfjs/pdf.mjs", "static/vendor/pdfjs/pdf.worker.mjs",
            "static/vendor/docx-preview/docx-preview.min.js", "static/vendor/jszip/jszip.min.js",
            "static/vendor/three/three.module.min.js", "static/vendor/three/three.core.min.js",
            "static/vendor/three/examples/jsm/controls/OrbitControls.js",
            "static/vendor/occt-import-js/occt-import-js.js", "static/vendor/occt-import-js/occt-import-js.wasm",
        )
        for relative_path in paths:
            asset = ROOT / relative_path
            self.assertTrue(asset.is_file(), f"missing asset: {relative_path}")
            self.assertGreater(asset.stat().st_size, 0, f"empty asset: {relative_path}")
            self.assertIn("/" + relative_path.replace("\\", "/"), source, f"asset not referenced: {relative_path}")
        orbit_controls = (ROOT / "static/vendor/three/examples/jsm/controls/OrbitControls.js").read_text(encoding="utf-8")
        self.assertIn("from '../../../three.core.min.js'", orbit_controls)
        self.assertNotRegex(orbit_controls, r"from\s+['\"]three['\"]")
        string_values = re.findall(r"[\"'`]([^\"'`]+)[\"'`]", source)
        self.assertFalse(
            any(re.match(r"(?:https?:)?//", value) for value in string_values),
            "external viewer dependency",
        )
        for reference in (value for value in string_values if value.startswith("/static/")):
            self.assertTrue(reference.startswith("/static/vendor/"), f"non-vendor viewer path: {reference}")

    def test_bundled_viewer_assets_are_nonempty_and_closed(self):
        paths = (
            "static/vendor/pdfjs/pdf.mjs", "static/vendor/pdfjs/pdf.worker.mjs",
            "static/vendor/docx-preview/docx-preview.min.js", "static/vendor/jszip/jszip.min.js",
            "static/vendor/three/three.module.min.js", "static/vendor/three/three.core.min.js",
            "static/vendor/three/examples/jsm/controls/OrbitControls.js",
            "static/vendor/occt-import-js/occt-import-js.js", "static/vendor/occt-import-js/occt-import-js.wasm",
        )
        for relative_path in paths:
            asset = ROOT / relative_path
            self.assertTrue(asset.is_file(), f"missing asset: {relative_path}")
            self.assertGreater(asset.stat().st_size, 0, f"empty asset: {relative_path}")
        orbit_controls = (ROOT / "static/vendor/three/examples/jsm/controls/OrbitControls.js").read_text(encoding="utf-8")
        self.assertIn("from '../../../three.core.min.js'", orbit_controls)
        self.assertNotRegex(orbit_controls, r"from\s+['\"]three['\"]")

    def test_viewer_mobile_rules_are_scoped(self):
        blocks = [body for _, body in media_blocks(CSS)]
        self.assertTrue(blocks, "missing max-width media block")
        selectors = (".file-viewer-modal", ".file-viewer-toolbar", ".pdf-viewer", ".word-viewer", ".cad-viewer")
        rules = {}
        for selector in selectors:
            match = next((block for block in blocks if has_css_rule(block, selector)), None)
            self.assertIsNotNone(match, f"missing mobile rule: {selector}")
            rules[selector] = css_rule(match, selector)
        canvas_block = next((block for block in blocks if has_css_rule(block, ".cad-viewer canvas")), None)
        self.assertIsNotNone(canvas_block, "missing mobile canvas rule")
        canvas = css_rule(canvas_block, ".cad-viewer canvas")
        for selector in (".file-viewer-modal", ".pdf-viewer", ".word-viewer"):
            self.assertRegex(rules[selector], r"(?:height|min-height|aspect-ratio)\s*:", f"missing size: {selector}")
            self.assertRegex(rules[selector], r"overflow\s*:", f"missing overflow: {selector}")
        self.assertRegex(rules[".file-viewer-toolbar"], r"(?:height|min-height)\s*:", "missing toolbar size")
        self.assertRegex(rules[".cad-viewer"], r"overflow\s*:", "missing CAD overflow")
        self.assertRegex(canvas, r"width\s*:\s*100%", "missing canvas width")
        self.assertRegex(canvas, r"height\s*:\s*100%", "missing canvas height")
        self.assertRegex(canvas, r"touch-action\s*:", "missing canvas touch rule")

    def test_preview_download_routes_are_protected(self):
        lines = APP.splitlines()
        for route in ("/api/files/<int:fid>/download", "/api/files/<int:fid>/preview", "/api/drawings/<int:did>/download", "/api/drawings/<int:did>/preview"):
            index = next((i for i, line in enumerate(lines) if f"@app.route('{route}')" in line), None)
            self.assertIsNotNone(index, f"missing route: {route}")
            self.assertEqual(lines[index + 1].strip(), "@login_required", f"unprotected route: {route}")

    def test_release_expectations(self):
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        manifest = (ROOT / "android-xinggui" / "app" / "src" / "main" / "AndroidManifest.xml").read_text(encoding="utf-8")
        self.assertEqual(version, "1.0.6", "wrong VERSION")
        self.assertIn('android:versionName="1.0.6"', manifest, "wrong Android version")
        self.assertIn('android:versionCode="7"', manifest, "wrong Android code")


if __name__ == "__main__":
    unittest.main()
