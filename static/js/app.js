/**
 * 项目管理系统 - 前端核心 JS
 * SPA 风格，基于 fetch API 与后端交互
 */

// ── 工具函数 ──────────────────────────────────────────────────
const $ = (sel, ctx = document) => ctx.querySelector(sel);
const $$ = (sel, ctx = document) => [...ctx.querySelectorAll(sel)];

function toast(msg, type = 'success') {
    const container = $('.toast-container') || (() => {
        const d = document.createElement('div');
        d.className = 'toast-container';
        document.body.appendChild(d);
        return d;
    })();
    const el = document.createElement('div');
    el.className = `toast ${type}`;
    el.innerHTML = `<span>${msg}</span>`;
    container.appendChild(el);
    setTimeout(() => el.remove(), 3500);
}

async function api(url, options = {}) {
    const defaults = {
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin'
    };
    if (options.body && !(options.body instanceof FormData)) {
        options.body = JSON.stringify(options.body);
    } else if (options.body instanceof FormData) {
        delete defaults.headers['Content-Type'];
    }
    const res = await fetch(url, { ...defaults, ...options });
    if (res.status === 401) {
        window.location.href = '/login';
        return null;
    }
    const data = await res.json();
    if (data.error) {
        toast(data.error, 'error');
        return null;
    }
    return data;
}

function formatDate(str) {
    if (!str) return '-';
    const d = new Date(str);
    return d.toLocaleDateString('zh-CN');
}

function formatDateTime(str) {
    if (!str) return '-';
    const d = new Date(str);
    return d.toLocaleString('zh-CN');
}

function getBadgeClass(status) {
    const map = {
        '进行中': 'badge-info', '已完成': 'badge-success', '已暂停': 'badge-warning',
        '草稿': 'badge-gray', '待审批': 'badge-warning', '已通过': 'badge-success',
        '已驳回': 'badge-danger', '已发布': 'badge-success', '已归档': 'badge-gray',
        '正常': 'badge-success', '异常': 'badge-danger', '待核查': 'badge-warning',
    };
    return map[status] || 'badge-gray';
}

function showModal(id) {
    const modal = $(`#${id}`);
    if (modal) modal.classList.add('active');
}

function hideModal(id) {
    const modal = $(`#${id}`);
    if (modal) modal.classList.remove('active');
}

function showConfirmDialog({
    title = '请确认',
    message,
    confirmText = '确定',
    cancelText = '取消',
    danger = false
}) {
    return new Promise(resolve => {
        const modal = $('#modal-main');
        const panel = modal?.querySelector('.modal');
        const titleEl = $('#modal-title');
        const bodyEl = $('#modal-body');
        const footerEl = $('#modal-footer');

        if (!modal || !panel || !titleEl || !bodyEl || !footerEl) {
            resolve(false);
            return;
        }

        const finish = confirmed => {
            panel.classList.remove('confirm-dialog');
            hideModal('modal-main');
            resolve(confirmed);
        };

        panel.classList.add('confirm-dialog');
        titleEl.textContent = title;
        bodyEl.innerHTML = `<p class="confirm-message">${message}</p>`;
        footerEl.innerHTML = '';

        const cancelButton = document.createElement('button');
        cancelButton.type = 'button';
        cancelButton.className = 'btn';
        cancelButton.textContent = cancelText;
        cancelButton.addEventListener('click', () => finish(false));

        const confirmButton = document.createElement('button');
        confirmButton.type = 'button';
        confirmButton.className = `btn ${danger ? 'btn-danger' : 'btn-primary'}`;
        confirmButton.textContent = confirmText;
        confirmButton.addEventListener('click', () => finish(true));

        footerEl.append(cancelButton, confirmButton);
        showModal('modal-main');
        confirmButton.focus();
    });
}

// ── 页面路由 ──────────────────────────────────────────────────
const routes = {};
let currentPage = '';
const PAGE_TRANSITION_MS = 170;

function registerPage(name, renderFn) {
    routes[name] = renderFn;
}

function prefersReducedMotion() {
    return window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

function waitForTransition(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

async function renderPageContent(content, page, params, previousPage) {
    if (!routes[page]) return;

    if (prefersReducedMotion() || !previousPage || previousPage === page) {
        try {
            await routes[page](content, params);
        } finally {
            content.classList.remove('page-transition-out', 'page-transition-in');
        }
        return;
    }

    content.classList.remove('page-transition-in');
    content.classList.add('page-transition-out');
    try {
        await waitForTransition(PAGE_TRANSITION_MS);
        await routes[page](content, params);
        content.classList.remove('page-transition-out');
        content.classList.add('page-transition-in');
        window.setTimeout(() => content.classList.remove('page-transition-in'), PAGE_TRANSITION_MS + 80);
    } catch (error) {
        content.classList.remove('page-transition-out', 'page-transition-in');
        throw error;
    }
}

async function navigateTo(page, params = {}) {
    const previousPage = currentPage;
    currentPage = page;
    const content = $('#page-content');
    if (!content) return;

    // 更新导航高亮
    $$('.nav-item').forEach(el => el.classList.remove('active'));
    const navItem = $(`.nav-item[data-page="${page}"]`);
    if (navItem) navItem.classList.add('active');

    if (routes[page]) {
        await renderPageContent(content, page, params, previousPage);
    }
}

// ── 初始化 ──────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    document.addEventListener('keydown', event => {
        if (event.key === 'Escape' && typeof closeFileViewer === 'function') closeFileViewer();
    });
    // 导航点击
    $$('.nav-item[data-page]').forEach(el => {
        el.addEventListener('click', (e) => {
            e.preventDefault();
            navigateTo(el.dataset.page);
        });
    });

    // 默认页面
    const defaultPage = $('.nav-item.active')?.dataset?.page || 'dashboard';
    navigateTo(defaultPage);
});
