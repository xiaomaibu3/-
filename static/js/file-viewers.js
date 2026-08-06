(function (root) {
    'use strict';

    const state = {
        file: null,
        viewerType: null,
        objectUrl: null,
        cleanup: []
    };
    const supported = { pdf: 'pdf', docx: 'word', stp: 'cad', step: 'cad' };
    const unsupported = new Set(['doc', 'x_t', 'x_b']);
    const localViewerAssets = [
        '/static/vendor/pdfjs/pdf.mjs', '/static/vendor/pdfjs/pdf.worker.mjs',
        '/static/vendor/docx-preview/docx-preview.min.js', '/static/vendor/jszip/jszip.min.js',
        '/static/vendor/three/three.module.min.js', '/static/vendor/three/three.core.min.js',
        '/static/vendor/three/examples/jsm/controls/OrbitControls.js',
        '/static/vendor/occt-import-js/occt-import-js.js', '/static/vendor/occt-import-js/occt-import-js.wasm'
    ];
    const hooks = root.window && root.window.XingguiViewerTestHooks;

    function element(id) {
        return root.document && root.document.getElementById(id);
    }

    function setText(id, value) {
        const target = element(id);
        if (target) target.textContent = value;
    }

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

    function downloadTarget(file) {
        return file && (file.downloadUrl || file.downloadURL || file.url || '');
    }

    function clearRenderer(type) {
        const target = element(`${type}-viewer`);
        if (target) {
            target.innerHTML = '';
            setVisible(target, false);
            target.removeAttribute && target.removeAttribute('data-file-name');
            target.removeAttribute && target.removeAttribute('data-preview-url');
        }
    }

    function resetFileViewer() {
        state.cleanup.splice(0).forEach(cleanup => {
            try { cleanup(); } catch (error) { /* renderer cleanup is best effort */ }
        });
        Object.values(supported).filter((type, index, types) => types.indexOf(type) === index).forEach(clearRenderer);
        if (state.objectUrl && root.URL && root.URL.revokeObjectURL) root.URL.revokeObjectURL(state.objectUrl);
        state.objectUrl = null;
        state.file = null;
        state.viewerType = null;
        const modal = element('file-viewer-modal');
        setVisible(modal, false);
        if (modal && modal.dataset) {
            delete modal.dataset.viewerType;
            delete modal.dataset.state;
        }
    }

    function setState(nextState) {
        const modal = element('file-viewer-modal');
        if (modal && modal.dataset) {
            modal.dataset.viewerType = state.viewerType || '';
            modal.dataset.state = nextState;
        }
        setText('file-viewer-status', nextState === 'loading' ? '正在加载...' : nextState === 'error' ? '预览加载失败' : '');
        if (hooks && hooks.setViewerState) hooks.setViewerState({ viewerType: state.viewerType || '', state: nextState });
    }

    function showFallback(message) {
        setState('error');
        setText('file-viewer-status', message);
        const download = element('file-viewer-download');
        if (download) {
            download.hidden = false;
            download.href = downloadTarget(state.file);
            download.onclick = downloadFileViewerSource;
        }
        if (hooks && hooks.setFallback) hooks.setFallback(message, state.file);
    }

    async function openFileViewer(file) {
        resetFileViewer();
        state.file = file || {};
        const ext = extension(state.file);
        state.viewerType = supported[ext] || null;
        const modal = element('file-viewer-modal');
        setVisible(modal, true);
        setText('file-viewer-title', state.file.fileName || state.file.name || '文件预览');
        const download = element('file-viewer-download');
        if (download) {
            download.href = downloadTarget(state.file);
            download.hidden = false;
            download.onclick = downloadFileViewerSource;
        }
        if (unsupported.has(ext)) {
            showFallback(`暂不支持 .${ext} 文件预览，请下载原文件查看。`);
            return state;
        }
        if (!state.viewerType) {
            showFallback('暂不支持此文件格式预览，请下载原文件查看。');
            return state;
        }
        setState('loading');
        const target = element(`${state.viewerType}-viewer`);
        if (target) setVisible(target, true);
        if (hooks && hooks.setViewerContent) {
            const cleanup = hooks.setViewerContent(state.viewerType, state.file);
            if (typeof cleanup === 'function') state.cleanup.push(cleanup);
        }
        if (target && target.dataset) {
            target.dataset.fileName = state.file.fileName || state.file.name || '';
            target.dataset.previewUrl = state.file.previewUrl || '';
        }
        setState('ready');
        return state;
    }

    function closeFileViewer() { resetFileViewer(); }

    function downloadFileViewerSource(event) {
        const target = downloadTarget(state.file);
        if (!target) return false;
        const link = element('file-viewer-download');
        if (link) link.href = target;
        if (!event && root.location && root.location.assign) root.location.assign(target);
        return true;
    }

    root.openFileViewer = openFileViewer;
    root.closeFileViewer = closeFileViewer;
    root.resetFileViewer = resetFileViewer;
    root.downloadFileViewerSource = downloadFileViewerSource;
    if (root.window) {
        root.window.openFileViewer = openFileViewer;
        root.window.closeFileViewer = closeFileViewer;
        root.window.resetFileViewer = resetFileViewer;
        root.window.downloadFileViewerSource = downloadFileViewerSource;
    }
    if (root.module && root.module.exports) root.module.exports = { openFileViewer, closeFileViewer, resetFileViewer, downloadFileViewerSource };
})(typeof globalThis !== 'undefined' ? globalThis : window);
