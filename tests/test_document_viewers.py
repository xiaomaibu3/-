import hashlib
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
    def test_pdf_renderer_contract_uses_local_pdfjs_and_controls(self):
        source = runtime_source()
        for asset in ("/static/vendor/pdfjs/pdf.mjs", "/static/vendor/pdfjs/pdf.worker.mjs"):
            self.assertIn(asset, source)
        self.assertIn("getDocument", source)
        self.assertRegex(source, r"fetch\s*\(\s*file\.previewUrl|fetch\s*\(\s*.*previewUrl")
        self.assertIn("credentials: 'include'", source)
        for control in ("pdf-page-number", "pdf-zoom-in", "pdf-zoom-out", "pdf-rotate", "pdf-fit-width"):
            self.assertIn(control, TEMPLATE, f"missing PDF control: {control}")
        self.assertRegex(source, r"canvas|getViewport|render\s*\(")
        self.assertRegex(source, r"devicePixelRatio|pixelRatio")

    def test_docx_renderer_contract_fetches_securely_and_uses_local_dependencies(self):
        source = runtime_source()
        self.assertIn("/static/vendor/docx-preview/docx-preview.min.js", source)
        self.assertIn("/static/vendor/jszip/jszip.min.js", source)
        self.assertIn("previewUrl", source)
        self.assertIn("credentials: 'include'", source)
        self.assertIn("arrayBuffer()", source)
        self.assertIn("docx.renderAsync", source)
        self.assertRegex(source, r"in隔离容器|isolat|render.*container")
        self.assertRegex(source, r"禁用脚本|scripts\s*:\s*false|allowScripts\s*:\s*false|script")
        self.assertRegex(source, r"ready|error")

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

    def test_viewer_asset_fetch_script_is_staged_and_hash_pinned(self):
        script = (ROOT / "scripts/fetch-viewer-assets.ps1").read_text(encoding="utf-8")
        self.assertIn("[guid]::NewGuid().ToString('N')", script)
        self.assertIn('.viewer-assets-staging-$operationId', script)
        self.assertIn('.viewer-assets-backup-$operationId', script)
        self.assertIn("Get-FileHash -LiteralPath $destination -Algorithm SHA256", script)
        self.assertGreaterEqual(len(re.findall(r"Sha256\s*=\s*'[0-9A-F]{64}'", script)), 10)
        self.assertIn("[Text.UTF8Encoding]::new($false, $true)", script)
        self.assertIn("Invalid WASM header", script)
        self.assertIn("HTML error page downloaded", script)
        self.assertIn("$replacedFiles = [System.Collections.Generic.List[object]]::new()", script)
        self.assertIn("BackedUp = $false; Installed = $false", script)
        self.assertIn("for ($index = $replacedFiles.Count - 1; $index -ge 0; $index--)", script)
        self.assertIn("if ($state.Installed", script)
        self.assertIn("if ($state.BackedUp", script)
        self.assertIn("if ($backupCreated -and $recoverySucceeded)", script)
        self.assertNotIn("Move-Item -LiteralPath $vendor", script)
        self.assertNotIn("Move-Item -LiteralPath $staging -Destination $vendor", script)
        self.assertNotRegex(script, r"Get-ChildItem[^\n]+\.viewer-assets")
        self.assertNotRegex(script, r"Remove-Item[^\n]+\.viewer-assets-\*")
        self.assertLess(script.index(".install-ready"), script.index("foreach ($asset in $assets) {\n        $relative = $asset.RelativePath"))
        entries = re.findall(
            r"RelativePath = '([^']+)'; Url = '[^']+'; Sha256 = '([0-9A-F]{64})'(?:; PublishedSha256 = '([0-9A-F]{64})')?",
            script,
        )
        self.assertEqual(len(entries), 9)
        for relative_path, download_hash, published_hash in entries:
            blob = (ROOT / "static/vendor" / relative_path).read_bytes()
            self.assertEqual(hashlib.sha256(blob).hexdigest().upper(), published_hash or download_hash, relative_path)

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

    def test_viewer_lifecycle_supports_dynamic_async_renderers_and_cleanup(self):
        node = node_executable()
        self.assertIsNotNone(node, "Node runtime missing; set NODE_EXE or install node")
        viewer_script = ROOT / "static/js" / "file-viewers.js"
        harness = r"""
const fs = require('fs'), vm = require('vm'), assert = require('assert');
const elements = new Map(), revoked = [], focusLog = [];
function element(id) {
  if (!elements.has(id)) elements.set(id, {
    id, dataset: {}, style: {}, hidden: false, textContent: '', innerHTML: '', href: '', onclick: null,
    listeners: {}, focus() { focusLog.push(this.id); },
    addEventListener(type, fn) { (this.listeners[type] ||= []).push(fn); },
    removeEventListener(type, fn) { this.listeners[type] = (this.listeners[type] || []).filter(item => item !== fn); },
    click() { if (this.onclick) this.onclick({preventDefault(){}}); },
  });
  return elements.get(id);
}
const document = { getElementById: element, querySelector: s => element(s.replace(/^#/, '')), createElement: tag => element(`${tag}-${elements.size}`) };
const context = { console, module: {exports:{}}, exports:{}, document, window:{}, globalThis:null,
  URL:{revokeObjectURL: url => revoked.push(url)}, location:{assign(){}}, setTimeout, clearTimeout };
context.globalThis = context; context.window.location = context.location;
vm.createContext(context); vm.runInContext(fs.readFileSync(process.argv[1], 'utf8'), context);
const api = context.module.exports;
assert.strictEqual(typeof api.registerFileViewerRenderer, 'function', 'renderer registry API missing');
const file = {name:'sample.pdf', fileName:'sample.pdf', extension:'pdf', previewUrl:'/preview', downloadUrl:'/download'};
let cleaned = false;
api.registerFileViewerRenderer('pdf', async (target, current) => {
  await Promise.resolve(); target.textContent = current.fileName;
  return () => { cleaned = true; };
});
(async () => {
  await api.openFileViewer(file);
  assert.strictEqual(element('file-viewer-modal').dataset.state, 'ready');
  api.resetFileViewer();
  assert.ok(cleaned, 'renderer cleanup not called');
  assert.strictEqual(element('file-viewer-download').href, '');
  assert.strictEqual(element('file-viewer-download').onclick, null);
  assert.strictEqual(element('file-viewer-status').textContent, '');
  api.registerFileViewerRenderer('pdf', () => Promise.reject(new Error('boom')));
  await api.openFileViewer(file);
  assert.strictEqual(element('file-viewer-modal').dataset.state, 'error');
  assert.match(element('file-viewer-status').textContent, /failed|error|澶辫触/i);
  assert.strictEqual(element('file-viewer-download').href, '/download');
})().catch(error => { console.error(error); process.exitCode = 1; });
"""
        result = subprocess.run([str(node), "-e", harness, str(viewer_script)], cwd=ROOT, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr or "viewer lifecycle failed")

    def test_preview_routing_preserves_images_and_download_fallback(self):
        self.assertRegex(TEMPLATE, r"function previewFile\(fid, fileName\)[\s\S]*?\['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp'\]")
        self.assertRegex(TEMPLATE, r"function previewDrawing\(did, filePath, drawingName\)[\s\S]*?\['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp'\]")
        self.assertRegex(TEMPLATE, r"\['pdf', 'docx', 'stp', 'step', 'doc', 'x_t', 'x_b'\]")
        self.assertNotIn("window.open", TEMPLATE)

    def test_viewer_dialog_focus_lifecycle_is_declared(self):
        source = runtime_source()
        self.assertIn("registerFileViewerRenderer", source)
        self.assertRegex(source, r"document\.activeElement")
        self.assertRegex(source, r"Tab")
        self.assertRegex(source, r"file-viewer-modal.*focus|focus.*file-viewer-modal", re.I)
        self.assertRegex(source, r"previousFocus|triggerElement|opener", re.I)
        self.assertRegex(CSS, r"\.pdf-viewer[^}]*max-width\s*:")
        self.assertRegex(CSS, r"\.word-viewer[^}]*line-height\s*:")
        self.assertRegex(CSS, r"\.cad-viewer[^}]*overflow\s*:\s*hidden")

    def test_stale_async_renderers_cannot_mutate_current_or_closed_viewer(self):
        node = node_executable()
        self.assertIsNotNone(node, "Node runtime missing; set NODE_EXE or install node")
        viewer_script = ROOT / "static/js" / "file-viewers.js"
        harness = r"""
const fs = require('fs'), vm = require('vm'), assert = require('assert');
const elements = new Map(), revoked = [], documentListeners = {};
function deferred() { let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no; }); return {promise, resolve, reject}; }
function element(id) {
  if (!elements.has(id)) elements.set(id, {id, dataset:{}, style:{}, hidden:false, textContent:'', innerHTML:'', href:'', onclick:null,
    focus(){ document.activeElement = this; }, addEventListener(){}, removeEventListener(){}, querySelectorAll(){ return []; }});
  return elements.get(id);
}
const trigger = element('trigger');
const document = {activeElement:trigger, getElementById:element, querySelector:s=>element(s.replace(/^#/,'')),
  addEventListener(type, fn){ (documentListeners[type] ||= []).push(fn); }, removeEventListener(){}};
const context = {console, module:{exports:{}}, exports:{}, document, window:{}, globalThis:null,
  URL:{revokeObjectURL:url=>revoked.push(url)}, location:{assign(){}}, setTimeout, clearTimeout};
context.globalThis=context; context.window.location=context.location;
vm.createContext(context); vm.runInContext(fs.readFileSync(process.argv[1], 'utf8'), context);
const api=context.module.exports, first=deferred(), second=deferred(); let firstCleanup=0, secondCleanup=0;
api.registerFileViewerRenderer('pdf', () => first.promise);
const openA=api.openFileViewer({name:'a.pdf', extension:'pdf', previewUrl:'/a', downloadUrl:'/da'});
api.registerFileViewerRenderer('pdf', () => second.promise);
const openB=api.openFileViewer({name:'b.pdf', extension:'pdf', previewUrl:'/b', downloadUrl:'/db'});
second.resolve({cleanup:()=>secondCleanup++, objectUrl:'blob:b'});
(async()=>{
  await openB;
  assert.strictEqual(element('file-viewer-modal').dataset.state, 'ready');
  assert.strictEqual(element('pdf-viewer').dataset.previewUrl, '/b');
  first.resolve({cleanup:()=>firstCleanup++, objectUrl:'blob:a'});
  await openA;
  assert.strictEqual(firstCleanup, 1, 'late cleanup must run immediately');
  assert.ok(revoked.includes('blob:a'), 'late object URL must be revoked immediately');
  assert.strictEqual(element('pdf-viewer').dataset.previewUrl, '/b', 'A overwrote B');
  api.closeFileViewer();
  assert.strictEqual(secondCleanup, 1);
  assert.ok(revoked.includes('blob:b'));
  const third=deferred(); let thirdCleanup=0;
  api.registerFileViewerRenderer('pdf', () => third.promise);
  const openC=api.openFileViewer({name:'c.pdf', extension:'pdf', previewUrl:'/c', downloadUrl:'/dc'});
  api.resetFileViewer();
  third.resolve({cleanup:()=>thirdCleanup++, objectUrl:'blob:c'});
  await openC;
  assert.strictEqual(thirdCleanup, 1);
  assert.ok(revoked.includes('blob:c'));
  assert.strictEqual(element('file-viewer-modal').dataset.state, undefined);
  assert.strictEqual(element('file-viewer-status').textContent, '');
  const fourth=deferred();
  api.registerFileViewerRenderer('pdf', () => fourth.promise);
  const openD=api.openFileViewer({name:'d.pdf', extension:'pdf', previewUrl:'/d', downloadUrl:'/dd'});
  api.closeFileViewer(); fourth.reject(new Error('late failure')); await openD;
  assert.strictEqual(element('file-viewer-modal').dataset.state, undefined, 'late rejection changed closed UI');
})().catch(error=>{console.error(error);process.exitCode=1;});
"""
        result = subprocess.run([str(node), "-e", harness, str(viewer_script)], cwd=ROOT, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr or "stale renderer race failed")

    def test_escape_closes_viewer_and_restores_focus(self):
        node = node_executable()
        self.assertIsNotNone(node, "Node runtime missing; set NODE_EXE or install node")
        viewer_script = ROOT / "static/js" / "file-viewers.js"
        harness = r"""
const fs=require('fs'),vm=require('vm'),assert=require('assert'); const elements=new Map(), listeners={};
function element(id){if(!elements.has(id))elements.set(id,{id,dataset:{},style:{},hidden:false,href:'',onclick:null,textContent:'',innerHTML:'',focus(){document.activeElement=this;},addEventListener(){},removeEventListener(){},querySelectorAll(){return[];}});return elements.get(id);}
const trigger=element('trigger'); const document={activeElement:trigger,getElementById:element,querySelector:s=>element(s.replace(/^#/,'')),addEventListener(t,f){(listeners[t]||=[]).push(f);}};
const context={console,module:{exports:{}},exports:{},document,window:{},globalThis:null,URL:{revokeObjectURL(){}},location:{assign(){}},setTimeout,clearTimeout};context.globalThis=context;context.window.location=context.location;
vm.createContext(context);vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),context);const api=context.module.exports;
api.registerFileViewerRenderer('pdf',()=>Promise.resolve());
(async()=>{await api.openFileViewer({name:'x.pdf',extension:'pdf',downloadUrl:'/d'});assert.ok((listeners.keydown||[]).length,'Escape listener missing');
for(const fn of listeners.keydown)fn({key:'Escape'});assert.strictEqual(element('file-viewer-modal').hidden,true);assert.strictEqual(document.activeElement,trigger);})().catch(e=>{console.error(e);process.exitCode=1;});
"""
        result = subprocess.run([str(node), "-e", harness, str(viewer_script)], cwd=ROOT, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr or "Escape lifecycle failed")

    def test_preview_functions_are_unique_and_switch_viewer_modes(self):
        self.assertEqual(len(re.findall(r"function\s+previewFile\s*\(", TEMPLATE)), 1)
        self.assertEqual(len(re.findall(r"function\s+previewDrawing\s*\(", TEMPLATE)), 1)
        for function_name in ("previewFile", "previewDrawing"):
            match = re.search(rf"function\s+{function_name}\s*\([^)]*\)\s*\{{([\s\S]*?)\n\}}", TEMPLATE)
            self.assertIsNotNone(match)
            body = match.group(1)
            self.assertNotIn("window.open", body)
            self.assertRegex(body, r"\b(?:resetFileViewer|closeFileViewer)\s*\(")
            self.assertRegex(body, r"location\.assign\([^)]*download")

    def test_renderer_direct_writes_are_isolated_per_generation(self):
        node = node_executable()
        self.assertIsNotNone(node, "Node runtime missing; set NODE_EXE or install node")
        viewer_script = ROOT / "static/js" / "file-viewers.js"
        harness = r"""
const fs=require('fs'),vm=require('vm'),assert=require('assert'); const elements=new Map();
function element(id){if(!elements.has(id))elements.set(id,{id,dataset:{},style:{},hidden:false,innerHTML:'',children:[],appendChild(n){this.children.push(n);n.parentNode=this;},removeChild(n){this.children=this.children.filter(x=>x!==n);n.parentNode=null;},focus(){document.activeElement=this;},addEventListener(){},removeEventListener(){},querySelectorAll(){return[];}});return elements.get(id);}
const trigger=element('trigger'); const document={activeElement:trigger,getElementById:element,querySelector:s=>element(s.replace(/^#/,'')),createElement:tag=>({tagName:tag.toUpperCase(),dataset:{},style:{},innerHTML:'',parentNode:null})};
const context={console,module:{exports:{}},exports:{},document,window:{},globalThis:null,URL:{revokeObjectURL(){}},location:{assign(){}},setTimeout,clearTimeout};context.globalThis=context;context.window.location=context.location;
vm.createContext(context);vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),context);const api=context.module.exports;let a,b;
api.registerFileViewerRenderer('pdf',(target,file)=>{if(file.name==='a.pdf')a=target;else b=target;return new Promise(resolve=>setTimeout(()=>{target.textContent=file.name;resolve();},file.name==='a.pdf'?20:1));});
(async()=>{const openA=api.openFileViewer({name:'a.pdf',extension:'pdf'});const openB=api.openFileViewer({name:'b.pdf',extension:'pdf'});await Promise.all([openA,openB]);assert.strictEqual(element('pdf-viewer').children.length,1);assert.strictEqual(element('pdf-viewer').children[0].textContent,'b.pdf');api.closeFileViewer();a.textContent='late-a';assert.strictEqual(element('pdf-viewer').children.length,0);})().catch(e=>{console.error(e);process.exitCode=1;});
"""
        result=subprocess.run([str(node),"-e",harness,str(viewer_script)],cwd=ROOT,capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stderr or "renderer target isolation failed")

    def test_release_expectations(self):
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        manifest = (ROOT / "android-xinggui" / "app" / "src" / "main" / "AndroidManifest.xml").read_text(encoding="utf-8")
        self.assertEqual(version, "1.0.6", "wrong VERSION")
        self.assertIn('android:versionName="1.0.6"', manifest, "wrong Android version")
        self.assertIn('android:versionCode="7"', manifest, "wrong Android code")


if __name__ == "__main__":
    unittest.main()
