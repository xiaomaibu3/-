import re
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = (ROOT / "templates" / "dashboard.html").read_text(encoding="utf-8")
CSS = (ROOT / "static" / "css" / "style.css").read_text(encoding="utf-8")
APP = (ROOT / "app.py").read_text(encoding="utf-8")
NODE = Path(r"C:\Users\yelei\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe")


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

    def test_dashboard_loads_local_file_viewer_script(self):
        self.assertRegex(
            TEMPLATE,
            r'<script\b[^>]*\bsrc=["\']/static/js/file-viewers\.js(?:[?#][^"\']*)?["\'][^>]*>',
            "dashboard.html must load the local file-viewers.js script",
        )

    def test_open_file_viewer_routes_extensions_by_behavior(self):
        self.assertTrue(NODE.is_file(), f"Node runtime not found: {NODE}")
        viewer_script = ROOT / "static" / "js" / "file-viewers.js"
        self.assertTrue(
            viewer_script.is_file(),
            "openFileViewer API is missing from static/js/file-viewers.js",
        )
        harness = r"""
const fs = require('fs');
const vm = require('vm');
const assert = require('assert');

const fileName = process.argv[1];
class ClassList {
  constructor(element) {
    this.element = element;
    this.values = new Set();
  }
  add(...names) { names.forEach(name => this.values.add(name)); }
  remove(...names) { names.forEach(name => this.values.delete(name)); }
  contains(name) { return this.values.has(name); }
  toggle(name, force) {
    const enabled = force === undefined ? !this.contains(name) : force;
    enabled ? this.add(name) : this.remove(name);
    return enabled;
  }
}

class Element {
  constructor(id, classes = [], tagName = 'div') {
    this.id = id;
    this.tagName = tagName.toUpperCase();
    this.dataset = {};
    this.style = {};
    this.hidden = false;
    this.attributes = {};
    this.textContent = '';
    this.innerText = '';
    this.innerHTML = '';
    this.href = '';
    this.src = '';
    this.value = '';
    this.onclick = null;
    this.listeners = new Map();
    this.classList = new ClassList(this);
    this.classList.add(...classes);
  }
  setAttribute(name, value) {
    const stringValue = String(value);
    this.attributes[name] = stringValue;
    if (name === 'href') this.href = stringValue;
    if (name === 'src') this.src = stringValue;
    if (name.startsWith('data-')) {
      const key = name.slice(5).replace(/-([a-z])/g, (_, letter) => letter.toUpperCase());
      this.dataset[key] = stringValue;
    }
  }
  getAttribute(name) {
    if (name === 'href') return this.href || this.attributes[name] || null;
    if (name === 'src') return this.src || this.attributes[name] || null;
    return this.attributes[name] || null;
  }
  removeAttribute(name) {
    delete this.attributes[name];
    if (name === 'href') this.href = '';
    if (name === 'src') this.src = '';
  }
  addEventListener(type, listener) {
    const listeners = this.listeners.get(type) || [];
    listeners.push(listener);
    this.listeners.set(type, listeners);
  }
  removeEventListener(type, listener) {
    const listeners = this.listeners.get(type) || [];
    this.listeners.set(type, listeners.filter(candidate => candidate !== listener));
  }
  click() {
    const event = {
      type: 'click',
      target: this,
      currentTarget: this,
      defaultPrevented: false,
      preventDefault() { this.defaultPrevented = true; },
    };
    for (const listener of this.listeners.get('click') || []) listener.call(this, event);
    if (typeof this.onclick === 'function') this.onclick.call(this, event);
    if (!event.defaultPrevented && this.tagName === 'A' && this.href) {
      navigation.href = this.href;
    }
  }
  replaceChildren() { this.innerHTML = ''; this.textContent = ''; }
  appendChild(child) { elements.push(child); return child; }
  querySelector(selector) { return document.querySelector(selector); }
  querySelectorAll(selector) { return document.querySelectorAll(selector); }
}

const elements = [
  new Element('file-viewer-modal', ['file-viewer-modal']),
  new Element('file-viewer-title', ['file-viewer-title']),
  new Element('file-viewer-status', ['file-viewer-status']),
  new Element('file-viewer-download', ['file-viewer-download'], 'a'),
  new Element('pdf-viewer', ['pdf-viewer']),
  new Element('word-viewer', ['word-viewer']),
  new Element('cad-viewer', ['cad-viewer']),
];
const byId = Object.fromEntries(elements.map(element => [element.id, element]));
const navigation = {
  href: '',
  assign(url) { this.href = String(url); },
  replace(url) { this.href = String(url); },
};
const selectorMatches = (element, selector) => {
  if (selector.startsWith('#')) return element.id === selector.slice(1);
  if (selector.startsWith('.')) return element.classList.contains(selector.slice(1));
  if (selector === '[data-viewer-type]') return element.dataset.viewerType !== undefined;
  if (selector.includes('download')) {
    return element.id.includes('download') || element.classList.contains('file-viewer-download');
  }
  return false;
};
const document = {
  body: new Element('body'),
  getElementById: id => byId[id] || null,
  querySelector: selector => elements.find(element => selectorMatches(element, selector)) || null,
  querySelectorAll: selector => elements.filter(element => selectorMatches(element, selector)),
  createElement: tag => new Element(`${tag}-${elements.length}`, [], tag),
};
const context = {
  console,
  module: { exports: {} },
  exports: {},
  window: { location: navigation },
  location: navigation,
  document,
  Element,
  HTMLElement: Element,
  URL,
  setTimeout,
  clearTimeout,
};
context.window.document = document;
context.window.open = url => { navigation.href = String(url); };
context.globalThis = context;
vm.createContext(context);
vm.runInContext(fs.readFileSync(fileName, 'utf8'), context, { filename: fileName });
vm.runInContext(
  "globalThis.__openFileViewer = typeof openFileViewer === 'function' ? openFileViewer : undefined",
  context
);

const exported = context.module.exports;
const openFileViewer =
  exported.openFileViewer || context.__openFileViewer || context.window.openFileViewer;
assert.strictEqual(
  typeof openFileViewer,
  'function',
  'openFileViewer API is missing from static/js/file-viewers.js'
);
const downloadCalls = [];
const downloadSpy = (...args) => downloadCalls.push(args);
context.__downloadSpy = downloadSpy;
vm.runInContext(
  "try { downloadFileViewerSource = globalThis.__downloadSpy; } catch (_) {}",
  context
);
context.downloadFileViewerSource = downloadSpy;
context.window.downloadFileViewerSource = downloadSpy;
exported.downloadFileViewerSource = downloadSpy;

const files = {
  pdf: {
    id: 101,
    name: 'contract-pdf.pdf',
    fileName: 'contract-pdf.pdf',
    extension: 'pdf',
    previewUrl: '/api/files/101/preview',
    downloadUrl: '/api/files/101/download',
  },
  docx: {
    id: 102,
    name: 'contract-docx.docx',
    fileName: 'contract-docx.docx',
    extension: 'docx',
    previewUrl: '/api/files/102/preview',
    downloadUrl: '/api/files/102/download',
  },
  stp: {
    drawingId: 103,
    name: 'contract-stp.stp',
    fileName: 'contract-stp.stp',
    extension: 'stp',
    previewUrl: '/api/drawings/103/preview',
    downloadUrl: '/api/drawings/103/download',
  },
  step: {
    drawingId: 104,
    name: 'contract-step.step',
    fileName: 'contract-step.step',
    extension: 'step',
    previewUrl: '/api/drawings/104/preview',
    downloadUrl: '/api/drawings/104/download',
  },
  doc: {
    id: 105,
    name: 'contract-doc.doc',
    fileName: 'contract-doc.doc',
    extension: 'doc',
    previewUrl: '/api/files/105/preview',
    downloadUrl: '/api/files/105/download',
  },
  x_t: {
    drawingId: 106,
    name: 'contract-x-t.x_t',
    fileName: 'contract-x-t.x_t',
    extension: 'x_t',
    previewUrl: '/api/drawings/106/preview',
    downloadUrl: '/api/drawings/106/download',
  },
  x_b: {
    drawingId: 107,
    name: 'contract-x-b.x_b',
    fileName: 'contract-x-b.x_b',
    extension: 'x_b',
    previewUrl: '/api/drawings/107/preview',
    downloadUrl: '/api/drawings/107/download',
  },
};

function resetDom() {
  downloadCalls.length = 0;
  navigation.href = '';
  for (const element of elements) {
    element.dataset = {};
    element.style = {};
    element.hidden = false;
    element.attributes = {};
    element.textContent = '';
    element.innerText = '';
    element.innerHTML = '';
    element.href = '';
    element.src = '';
    element.onclick = null;
    element.listeners = new Map();
    element.classList.remove('active', 'visible', 'is-active', 'is-visible', 'hidden');
  }
}

function isVisible(element) {
  const panels = ['pdf-viewer', 'word-viewer', 'cad-viewer'].map(id => byId[id]);
  const positiveClasses = ['active', 'visible', 'is-active', 'is-visible'];
  const usesPositiveClass = panels.some(panel =>
    positiveClasses.some(name => panel.classList.contains(name))
  );
  if (usesPositiveClass) {
    return positiveClasses.some(name => element.classList.contains(name));
  }
  return !element.hidden &&
    element.style.display !== 'none' &&
    element.style.visibility !== 'hidden' &&
    !element.classList.contains('hidden');
}

function datasetValues() {
  return elements.flatMap(element => Object.values(element.dataset)).map(String);
}

function domValues() {
  return elements.flatMap(element => [
    element.textContent,
    element.innerText,
    element.innerHTML,
    element.href,
    element.src,
    ...Object.values(element.dataset),
    ...Object.values(element.attributes),
  ]).map(String);
}

function inlineDownloadControls() {
  const controls = [];
  for (const owner of elements) {
    const pattern = /<(a|button)\b([^>]*)>([\s\S]*?)<\/\1>/gi;
    for (const match of owner.innerHTML.matchAll(pattern)) {
      const control = new Element(`inline-download-${controls.length}`, [], match[1]);
      control.textContent = match[3].replace(/<[^>]+>/g, ' ');
      const href = match[2].match(/\bhref\s*=\s*["']([^"']+)["']/i);
      if (href) control.href = href[1];
      const onclick = match[2].match(/\bonclick\s*=\s*["']([^"']+)["']/i);
      if (onclick) {
        control.onclick = () => vm.runInContext(onclick[1], context);
      }
      controls.push(control);
    }
  }
  return controls;
}

function downloadControls() {
  return [...elements, ...inlineDownloadControls()].filter(element =>
    ['A', 'BUTTON'].includes(element.tagName) &&
    (element.id.toLowerCase().includes('download') ||
      element.classList.contains('file-viewer-download') ||
      /(?:download|下载)/i.test(element.textContent) ||
      element.href || element.onclick || (element.listeners.get('click') || []).length)
  );
}

function downloadCallTargetsFile(args, file) {
  return args.some(value => value === file || value === file.downloadUrl);
}

(async () => {
  const supported = [
    ['pdf', 'pdf'],
    ['docx', 'word'],
    ['stp', 'cad'],
    ['step', 'cad'],
  ];
  for (const [extension, viewerType] of supported) {
    resetDom();
    const file = files[extension];
    await Promise.resolve(openFileViewer(file));
    const root = byId['file-viewer-modal'];
    assert.strictEqual(root.dataset.viewerType, viewerType, `${extension} must expose its viewer type`);
    for (const type of ['pdf', 'word', 'cad']) {
      const panel = byId[`${type}-viewer`];
      assert.strictEqual(
        isVisible(panel),
        type === viewerType,
        `${extension} must ${type === viewerType ? 'show' : 'hide'} .${type}-viewer`
      );
    }
    const values = datasetValues();
    assert.ok(values.includes(file.fileName) || values.includes(file.name), `${extension} metadata must be exposed in the viewer DOM`);
    assert.ok(values.includes(file.previewUrl), `${extension} previewUrl must be exposed in the viewer DOM`);
  }

  const fallbackPrompts = {
    doc: /(?:旧版|Word|DOC)/i,
    x_t: /(?:XT|X_T)/i,
    x_b: /(?:XT|X_B)/i,
  };
  for (const extension of ['doc', 'x_t', 'x_b']) {
    resetDom();
    const file = files[extension];
    await Promise.resolve(openFileViewer(file));
    const message = domValues().join(' ');
    assert.match(message, fallbackPrompts[extension], `${extension} must show its fallback prompt`);
    assert.match(message, /(?:不支持|暂不支持|unsupported)/i, `${extension} must be explicitly unsupported`);
    const controls = downloadControls();
    assert.ok(controls.length, `${extension} must expose an anchor or button download control`);
    let matched = false;
    for (const control of controls) {
      downloadCalls.length = 0;
      navigation.href = '';
      control.click();
      matched = downloadCalls.some(args => downloadCallTargetsFile(args, file)) ||
        navigation.href === file.downloadUrl || control.href === file.downloadUrl;
      if (matched) break;
    }
    assert.ok(matched, `${extension} download click must target its file or downloadUrl`);
  }
})().catch(error => {
  console.error(`openFileViewer behavior test failed: ${error.stack || error}`);
  process.exitCode = 1;
});
"""
        result = subprocess.run(
            [str(NODE), "-e", harness, str(viewer_script)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
        )
        self.assertEqual(
            result.returncode,
            0,
            "openFileViewer behavior test failed:\n" + (result.stderr or result.stdout),
        )

    def test_local_viewer_assets_exist_and_runtime_references_are_local(self):
        source = runtime_source()
        viewer_script = ROOT / "static" / "js" / "file-viewers.js"
        viewer_source = without_comments(
            viewer_script.read_text(encoding="utf-8") if viewer_script.exists() else ""
        )
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
        static_references = re.findall(r'["\'](?P<path>/static/[^"\']+)["\']', viewer_source)
        for reference in static_references:
            self.assertTrue(
                reference.startswith("/static/vendor/"),
                f"viewer runtime dependency is outside /static/vendor/: {reference}",
            )
        self.assertNotRegex(source, r"https?://", re.IGNORECASE)
        self.assertNotRegex(source, r"//", "viewer runtime must not use protocol-relative external URLs")

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
        self.assertRegex(rules[".file-viewer-modal"], r"(?:min-height|height|aspect-ratio)\s*:")
        self.assertRegex(rules[".file-viewer-modal"], r"overflow\s*:")
        self.assertRegex(rules[".file-viewer-toolbar"], r"(?:min-height|height)\s*:")
        self.assertRegex(rules[".pdf-viewer"], r"(?:min-height|height|aspect-ratio)\s*:")
        self.assertRegex(rules[".pdf-viewer"], r"overflow\s*:")
        self.assertRegex(rules[".word-viewer"], r"(?:min-height|height|aspect-ratio)\s*:")
        self.assertRegex(rules[".word-viewer"], r"overflow\s*:")
        self.assertRegex(rules[".cad-viewer"], r"overflow\s*:\s*(?:hidden|auto)")
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
