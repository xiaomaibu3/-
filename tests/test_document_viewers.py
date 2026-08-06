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
const calls = { pdf: [], docx: [], cad: [], download: [], message: [] };
const spies = {
  pdf: (...args) => calls.pdf.push(args),
  docx: (...args) => calls.docx.push(args),
  cad: (...args) => calls.cad.push(args),
  download: (...args) => calls.download.push(args),
  message: (...args) => calls.message.push(args),
};
const statusMessages = [];
const status = {};
for (const property of ['textContent', 'innerText', 'innerHTML']) {
  Object.defineProperty(status, property, {
    get: () => statusMessages.join(' '),
    set: value => statusMessages.push(String(value)),
  });
}
const context = {
  console,
  module: { exports: {} },
  exports: {},
  window: {},
  document: {
    getElementById: () => status,
    querySelector: () => status,
  },
  alert: spies.message,
};
context.window.alert = spies.message;
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

function installSpy(names, spyName) {
  context.__viewerSpies = spies;
  for (const name of names) {
    vm.runInContext(
      `try { ${name} = globalThis.__viewerSpies.${spyName}; } catch (_) {}`,
      context
    );
    context[name] = spies[spyName];
    context.window[name] = spies[spyName];
    exported[name] = spies[spyName];
  }
}

installSpy(
  ['renderPdfViewer', 'renderPDFViewer', 'renderPdf', 'renderPDF', 'openPdfViewer'],
  'pdf'
);
installSpy(
  ['renderDocxViewer', 'renderDOCXViewer', 'renderDocx', 'renderDOCX', 'openDocxViewer'],
  'docx'
);
installSpy(
  [
    'renderCadViewer', 'renderCADViewer', 'renderStepViewer',
    'renderCad', 'renderCAD', 'renderStep', 'renderSTEP', 'openCadViewer',
  ],
  'cad'
);
installSpy(['downloadFileViewerSource'], 'download');
installSpy(
  ['showFileViewerMessage', 'showFileViewerStatus', 'setFileViewerStatus'],
  'message'
);

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

function resetCalls() {
  for (const entries of Object.values(calls)) entries.length = 0;
  statusMessages.length = 0;
}

function assertReceivesFileOrUrl(args, file, label, urlKey) {
  assert.ok(
    args.some(value => value === file || value === file[urlKey]),
    `${label} must receive the original file object or exact ${urlKey}`
  );
}

(async () => {
  const supported = [
    ['pdf', 'pdf'],
    ['docx', 'docx'],
    ['stp', 'cad'],
    ['step', 'cad'],
  ];
  for (const [extension, renderer] of supported) {
    resetCalls();
    const file = files[extension];
    await Promise.resolve(openFileViewer(file));
    assert.strictEqual(calls[renderer].length, 1, `${extension} must invoke its renderer`);
    assertReceivesFileOrUrl(calls[renderer][0], file, extension, 'previewUrl');
    for (const otherRenderer of ['pdf', 'docx', 'cad'].filter(name => name !== renderer)) {
      assert.strictEqual(
        calls[otherRenderer].length,
        0,
        `${extension} must not invoke the ${otherRenderer} renderer`
      );
    }
    assert.strictEqual(calls.download.length, 0, `${extension} must not download`);
  }

  const fallbackPrompts = {
    doc: /(?:旧版|Word|DOC)/i,
    x_t: /(?:XT|X_T)/i,
    x_b: /(?:XT|X_B)/i,
  };
  for (const extension of ['doc', 'x_t', 'x_b']) {
    resetCalls();
    const file = files[extension];
    await Promise.resolve(openFileViewer(file));
    assert.strictEqual(calls.download.length, 1, `${extension} must invoke download fallback`);
    assertReceivesFileOrUrl(calls.download[0], file, extension, 'downloadUrl');
    const message = calls.message.flat().join(' ') + ' ' + statusMessages.join(' ');
    assert.match(message, fallbackPrompts[extension], `${extension} must show its fallback prompt`);
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
