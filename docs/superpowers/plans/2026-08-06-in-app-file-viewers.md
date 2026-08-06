# 内置文件查看器 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在桌面网页、PWA 和星轨 Android WebView 内集成 PDF、DOCX、STP/STEP 查看器，排除 XT，并升级到 1.0.6。

**Architecture:** 在现有 `modal-main` 基础上增加统一 viewer shell，由文件扩展名选择 PDF、DOCX 或 STEP 渲染器。PDF.js、docx-preview、Three.js 和 occt-import-js 的浏览器构建产物随项目静态发布；现有受登录保护的预览/下载路由继续作为唯一文件入口。渲染器只处理展示和生命周期，不接触项目业务逻辑。

**Tech Stack:** Flask, vanilla JavaScript, CSS, PDF.js, docx-preview, Three.js, OpenCascade WebAssembly via occt-import-js, Android WebView.

---

### Task 1: Lock viewer behavior with failing tests

**Files:**
- Create: `tests/test_document_viewers.py`
- Modify: `tests/test_xinggui_mobile_app.py`

- [ ] **Step 1: Write failing backend/static contract tests**

Add tests that read the real application files and assert:
- `dashboard.html` contains `openFileViewer`, `pdf-viewer`, `word-viewer`, `cad-viewer`.
- PDF/DOCX/STP/STEP are routed to `openFileViewer`.
- `.doc` and XT are routed to a download/fallback branch.
- `dashboard.html` loads local viewer assets, never a remote viewer URL.
- CSS contains responsive viewer classes and touch-safe canvas sizing.
- `app.py` keeps `login_required` on file preview and download routes.
- `VERSION` and Android manifest are expected to move to 1.0.6/versionCode 7.

- [ ] **Step 2: Run only the new tests**

Run: `python -m unittest tests.test_document_viewers -v`

Expected: FAIL because the viewer shell, assets, routing, and release values do not exist yet.

- [ ] **Step 3: Commit the red tests**

Run:
`git add tests/test_document_viewers.py tests/test_xinggui_mobile_app.py`
`git commit -m "test: define in-app viewer contracts"`

---

### Task 2: Add pinned local viewer assets

**Files:**
- Create: `static/vendor/pdfjs/pdf.mjs`, `static/vendor/pdfjs/pdf.worker.mjs`
- Create: `static/vendor/docx-preview/docx-preview.min.js`
- Create: `static/vendor/three/three.module.min.js`, `static/vendor/three/examples/jsm/controls/OrbitControls.js`
- Create: `static/vendor/occt-import-js/occt-import-js.js`, `static/vendor/occt-import-js/occt-import-js.wasm`
- Create: `scripts/fetch-viewer-assets.ps1`
- Modify: `.gitignore`

- [ ] **Step 1: Add a reproducible asset fetch script**

Pin exact upstream versions in the PowerShell script:
- `pdfjs-dist` 6.2.108 generic build.
- `docx-preview` 0.4.0.
- `three` 0.185.1.
- `occt-import-js` 0.0.23.

The script downloads only the listed browser builds into `static/vendor`, creates directories, and fails if any required file is missing. It must not use a CDN at runtime.

- [ ] **Step 2: Fetch and validate assets**

Run: `powershell -ExecutionPolicy Bypass -File .\scripts\fetch-viewer-assets.ps1`

Expected: all required files exist and have non-zero sizes; the WASM file is present for STEP parsing.

- [ ] **Step 3: Add only generated vendor assets to the intended paths**

Update `.gitignore` so unrelated build output is ignored while `static/vendor` remains tracked.

- [ ] **Step 4: Commit assets separately**

Run:
`git add scripts/fetch-viewer-assets.ps1 .gitignore static/vendor`
`git commit -m "feat: bundle local document and CAD viewer assets"`

---

### Task 3: Implement the unified viewer shell

**Files:**
- Modify: `templates/dashboard.html:96-107`
- Modify: `static/css/style.css`
- Modify: `static/js/app.js`

- [ ] **Step 1: Add viewer modal markup**

Add a viewer-specific modal inside the existing modal system with:
- title and file name;
- close button;
- toolbar slot;
- content slot;
- status/error slot;
- download button.

Use stable `min-height` and `aspect-ratio` constraints so loading text and controls cannot resize the viewer.

- [ ] **Step 2: Add viewer CSS**

