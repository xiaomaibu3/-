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
