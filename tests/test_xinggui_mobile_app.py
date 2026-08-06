import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class XingguiMobileAppTest(unittest.TestCase):
    def test_pwa_manifest_declares_xinggui_mobile_app(self):
        manifest = json.loads((ROOT / "static" / "manifest.webmanifest").read_text(encoding="utf-8"))

        self.assertEqual(manifest["name"], "星轨")
        self.assertEqual(manifest["short_name"], "星轨")
        self.assertEqual(manifest["start_url"], "/")
        self.assertEqual(manifest["display"], "standalone")
        self.assertEqual(manifest["theme_color"], "#10B981")
        self.assertIn({"src": "/static/icons/app-icon-192.png", "sizes": "192x192", "type": "image/png"}, manifest["icons"])
        self.assertIn({"src": "/static/icons/app-icon-512.png", "sizes": "512x512", "type": "image/png"}, manifest["icons"])

    def test_templates_register_pwa_assets(self):
        login = (ROOT / "templates" / "login.html").read_text(encoding="utf-8")
        dashboard = (ROOT / "templates" / "dashboard.html").read_text(encoding="utf-8")

        for html in (login, dashboard):
            self.assertIn('rel="manifest"', html)
            self.assertIn('name="theme-color"', html)
            self.assertIn('/static/js/pwa.js', html)

    def test_app_serves_root_scope_service_worker(self):
        app_py = (ROOT / "app.py").read_text(encoding="utf-8")

        self.assertIn("@app.route('/manifest.webmanifest')", app_py)
        self.assertIn("@app.route('/service-worker.js')", app_py)
        self.assertIn("send_from_directory", app_py)

    def test_mobile_styles_exist_for_app_shell(self):
        css = (ROOT / "static" / "css" / "style.css").read_text(encoding="utf-8")

        self.assertIn("@media (max-width: 768px)", css)
        self.assertIn(".mobile-app-bar", css)
        self.assertIn(".mobile-nav-toggle", css)
        self.assertIn(".sidebar.mobile-open", css)

    def test_android_wrapper_targets_server_and_uses_xinggui_name(self):
        manifest = (ROOT / "android-xinggui" / "app" / "src" / "main" / "AndroidManifest.xml").read_text(encoding="utf-8")
        strings = (ROOT / "android-xinggui" / "app" / "src" / "main" / "res" / "values" / "strings.xml").read_text(encoding="utf-8")
        activity = (ROOT / "android-xinggui" / "app" / "src" / "main" / "java" / "com" / "xinggui" / "app" / "MainActivity.java").read_text(encoding="utf-8")

        self.assertIn('android:label="@string/app_name"', manifest)
        self.assertIn('android:usesCleartextTraffic="true"', manifest)
        self.assertIn("android.permission.INTERNET", manifest)
        self.assertIn("<string name=\"app_name\">星轨</string>", strings)
        self.assertIn('WEB_APP_URL = "http://154.12.85.176/"', activity)
        self.assertIn("setJavaScriptEnabled(true)", activity)
        self.assertIn("setDomStorageEnabled(true)", activity)
        self.assertIn("new WebViewClient()", activity)

    def test_android_wrapper_uses_system_auth_for_local_credential_login(self):
        manifest = (ROOT / "android-xinggui" / "app" / "src" / "main" / "AndroidManifest.xml").read_text(encoding="utf-8")
        activity = (ROOT / "android-xinggui" / "app" / "src" / "main" / "java" / "com" / "xinggui" / "app" / "MainActivity.java").read_text(encoding="utf-8")

        self.assertIn("android.permission.USE_BIOMETRIC", manifest)
        self.assertIn("android.permission.USE_FINGERPRINT", manifest)
        self.assertIn("@JavascriptInterface", activity)
        self.assertIn("enableCredentialLogin", activity)
        self.assertIn("requestFingerprintLogin", activity)
        self.assertIn("AndroidKeyStore", activity)
        self.assertIn("setUserAuthenticationRequired(true)", activity)
        self.assertIn("BiometricPrompt", activity)
        self.assertIn("xinggui:credentials", activity)

    def test_android_wrapper_requires_fresh_login_after_background_resume(self):
        activity = (ROOT / "android-xinggui" / "app" / "src" / "main" / "java" / "com" / "xinggui" / "app" / "MainActivity.java").read_text(encoding="utf-8")

        self.assertIn("protected void onStop()", activity)
        self.assertIn("protected void onResume()", activity)
        self.assertIn("requireFreshLogin()", activity)
        self.assertIn("removeSessionCookies", activity)
        self.assertIn('WEB_APP_URL + "login"', activity)

    def test_android_wrapper_does_not_prompt_again_after_fingerprint_enrolled(self):
        activity = (ROOT / "android-xinggui" / "app" / "src" / "main" / "java" / "com" / "xinggui" / "app" / "MainActivity.java").read_text(encoding="utf-8")
        login = (ROOT / "templates" / "login.html").read_text(encoding="utf-8")

        self.assertIn("if (hasSavedLogin())", activity)
        self.assertIn("return;", activity[activity.index("enableCredentialLogin"):activity.index("requestFingerprintLogin")])
        self.assertIn("hasSavedLogin()", login)

    def test_web_login_exposes_fingerprint_login_for_android_shell(self):
        login = (ROOT / "templates" / "login.html").read_text(encoding="utf-8")
        pwa_js = (ROOT / "static" / "js" / "pwa.js").read_text(encoding="utf-8")

        self.assertIn("enableCredentialLogin", login)
        self.assertIn("fingerprint-login-button", pwa_js)
        self.assertIn("requestFingerprintLogin", pwa_js)
        self.assertIn("xinggui:credentials", pwa_js)

    def test_mobile_styles_use_phone_first_proportions(self):
        css = (ROOT / "static" / "css" / "style.css").read_text(encoding="utf-8")

        self.assertIn("@media (max-width: 480px)", css)
        self.assertIn("min-height: 48px", css)
        self.assertIn(".modal.mobile-bottom-sheet", css)
        self.assertIn("grid-template-columns: repeat(2, minmax(0, 1fr))", css)

    def test_mobile_tables_render_as_cards_on_phone(self):
        css = (ROOT / "static" / "css" / "style.css").read_text(encoding="utf-8")
        pwa_js = (ROOT / "static" / "js" / "pwa.js").read_text(encoding="utf-8")

        self.assertIn("enhanceMobileTables", pwa_js)
        self.assertIn("MutationObserver", pwa_js)
        self.assertIn("mobile-card-list", pwa_js)
        self.assertIn("mobile-record-card", pwa_js)
        self.assertIn(".mobile-card-list", css)
        self.assertIn(".mobile-record-card", css)
        self.assertIn(".mobile-record-actions", css)
        self.assertIn(".table-wrapper table", css)

    def test_mobile_table_actions_keep_real_click_handlers_on_phone_cards(self):
        pwa_js = (ROOT / "static" / "js" / "pwa.js").read_text(encoding="utf-8")

        self.assertIn("cloneNode(true)", pwa_js)
        self.assertIn("clone.setAttribute('type', 'button')", pwa_js)
        self.assertNotIn("source.click()", pwa_js)
        self.assertNotIn("event.target.closest", pwa_js)

    def test_page_navigation_uses_smooth_web_layer_transitions(self):
        css = (ROOT / "static" / "css" / "style.css").read_text(encoding="utf-8")
        app_js = (ROOT / "static" / "js" / "app.js").read_text(encoding="utf-8")

        self.assertIn("PAGE_TRANSITION_MS", app_js)
        self.assertIn("page-transition-out", app_js)
        self.assertIn("page-transition-in", app_js)
        self.assertIn("prefers-reduced-motion", app_js)
        self.assertIn(".page-transition-out", css)
        self.assertIn(".page-transition-in", css)
        self.assertIn("@keyframes pageEnter", css)
        self.assertIn("@media (prefers-reduced-motion: reduce)", css)

    def test_page_transitions_do_not_disable_clicks_on_content(self):
        css = (ROOT / "static" / "css" / "style.css").read_text(encoding="utf-8")
        app_js = (ROOT / "static" / "js" / "app.js").read_text(encoding="utf-8")

        self.assertNotIn("pointer-events: none;", css)
        self.assertIn("try {", app_js)
        self.assertIn("finally", app_js)

    def test_service_worker_cache_version_updates_for_animation_assets(self):
        service_worker = (ROOT / "static" / "service-worker.js").read_text(encoding="utf-8")

        self.assertIn("xinggui-pwa-v4", service_worker)

    def test_android_wrapper_refreshes_web_assets_after_mobile_click_fixes(self):
        activity = (ROOT / "android-xinggui" / "app" / "src" / "main" / "java" / "com" / "xinggui" / "app" / "MainActivity.java").read_text(encoding="utf-8")

        self.assertIn("settings.setCacheMode(WebSettings.LOAD_NO_CACHE)", activity)
        self.assertIn("webView.clearCache(true)", activity)


if __name__ == "__main__":
    unittest.main()