Implement `.file-viewer-modal`, `.file-viewer-toolbar`, `.pdf-viewer`, `.word-viewer`, `.cad-viewer`, and mobile media rules. The CAD canvas must fill its parent with no overflow; document content must use bounded width and readable line height. Respect `prefers-reduced-motion`.

- [ ] **Step 3: Add lifecycle helpers**

Implement `openFileViewer(file)`, `closeFileViewer()`, `resetFileViewer()`, and `downloadFileViewerSource()`. Opening clears the previous renderer, sets loading state, and dispatches by lower-case extension. Closing destroys PDF pages, DOCX content, Three.js controls/renderer, object URLs, and event listeners.

- [ ] **Step 4: Run the contract test**

Run: `python -m unittest tests.test_document_viewers -v`

Expected: still FAIL only on renderer-specific behavior and asset references.

---

### Task 4: Implement PDF and DOCX rendering test-first

**Files:**
- Modify: `static/js/file-viewers.js`
- Modify: `templates/dashboard.html`
- Modify: `static/css/style.css`
- Test: `tests/test_document_viewers.py`

- [ ] **Step 1: Add renderer contract assertions**

Assert that the PDF renderer configures the local worker, fetches the protected preview URL, renders pages into stable containers, and exposes zoom/rotation/page controls. Assert that the DOCX renderer fetches the preview URL as an ArrayBuffer and invokes the local docx renderer into a sandboxed container.

- [ ] **Step 2: Run the focused tests and verify red**

Run: `python -m unittest tests.test_document_viewers -v`

Expected: FAIL with missing renderer functions/assets.

- [ ] **Step 3: Implement PDF renderer**

Use `pdfjsLib.getDocument({url})` with `GlobalWorkerOptions.workerSrc` pointing to the local worker. Render each page to a canvas with device-pixel-ratio capped for mobile memory. Keep current page, scale and rotation in viewer state; re-render after each control action.

- [ ] **Step 4: Implement DOCX renderer**

Fetch the preview URL with credentials, pass the response buffer to `docx.renderAsync`, render into a container with a strict class/style boundary, and show parse errors without replacing the rest of the dashboard.

- [ ] **Step 5: Implement fallback branches**

For `.doc`, XT, unknown CAD formats and failed library loading, show a Chinese explanatory status and a download action. Do not call `window.open` for supported or fallback files.

- [ ] **Step 6: Run focused and full Python tests**

Run:
`python -m unittest tests.test_document_viewers -v`
`python -m unittest discover -s tests -v`

Expected: all tests PASS.

- [ ] **Step 7: Commit document viewer**

Run:
`git add static/js/file-viewers.js templates/dashboard.html static/css/style.css tests/test_document_viewers.py`
`git commit -m "feat: add in-app PDF and DOCX viewers"`

---

### Task 5: Implement STP/STEP WebGL viewer test-first

**Files:**
- Modify: `static/js/file-viewers.js`
- Modify: `templates/dashboard.html`
- Modify: `static/css/style.css`
- Test: `tests/test_document_viewers.py`

- [ ] **Step 1: Add CAD renderer contract assertions**

Assert that the CAD renderer loads local Three.js, OrbitControls, and occt-import-js resources, fetches the protected preview URL, initializes a WebGL renderer, parses STEP data, and exposes reset plus display-mode controls.

- [ ] **Step 2: Run the focused test and verify red**

Run: `python -m unittest tests.test_document_viewers -v`

Expected: FAIL because the CAD renderer is not implemented.

- [ ] **Step 3: Implement the minimal STEP renderer**

Fetch the response as an ArrayBuffer, initialize occt-import-js with the local WASM path, call the STEP reader, convert returned meshes to Three.js geometry/materials, add them to a scene, and attach OrbitControls. Use requestAnimationFrame only while the viewer is open.

- [ ] **Step 4: Add interaction and cleanup**

Implement pointer/touch orbit, wheel/pinch zoom through OrbitControls, fit-to-view using model bounds, reset camera, solid/line display toggle, resize handling, and disposal of geometries/materials/renderer on close.

- [ ] **Step 5: Run all tests**

Run: `python -m unittest discover -s tests -v`

Expected: all tests PASS.

- [ ] **Step 6: Commit CAD viewer**

Run:
`git add static/js/file-viewers.js templates/dashboard.html static/css/style.css tests/test_document_viewers.py`
`git commit -m "feat: add in-app STEP viewer"`

