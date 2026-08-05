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
