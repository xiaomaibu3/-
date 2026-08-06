(function (root) {
    'use strict';

    const state = { file: null, viewerType: null, target: null, objectUrl: null, cleanup: [], previousFocus: null, modalListener: null, generation: 0 };
    const supported = { pdf: 'pdf', docx: 'word', stp: 'cad', step: 'cad' };
    const unsupported = new Set(['doc', 'x_t', 'x_b']);
    const renderers = Object.create(null);
    const localViewerAssets = [
        '/static/vendor/pdfjs/pdf.mjs', '/static/vendor/pdfjs/pdf.worker.mjs',
        '/static/vendor/docx-preview/docx-preview.min.js', '/static/vendor/jszip/jszip.min.js',
        '/static/vendor/three/three.module.min.js', '/static/vendor/three/three.core.min.js',
        '/static/vendor/three/examples/jsm/controls/OrbitControls.js',
        '/static/vendor/occt-import-js/occt-import-js.js', '/static/vendor/occt-import-js/occt-import-js.wasm'
    ];

    function element(id) { return root.document && root.document.getElementById(id); }
    function currentHooks() { return root.window && root.window.XingguiViewerTestHooks; }
    function setText(id, value) { const target = element(id); if (target) target.textContent = value; }
    function setVisible(target, visible) {
        if (!target) return;
        target.hidden = !visible;
        if (target.classList && target.classList.toggle) target.classList.toggle('active', visible);
        if (target.style) target.style.display = visible ? 'flex' : 'none';
    }
    function extension(file) {
        const name = file && (file.fileName || file.name || '');
        return String(file && file.extension || name.split('.').pop() || '').replace(/^\./, '').toLowerCase();
    }
    function downloadTarget(file) { return file && (file.downloadUrl || file.downloadURL || file.url || ''); }
    function uniqueViewerTypes() { return Object.values(supported).filter((type, index, types) => types.indexOf(type) === index); }
    function clearRenderer(type) {
        const target = element(`${type}-viewer`);
        if (!target) return;
        if (target.innerHTML !== undefined) target.innerHTML = '';
        target.innerHTML = '';
        setVisible(target, false);
        if (target.removeAttribute) {
            target.removeAttribute('data-file-name');
            target.removeAttribute('data-preview-url');
        }
    }
    function setState(nextState) {
        const modal = element('file-viewer-modal');
        if (modal && modal.dataset) {
            modal.dataset.viewerType = state.viewerType || '';
            modal.dataset.state = nextState;
        }
        setText('file-viewer-status', nextState === 'loading' ? 'Loading...' : nextState === 'error' ? 'Preview failed' : '');
        const hooks = currentHooks();
        if (hooks && hooks.setViewerState) hooks.setViewerState({ viewerType: state.viewerType || '', state: nextState });
    }
    function focusables() {
        const modal = element('file-viewer-modal');
        if (!modal || !modal.querySelectorAll) return [];
        return Array.from(modal.querySelectorAll('a[href],button:not([disabled]),[tabindex]:not([tabindex="-1"])')).filter(item => !item.hidden);
    }
    function trapFocus(event) {
        if (event.key !== 'Tab') return;
        const items = focusables();
        if (!items.length) return;
        const first = items[0];
        const last = items[items.length - 1];
        if (event.shiftKey && root.document.activeElement === first) { event.preventDefault(); last.focus(); }
        else if (!event.shiftKey && root.document.activeElement === last) { event.preventDefault(); first.focus(); }
    }
    function attachFocusTrap() {
        const modal = element('file-viewer-modal');
        if (!modal || !modal.addEventListener) return;
        state.modalListener = trapFocus;
        modal.addEventListener('keydown', state.modalListener);
    }
    function showFallback(message) {
        setState('error');
        setText('file-viewer-status', message);
        const download = element('file-viewer-download');
        if (download) { download.hidden = false; download.href = downloadTarget(state.file); download.onclick = downloadFileViewerSource; }
        const hooks = currentHooks();
        if (hooks && hooks.setFallback) hooks.setFallback(message, state.file);
    }
    function resetFileViewer(restoreFocus = true) {
        state.generation += 1;
        if (state.target && state.target.parentNode && state.target.parentNode.removeChild) state.target.parentNode.removeChild(state.target);
        state.target = null;
        state.cleanup.splice(0).forEach(cleanup => { try { cleanup(); } catch (error) {} });
        if (state.modalListener) {
            const modal = element('file-viewer-modal');
            if (modal && modal.removeEventListener) modal.removeEventListener('keydown', state.modalListener);
        }
        uniqueViewerTypes().forEach(clearRenderer);
        if (state.objectUrl && root.URL && root.URL.revokeObjectURL) root.URL.revokeObjectURL(state.objectUrl);
        state.objectUrl = null;
        const download = element('file-viewer-download');
        if (download) { download.hidden = true; download.href = ''; download.onclick = null; }
        setText('file-viewer-status', '');
        const modal = element('file-viewer-modal');
        setVisible(modal, false);
        if (modal && modal.dataset) { delete modal.dataset.viewerType; delete modal.dataset.state; }
        const previousFocus = state.previousFocus;
        state.file = null; state.viewerType = null; state.modalListener = null; state.previousFocus = null;
        if (restoreFocus && previousFocus && previousFocus.focus) previousFocus.focus();
    }
    function rendererResult(result) {
        if (typeof result === 'function') return { cleanup: result };
        return result || {};
    }
    function disposeRendererResult(rendered) {
        if (rendered.cleanup) { try { rendered.cleanup(); } catch (error) {} }
        if (rendered.objectUrl && root.URL && root.URL.revokeObjectURL) root.URL.revokeObjectURL(rendered.objectUrl);
    }
    function isCurrentRequest(generation, file) {
        return state.generation === generation && state.file === file && state.target && state.target.dataset.viewerGeneration === String(generation);
    }
    function createTarget(type, generation) {
        const host = element(`${type}-viewer`);
        const target = root.document && root.document.createElement ? root.document.createElement('div') : { dataset: {}, style: {}, hidden: false, innerHTML: '' };
        target.className = 'file-viewer-generation';
        target.dataset.viewerGeneration = String(generation);
        if (host && host.appendChild) host.appendChild(target);
        return target;
    }
    async function openFileViewer(file) {
        const modalWasOpen = Boolean(state.file);
        const opener = modalWasOpen ? state.previousFocus : root.document && root.document.activeElement;
        resetFileViewer(false);
        state.previousFocus = opener;
        state.file = file || {};
        const requestFile = state.file;
        const requestGeneration = state.generation;
        const ext = extension(state.file);
        state.viewerType = supported[ext] || null;
        const modal = element('file-viewer-modal');
        setVisible(modal, true);
        setText('file-viewer-title', state.file.fileName || state.file.name || '文件预览');
        const download = element('file-viewer-download');
        if (download) { download.hidden = false; download.href = downloadTarget(state.file); download.onclick = downloadFileViewerSource; }
        attachFocusTrap();
        const focusModal = element('file-viewer-modal');
        const close = element('file-viewer-close');
        if (close && close.focus) close.focus();
        if (unsupported.has(ext)) { showFallback(`Unsupported .${ext} file. Download the source.`); return state; }
        if (!state.viewerType) { showFallback('Unsupported file type. Download the source.'); return state; }
        setState('loading');
        const target = element(`${state.viewerType}-viewer`);
        const renderTarget = createTarget(state.viewerType, requestGeneration);
        state.target = renderTarget;
        if (target) setVisible(target, true);
        const hooks = currentHooks();
        try {
            const registeredRenderer = renderers[state.viewerType];
            const renderer = registeredRenderer || (hooks && hooks.setViewerContent);
            if (!renderer) { showFallback('Viewer not ready. Download the source.'); return state; }
            const result = registeredRenderer ? renderer(renderTarget, state.file) : renderer(state.viewerType, state.file);
            const rendered = rendererResult(await Promise.resolve(result));
            if (!isCurrentRequest(requestGeneration, requestFile)) { disposeRendererResult(rendered); return state; }
            if (rendered.cleanup) state.cleanup.push(rendered.cleanup);
            if (rendered.objectUrl) state.objectUrl = rendered.objectUrl;
            if (target && target.dataset) { target.dataset.fileName = state.file.fileName || state.file.name || ''; target.dataset.previewUrl = state.file.previewUrl || ''; }
            setState('ready');
        } catch (error) {
            if (isCurrentRequest(requestGeneration, requestFile)) showFallback('Preview failed. Download the source.');
        }
        return state;
    }
    function closeFileViewer() { resetFileViewer(); }
    function downloadFileViewerSource() { const target = downloadTarget(state.file); const link = element('file-viewer-download'); if (link) link.href = target || ''; return Boolean(target); }
    function registerFileViewerRenderer(type, renderer) { if (type && typeof renderer === 'function') renderers[type] = renderer; return renderer; }

    let pdfModulePromise;
    function loadPdfModule() {
        if (!pdfModulePromise) pdfModulePromise = import('/static/vendor/pdfjs/pdf.mjs');
        return pdfModulePromise;
    }
    function localPixelRatio() {
        const mobile = root.matchMedia && root.matchMedia('(max-width: 700px)').matches;
        return Math.min(Number(root.devicePixelRatio) || 1, mobile ? 1.5 : 2);
    }
    async function renderPdf(target, file) {
        const response = await root.fetch(file.previewUrl, { credentials: 'include' });
        if (!response.ok) throw new Error('PDF preview request failed');
        const bytes = await response.arrayBuffer();
        const pdfjs = await loadPdfModule();
        pdfjs.GlobalWorkerOptions.workerSrc = '/static/vendor/pdfjs/pdf.worker.mjs';
        const loadingTask = pdfjs.getDocument({ data: bytes });
        const pdf = await loadingTask.promise;
        const controls = element('pdf-viewer-controls');
        const pageLabel = element('pdf-page-number');
        const pageCount = element('pdf-page-count');
        const renderTasks = new Set();
        const pages = root.document.createElement('div');
        pages.className = 'pdf-pages';
        target.appendChild(pages);
        let scale = 1;
        let rotation = 0;
        let fitWidth = false;
        let currentPage = 1;
        let drawGeneration = 0;
        let drawQueue = Promise.resolve();
        let disposed = false;
        function cancelRenderTasks() {
            renderTasks.forEach(renderTask => { try { renderTask.cancel(); } catch (error) {} });
            renderTasks.clear();
        }
        async function draw() {
            const generation = ++drawGeneration;
            cancelRenderTasks();
            pages.innerHTML = '';
            if (pageLabel) pageLabel.value = String(currentPage);
            if (pageCount) pageCount.textContent = `/ ${pdf.numPages}`;
            const pageNumbers = [currentPage];
            for (const pageNumber of pageNumbers) {
                if (disposed || generation !== drawGeneration) return;
                const page = await pdf.getPage(pageNumber);
                if (disposed || generation !== drawGeneration) return;
                let viewport = page.getViewport({ scale, rotation });
                if (fitWidth) {
                    const width = target.clientWidth || 900;
                    scale = Math.max(0.25, (width - 24) / viewport.width * scale);
                    viewport = page.getViewport({ scale, rotation });
                }
                const canvas = root.document.createElement('canvas');
                canvas.className = 'pdf-viewer-page';
                const ratio = localPixelRatio();
                canvas.width = Math.floor(viewport.width * ratio);
                canvas.height = Math.floor(viewport.height * ratio);
                canvas.style.width = `${viewport.width}px`;
                canvas.style.height = `${viewport.height}px`;
                pages.appendChild(canvas);
                const renderTask = page.render({ canvasContext: canvas.getContext('2d'), viewport, transform: ratio === 1 ? null : [ratio, 0, 0, ratio, 0, 0] });
                renderTasks.add(renderTask);
                try { await renderTask.promise; } catch (error) { if (error && error.name !== 'RenderingCancelledException') throw error; }
                finally { renderTasks.delete(renderTask); }
            }
            if (disposed || generation !== drawGeneration) return;
            if (pageLabel) pageLabel.value = String(currentPage);
        }
        function queueDraw() {
            drawGeneration += 1;
            cancelRenderTasks();
            drawQueue = drawQueue.catch(() => {}).then(() => draw()).catch(error => {
                if (!disposed) throw error;
            });
            return drawQueue;
        }
        function setPage(value) { currentPage = Math.min(Math.max(Number(value) || 1, 1), pdf.numPages); return queueDraw(); }
        function listen(id, handler, eventName = 'click') {
            const button = element(id);
            if (button && button.addEventListener) button.addEventListener(eventName, handler);
            return () => button && button.removeEventListener && button.removeEventListener(eventName, handler);
        }
        const cleanups = [
            listen('pdf-page-prev', () => setPage(currentPage - 1)),
            listen('pdf-page-next', () => setPage(currentPage + 1)),
            listen('pdf-page-number', event => setPage(event.target.value), 'input'),
            listen('pdf-zoom-in', () => { scale = Math.min(scale + 0.25, 4); fitWidth = false; return queueDraw(); }),
            listen('pdf-zoom-out', () => { scale = Math.max(scale - 0.25, 0.25); fitWidth = false; return queueDraw(); }),
            listen('pdf-rotate', () => { rotation = (rotation + 90) % 360; return queueDraw(); }),
            listen('pdf-fit-width', () => { fitWidth = true; return queueDraw(); }),
        ];
        const cleanup = () => { disposed = true; drawGeneration += 1; cancelRenderTasks(); try { loadingTask.destroy(); } catch (error) {} try { pdf.destroy(); } catch (error) {} cleanups.forEach(cleanupHandler => cleanupHandler()); if (controls) controls.hidden = true; };
        if (controls) controls.hidden = false;
        queueDraw().catch(error => { if (!disposed) { setState('error'); setText('file-viewer-status', 'Preview failed. Download the source.'); } });
        return { cleanup };
    }
    function sanitizeDocxHtml(html) {
        const template = root.document.createElement('template');
        template.innerHTML = html;
        template.content.querySelectorAll && template.content.querySelectorAll('*').forEach(node => {
            Array.from(node.attributes || []).forEach(attribute => {
                const name = attribute.name.toLowerCase();
                const value = attribute.value.trim().toLowerCase();
                if (name.startsWith('on*') || name.startsWith('on') || ['src', 'href', 'xlink:href'].includes(name) && /^(?:javascript:|data:|vbscript:|file:)/i.test(value)) node.removeAttribute(attribute.name);
                else if (['src', 'href', 'xlink:href'].includes(name) && value && !/^(?:https?:|\/|#|[^:]+$)/i.test(value)) node.removeAttribute(attribute.name);
            });
            if (node.tagName && ['SCRIPT', 'IFRAME', 'OBJECT', 'EMBED'].includes(node.tagName)) node.remove();
        });
        return template.innerHTML;
    }
    async function renderDocx(target, file) {
        const response = await root.fetch(file.previewUrl, { credentials: 'include' });
        if (!response.ok) throw new Error('DOCX preview request failed');
        const buffer = await response.arrayBuffer();
        if (!root.docx || typeof root.docx.renderAsync !== 'function') throw new Error('DOCX renderer unavailable');
        const staging = root.document.createElement('div');
        staging.className = 'docx-isolated-container';
        await root.docx.renderAsync(buffer, staging, null, { inWrapper: true, breakPages: true, ignoreWidth: false, ignoreHeight: false, useBase64URL: true, experimental: false, renderHeaders: true, renderFooters: true, renderFootnotes: true, renderEndnotes: true, debug: false, scripts: false });
        const iframe = root.document.createElement('iframe');
        iframe.className = 'docx-sandbox';
        iframe.setAttribute('sandbox', '');
        iframe.setAttribute('aria-label', 'DOCX preview');
        iframe.srcdoc = sanitizeDocxHtml(staging.innerHTML);
        target.appendChild(iframe);
        return { cleanup: () => { iframe.remove(); staging.innerHTML = ''; } };
    }
    if (typeof root.fetch === 'function') {
        registerFileViewerRenderer('pdf', renderPdf);
        registerFileViewerRenderer('word', renderDocx);
    }

    if (root.document && root.document.addEventListener) {
        root.document.addEventListener('keydown', event => {
            if (event.key === 'Escape' && state.file) closeFileViewer();
        });
    }

    Object.assign(root, { openFileViewer, closeFileViewer, resetFileViewer, downloadFileViewerSource, registerFileViewerRenderer });
    if (root.window) Object.assign(root.window, { openFileViewer, closeFileViewer, resetFileViewer, downloadFileViewerSource, registerFileViewerRenderer });
    if (root.module && root.module.exports) root.module.exports = { openFileViewer, closeFileViewer, resetFileViewer, downloadFileViewerSource, registerFileViewerRenderer };
})(typeof globalThis !== 'undefined' ? globalThis : window);