---

### Task 6: Wire all existing file and drawing entry points

**Files:**
- Modify: `templates/dashboard.html`
- Modify: `static/js/file-viewers.js`
- Test: `tests/test_document_viewers.py`

- [ ] **Step 1: Add entry-point tests**

Assert that both `previewFile` and `previewDrawing` pass file metadata and protected URLs into `openFileViewer` for PDF, DOCX, STP and STEP. Assert that images keep the existing image modal and that ordinary unsupported files retain download behavior.

- [ ] **Step 2: Run tests and verify red**

Run: `python -m unittest tests.test_document_viewers -v`

Expected: FAIL because the existing functions still open preview URLs in a new window.

- [ ] **Step 3: Replace only supported branches**

Route supported files through the unified viewer and retain existing image and generic download behavior. Keep drawing IDs and file IDs intact so permissions and downloads are unchanged.

- [ ] **Step 4: Run all tests**

Run: `python -m unittest discover -s tests -v`

Expected: all tests PASS.

- [ ] **Step 5: Commit entry-point integration**

Run:
`git add templates/dashboard.html static/js/file-viewers.js tests/test_document_viewers.py`
`git commit -m "feat: route project files to in-app viewers"`

---

### Task 7: Bump synchronized release version

**Files:**
- Modify: `VERSION`
- Modify: `static/manifest.webmanifest`
- Modify: `static/service-worker.js`
- Modify: `android-xinggui/app/src/main/AndroidManifest.xml`
- Modify: `tests/test_xinggui_mobile_app.py`

- [ ] **Step 1: Update release expectations first**

Change test expectations to `APP_VERSION == "1.0.6"`, Android `versionCode == "7"`, web manifest version `1.0.6`, and service worker cache key `xinggui-pwa-1.0.6`. Run the focused version tests and confirm they fail.

- [ ] **Step 2: Update the shared version files**

Set `VERSION` to `1.0.6`, web manifest version to `1.0.6`, service worker cache to `xinggui-pwa-1.0.6`, and Android manifest attributes to `versionCode="7"` and `versionName="1.0.6"`.

- [ ] **Step 3: Verify version tests**

Run: `python -m unittest tests.test_xinggui_mobile_app -v`

Expected: PASS, including the existing build-script consistency check.

- [ ] **Step 4: Commit release metadata**

Run:
`git add VERSION static/manifest.webmanifest static/service-worker.js android-xinggui/app/src/main/AndroidManifest.xml tests/test_xinggui_mobile_app.py`
`git commit -m "chore: bump release to 1.0.6"`

---

### Task 8: Deploy, build APK, and verify on desktop/mobile paths

**Files:**
- Modify: server copy of `/opt/mimoclaw/app`
- Create: desktop `星轨_1.0.6.apk` and `星轨.apk`

- [ ] **Step 1: Run the full test suite and static checks**

Run: `python -m unittest discover -s tests -v` and `git diff --check`. Expected: PASS and no whitespace errors.

- [ ] **Step 2: Deploy web files and viewer assets**

Use the existing SSH key to copy `app.py`, `templates/dashboard.html`, `static/css/style.css`, `static/js/file-viewers.js`, `static/vendor`, `VERSION`, `static/manifest.webmanifest`, and `static/service-worker.js` to `/opt/mimoclaw/app`, then restart `mimoclaw`.

- [ ] **Step 3: Verify the server**

Check `systemctl is-active mimoclaw`, `curl -I http://154.12.85.176/api/files/1/preview` while unauthenticated, and fetch the root HTML. Expected: service active, protected file route returns 302/401 rather than exposing a file, and the app reports version 1.0.6 after login.

- [ ] **Step 4: Build the Android APK**

Set the existing JDK 17 and Android SDK paths, run `android-xinggui/build-apk.ps1`, and verify the generated APK manifest reports `versionName='1.0.6'` and `versionCode='7'`.

- [ ] **Step 5: Copy release outputs**

Copy the verified APK to the desktop as `星轨.apk` and `星轨_1.0.6.apk`, and to `outputs/星轨_1.0.6.apk`.

- [ ] **Step 6: Commit any final verification-only corrections**

Run `git status --short`; only expected feature/version changes may remain. If a correction is necessary, add a focused test first, fix it, rerun the suite, and commit it.
