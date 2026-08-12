"""Thin desktop client entrypoint for the deployed web app."""
import os
import time
import urllib.error
import urllib.request
import webbrowser


DEFAULT_DESKTOP_URL = "http://154.12.85.176/"


def wait_until_ready(url, timeout_seconds=20):
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=1).close()
            return True
        except (OSError, urllib.error.URLError):
            time.sleep(0.2)
    return False


def exit_process(code):
    os._exit(code)


def get_desktop_url():
    url = os.environ.get("MIMOCLAW_DESKTOP_URL", DEFAULT_DESKTOP_URL).strip()
    if not url:
        url = DEFAULT_DESKTOP_URL
    return url if url.endswith("/") else f"{url}/"


def main():
    url = get_desktop_url()

    if os.environ.get("MIMOCLAW_DESKTOP_SMOKE") == "1":
        ready = wait_until_ready(url)
        return exit_process(0 if ready else 1)

    try:
        import webview

        window = webview.create_window(
            "星轨",
            url,
            width=1280,
            height=820,
            min_size=(1024, 680),
        )
        webview.start()
        return 0 if window else 1
    except Exception:
        webbrowser.open(url)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
