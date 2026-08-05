(function () {
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', function () {
      navigator.serviceWorker.register('/service-worker.js').catch(function () {});
    });
  }

  function closeSidebar(sidebar, toggle) {
    sidebar.classList.remove('mobile-open');
    toggle.setAttribute('aria-expanded', 'false');
  }

  function getCleanText(node) {
    return (node && node.textContent ? node.textContent : '').replace(/\s+/g, ' ').trim();
  }

  function enhanceMobileTables() {
    var wrappers = document.querySelectorAll('.table-wrapper');
    var isPhone = window.innerWidth <= 768;

    wrappers.forEach(function (wrapper) {
      var table = wrapper.querySelector('table');
      var existing = wrapper.querySelector('.mobile-card-list');
      if (!table || !isPhone) {
        if (existing) {
          existing.remove();
        }
        wrapper.removeAttribute('data-mobile-card-signature');
        return;
      }

      var headers = Array.prototype.slice.call(table.querySelectorAll('thead th')).map(getCleanText);
      var rows = Array.prototype.slice.call(table.querySelectorAll('tbody tr'));
      if (!headers.length || !rows.length) {
        if (existing) {
          existing.remove();
        }
        wrapper.removeAttribute('data-mobile-card-signature');
        return;
      }

      var signature = rows.map(function (row) {
        return getCleanText(row);
      }).join('|') + ':' + rows.length + ':' + headers.join('|');
      if (existing && wrapper.getAttribute('data-mobile-card-signature') === signature) {
        return;
      }
      if (existing) {
        existing.remove();
      }

      var list = document.createElement('div');
      list.className = 'mobile-card-list';

      rows.forEach(function (row) {
        var cells = Array.prototype.slice.call(row.children);
        var card = document.createElement('article');
        card.className = 'mobile-record-card';

        var title = document.createElement('div');
        title.className = 'mobile-record-title';
        title.textContent = getCleanText(cells[0]) || '记录';
        card.appendChild(title);

        if (cells[1] && getCleanText(cells[1])) {
          var subtitle = document.createElement('div');
          subtitle.className = 'mobile-record-subtitle';
          subtitle.textContent = getCleanText(cells[1]);
          card.appendChild(subtitle);
        }

        var fields = document.createElement('div');
        fields.className = 'mobile-record-fields';
        var actions = document.createElement('div');
        actions.className = 'mobile-record-actions';

        cells.forEach(function (cell, index) {
          var hasAction = cell.querySelector('button, a.btn, [onclick]');
          if (hasAction) {
            Array.prototype.slice.call(cell.children).forEach(function (child) {
              actions.appendChild(child.cloneNode(true));
            });
            return;
          }
          if (index < 2 || !getCleanText(cell)) {
            return;
          }

          var field = document.createElement('div');
          field.className = 'mobile-record-field';

          var label = document.createElement('span');
          label.className = 'mobile-record-label';
          label.textContent = headers[index] || '';

          var value = document.createElement('span');
          value.className = 'mobile-record-value';
          value.textContent = getCleanText(cell);

          field.appendChild(label);
          field.appendChild(value);
          fields.appendChild(field);
        });

        if (fields.children.length) {
          card.appendChild(fields);
        }
        if (actions.children.length) {
          card.appendChild(actions);
        }
        list.appendChild(card);
      });

      wrapper.appendChild(list);
      wrapper.setAttribute('data-mobile-card-signature', signature);
    });
  }

  function scheduleMobileEnhancement() {
    if (scheduleMobileEnhancement.pending) {
      return;
    }
    scheduleMobileEnhancement.pending = true;
    window.setTimeout(function () {
      scheduleMobileEnhancement.pending = false;
      enhanceMobileTables();
    }, 80);
  }

  document.addEventListener('DOMContentLoaded', function () {
    var loginForm = document.getElementById('loginForm');
    if (loginForm && window.XingguiNative && window.XingguiNative.hasSavedLogin && window.XingguiNative.hasSavedLogin()) {
      var submit = loginForm.querySelector('button[type="submit"]');
      var button = document.createElement('button');
      button.type = 'button';
      button.className = 'btn fingerprint-login-button';
      button.textContent = '指纹登录';
      button.addEventListener('click', function () {
        window.XingguiNative.requestFingerprintLogin();
      });
      if (submit && submit.parentNode) {
        submit.parentNode.appendChild(button);
      }
    }

    window.addEventListener('xinggui:credentials', function (event) {
      var detail = event.detail || {};
      var username = document.getElementById('username');
      var password = document.getElementById('password');
      if (!loginForm || !username || !password) {
        return;
      }
      username.value = detail.username || '';
      password.value = detail.password || '';
      if (loginForm.requestSubmit) {
        loginForm.requestSubmit();
      } else {
        loginForm.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
      }
    });

    enhanceMobileTables();
    window.addEventListener('resize', scheduleMobileEnhancement);
    if ('MutationObserver' in window) {
      var observerTarget = document.getElementById('page-content') || document.querySelector('.main-content') || document.body;
      new MutationObserver(scheduleMobileEnhancement).observe(observerTarget, {
        childList: true,
        subtree: true
      });
    }

    var toggle = document.querySelector('.mobile-nav-toggle');
    var sidebar = document.querySelector('.sidebar');
    if (!toggle || !sidebar) {
      return;
    }

    toggle.addEventListener('click', function () {
      var isOpen = sidebar.classList.toggle('mobile-open');
      toggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
    });

    document.addEventListener('click', function (event) {
      if (!sidebar.classList.contains('mobile-open')) {
        return;
      }
      if (sidebar.contains(event.target) || toggle.contains(event.target)) {
        return;
      }
      closeSidebar(sidebar, toggle);
    });

    sidebar.querySelectorAll('.nav-item').forEach(function (item) {
      item.addEventListener('click', function () {
        closeSidebar(sidebar, toggle);
      });
    });
  });
})();
