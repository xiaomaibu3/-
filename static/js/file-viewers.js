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

    if (root.document && root.document.addEventListener) {
        root.document.addEventListener('keydown', event => {
            if (event.key === 'Escape' && state.file) closeFileViewer();
        });
    }

    Object.assign(root, { openFileViewer, closeFileViewer, resetFileViewer, downloadFileViewerSource, registerFileViewerRenderer });
    if (root.window) Object.assign(root.window, { openFileViewer, closeFileViewer, resetFileViewer, downloadFileViewerSource, registerFileViewerRenderer });
    if (root.module && root.module.exports) root.module.exports = { openFileViewer, closeFileViewer, resetFileViewer, downloadFileViewerSource, registerFileViewerRenderer };
})(typeof globalThis !== 'undefined' ? globalThis : window);
