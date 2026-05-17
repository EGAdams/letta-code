import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request


def ensure_dependencies():
    try:
        import flask  # noqa: F401
        import undetected_chromedriver  # noqa: F401
    except ModuleNotFoundError as exc:
        candidates = [
            os.environ.get("BROWSER_SERVER_PYTHON"),
            os.path.join(os.path.dirname(__file__), ".venv", "bin", "python3"),
            "/home/adamsl/planner/nonprofit_finance_db/receipt_scanning_tools/venv/bin/python3",
        ]

        for candidate in candidates:
            if not candidate or not os.path.exists(candidate):
                continue
            if os.path.abspath(candidate) == os.path.abspath(sys.executable):
                continue
            check = subprocess.run(
                [
                    candidate,
                    "-c",
                    "import flask, undetected_chromedriver",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            if check.returncode == 0:
                os.execvpe(candidate, [candidate, __file__, *sys.argv[1:]], os.environ)

        raise SystemExit(
            "Missing Python dependency "
            f"{exc.name!r}. Run with a Python environment that has Flask and "
            "undetected-chromedriver installed, or set BROWSER_SERVER_PYTHON "
            "to that Python executable."
        ) from exc


ensure_dependencies()

from flask import Flask, request, jsonify
import undetected_chromedriver as uc
from selenium import webdriver
from selenium.common.exceptions import (
    InvalidSessionIdException,
    SessionNotCreatedException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.chrome.options import Options as SeleniumChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains

app = Flask(__name__)
driver = None
fallback_profile_dir = None
startup_profile_dir = None
startup_browser_process = None
startup_browser_pid = None
startup_debugger_address = None
driver_lock = threading.Lock()


def default_user_data_dir():
    configured = os.environ.get("CHROME_USER_DATA_DIR")
    default_profile = os.path.expanduser("~/.config/google-chrome")
    browser_server_profile = os.path.expanduser("~/.config/google-chrome-browser-server")
    if configured and os.path.abspath(configured) != os.path.abspath(default_profile):
        return configured
    if configured:
        print(
            "CHROME_USER_DATA_DIR points at Chrome's default profile, which "
            "cannot be remote-debugged by this Chrome version; using "
            f"{browser_server_profile!r} instead.",
            flush=True,
        )
    return browser_server_profile


def allow_temporary_profile():
    return os.environ.get("BROWSER_SERVER_ALLOW_TEMP_PROFILE") == "1"


def chrome_version_main():
    configured = os.environ.get("CHROME_VERSION_MAIN")
    if configured:
        return int(configured)

    browser_path = os.environ.get("CHROME_BINARY")
    candidates = [browser_path] if browser_path else [
        shutil.which("google-chrome"),
        shutil.which("google-chrome-stable"),
        shutil.which("chromium"),
        shutil.which("chromium-browser"),
    ]

    for candidate in candidates:
        if not candidate:
            continue
        try:
            output = subprocess.check_output(
                [candidate, "--version"],
                text=True,
                stderr=subprocess.STDOUT,
                timeout=5,
            )
        except (OSError, subprocess.SubprocessError):
            continue

        match = re.search(r"\b(\d+)\.", output)
        if match:
            return int(match.group(1))

    return None


def chrome_binary():
    configured = os.environ.get("CHROME_BINARY")
    if configured:
        return configured

    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        path = shutil.which(name)
        if path:
            return path

    return None


def build_chrome_options(user_data_dir):
    options = uc.ChromeOptions()
    browser_path = chrome_binary()
    if browser_path:
        options.binary_location = browser_path

    options.add_argument(f"--user-data-dir={user_data_dir}")
    options.add_argument(f"--profile-directory={os.environ.get('CHROME_PROFILE', 'Default')}")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    return options


def create_driver(user_data_dir):
    if startup_debugger_address and debugger_is_ready(startup_debugger_address):
        return attach_to_startup_browser()

    kwargs = {"options": build_chrome_options(user_data_dir)}
    version_main = chrome_version_main()
    if version_main:
        kwargs["version_main"] = version_main
    return uc.Chrome(**kwargs)


def driver_session_is_alive(d):
    try:
        d.window_handles
        return True
    except (InvalidSessionIdException, WebDriverException) as exc:
        message = str(exc).lower()
        if isinstance(exc, InvalidSessionIdException) or "invalid session id" in message:
            return False
        raise


def attach_to_startup_browser():
    deadline = time.time() + int(os.environ.get("BROWSER_SERVER_ATTACH_TIMEOUT", "15"))
    version_url = f"http://{startup_debugger_address}/json/version"
    last_error = None

    while time.time() < deadline:
        try:
            with urllib.request.urlopen(version_url, timeout=1):
                break
        except (OSError, urllib.error.URLError) as exc:
            last_error = exc
            time.sleep(0.25)
    else:
        raise WebDriverException(
            f"Startup browser debugger did not become ready at {startup_debugger_address}: {last_error}"
        )

    close_non_page_debug_targets(startup_debugger_address)

    options = SeleniumChromeOptions()
    options.debugger_address = startup_debugger_address
    return webdriver.Chrome(options=options)


def debugger_is_ready(debugger_address):
    try:
        with urllib.request.urlopen(f"http://{debugger_address}/json/version", timeout=1):
            return True
    except (OSError, urllib.error.URLError):
        return False


def close_non_page_debug_targets(debugger_address):
    try:
        with urllib.request.urlopen(f"http://{debugger_address}/json/list", timeout=2) as response:
            targets = jsonify_loads(response.read().decode("utf-8", "replace"))
    except (OSError, urllib.error.URLError, ValueError):
        return

    page_target_id = next(
        (
            target.get("id")
            for target in targets
            if target.get("url", "").startswith(("http://", "https://"))
        ),
        None,
    )
    if page_target_id:
        try:
            urllib.request.urlopen(
                f"http://{debugger_address}/json/activate/{page_target_id}",
                timeout=1,
            ).close()
        except (OSError, urllib.error.URLError):
            pass

    closed_target = False
    for target in targets:
        url = target.get("url", "")
        target_id = target.get("id")
        if not target_id or not url.startswith("chrome://omnibox-popup"):
            continue
        try:
            urllib.request.urlopen(
                f"http://{debugger_address}/json/close/{target_id}",
                timeout=1,
            ).close()
            closed_target = True
        except (OSError, urllib.error.URLError):
            pass
    if closed_target:
        time.sleep(0.5)


def jsonify_loads(raw):
    import json

    return json.loads(raw)


def proc_cmdline(pid):
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as handle:
            return [part.decode("utf-8", "replace") for part in handle.read().split(b"\0") if part]
    except OSError:
        return []


def find_existing_debugger_address(user_data_dir):
    expected_user_data_arg = f"--user-data-dir={user_data_dir}"
    for entry in os.scandir("/proc"):
        if not entry.name.isdigit():
            continue
        args = proc_cmdline(entry.name)
        command_line = " ".join(args)
        if not args or expected_user_data_arg not in command_line:
            continue
        debug_port = None
        match = re.search(r"--remote-debugging-port=(\d+)", command_line)
        if match:
            debug_port = match.group(1)
        if not debug_port:
            continue
        debugger_address = f"127.0.0.1:{debug_port}"
        if debugger_is_ready(debugger_address):
            return int(entry.name), debugger_address
    return None, None


def close_driver():
    global driver, fallback_profile_dir, startup_browser_process, startup_profile_dir, startup_browser_pid
    if driver:
        driver.quit()
        driver = None
    if startup_browser_process and startup_browser_process.poll() is None:
        startup_browser_process.terminate()
        try:
            startup_browser_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            startup_browser_process.kill()
    startup_browser_process = None
    startup_browser_pid = None
    if fallback_profile_dir:
        shutil.rmtree(fallback_profile_dir, ignore_errors=True)
        fallback_profile_dir = None
    if startup_profile_dir:
        shutil.rmtree(startup_profile_dir, ignore_errors=True)
        startup_profile_dir = None


def singleton_paths(user_data_dir):
    return [
        os.path.join(user_data_dir, name)
        for name in ("SingletonLock", "SingletonSocket", "SingletonCookie")
    ]


def remove_stale_singletons(user_data_dir):
    lock_path = os.path.join(user_data_dir, "SingletonLock")
    try:
        target = os.readlink(lock_path)
    except OSError:
        return

    prefix = f"{subprocess.check_output(['hostname'], text=True).strip()}-"
    if not target.startswith(prefix):
        return

    try:
        pid = int(target.removeprefix(prefix))
    except ValueError:
        return

    try:
        os.kill(pid, 0)
        return
    except ProcessLookupError:
        pass
    except PermissionError:
        return

    for path in singleton_paths(user_data_dir):
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass


def profile_is_locked(user_data_dir):
    remove_stale_singletons(user_data_dir)
    return any(
        os.path.exists(path)
        for path in singleton_paths(user_data_dir)
    )


def usable_user_data_dir(configured_dir):
    global fallback_profile_dir
    if (
        os.environ.get("CHROME_ALLOW_LOCKED_PROFILE") != "1"
        and profile_is_locked(configured_dir)
    ):
        if not allow_temporary_profile():
            raise WebDriverException(
                "Chrome profile appears to be in use. Refusing to open a "
                "temporary profile because it will not have your saved login. "
                "Close the Chrome window using this profile, or set "
                "BROWSER_SERVER_ALLOW_TEMP_PROFILE=1 to opt in to a temporary "
                "logged-out browser."
            )
        fallback_profile_dir = tempfile.mkdtemp(prefix="browser-server-chrome-")
        print(
            "Chrome profile appears to be in use; using temporary profile "
            f"{fallback_profile_dir!r} instead of {configured_dir!r}. "
            "Close Chrome or set CHROME_ALLOW_LOCKED_PROFILE=1 to force it."
        )
        return fallback_profile_dir
    return configured_dir


def current_start_url():
    return os.environ.get("BROWSER_SERVER_START_URL", "https://chatgpt.com/")


def normalize_browser_window(d):
    try:
        d.set_window_rect(x=600, y=120, width=1000, height=800)
    except WebDriverException as exc:
        if "Browser window not found" not in str(exc):
            raise


def ensure_chatgpt_page(d):
    url = current_start_url()
    chatgpt_handle = None

    for handle in d.window_handles:
        try:
            d.switch_to.window(handle)
            if "chatgpt.com" in (d.current_url or ""):
                chatgpt_handle = handle
                break
        except WebDriverException:
            continue

    if chatgpt_handle:
        d.switch_to.window(chatgpt_handle)
        normalize_browser_window(d)
        return

    d.get(url)
    normalize_browser_window(d)


def find_prompt_element(d, timeout=20):
    selectors = [
        "#prompt-textarea",
        'div[contenteditable="true"]#prompt-textarea',
        'div.ProseMirror[contenteditable="true"]',
        'div[contenteditable="true"][data-placeholder]',
        'textarea[data-testid="prompt-textarea"]',
        "textarea",
    ]
    deadline = time.time() + timeout
    last_error = None

    while time.time() < deadline:
        for selector in selectors:
            try:
                elements = d.find_elements(By.CSS_SELECTOR, selector)
            except WebDriverException as exc:
                last_error = exc
                continue
            for el in elements:
                try:
                    if not el.is_displayed() or not el.is_enabled():
                        continue
                    rect = el.rect or {}
                    if rect.get("width", 0) <= 0 or rect.get("height", 0) <= 0:
                        continue
                    return el
                except WebDriverException as exc:
                    last_error = exc
                    continue
        time.sleep(0.25)

    raise TimeoutException(f"Could not find visible prompt element using selectors: {selectors}") from last_error


def get_driver():
    global driver, fallback_profile_dir, startup_browser_pid, startup_debugger_address
    with driver_lock:
        if driver is not None and not driver_session_is_alive(driver):
            try:
                driver.quit()
            except WebDriverException:
                pass
            driver = None

        if driver is None:
            user_data_dir = default_user_data_dir()
            existing_pid, existing_debugger_address = find_existing_debugger_address(user_data_dir)
            if existing_debugger_address:
                startup_browser_pid = existing_pid
                startup_debugger_address = existing_debugger_address
            else:
                user_data_dir = usable_user_data_dir(user_data_dir)
            try:
                driver = create_driver(user_data_dir)
            except (SessionNotCreatedException, WebDriverException) as exc:
                if not allow_temporary_profile():
                    raise WebDriverException(
                        "Chrome failed to start with the configured profile. "
                        "Refusing to retry with a temporary profile because it "
                        "will not have your saved login. Set "
                        "BROWSER_SERVER_ALLOW_TEMP_PROFILE=1 to opt in to a "
                        f"temporary logged-out browser. Original error: {exc}"
                    ) from exc
                fallback_profile_dir = tempfile.mkdtemp(prefix="browser-server-chrome-")
                print(
                    "Chrome failed to start with configured profile "
                    f"{user_data_dir!r}; retrying with temporary profile "
                    f"{fallback_profile_dir!r}. Original error: {exc}"
                )
                driver = create_driver(fallback_profile_dir)
            driver.set_page_load_timeout(int(os.environ.get("CHROME_PAGE_LOAD_TIMEOUT", "30")))
            try:
                normalize_browser_window(driver)
            except WebDriverException as exc:
                if "Browser window not found" not in str(exc):
                    raise
    return driver


def open_initial_url():
    global startup_browser_process, startup_profile_dir, startup_debugger_address, startup_browser_pid
    url = current_start_url()
    browser_path = chrome_binary()
    if not browser_path:
        print("No Chrome binary found for startup open.", file=sys.stderr)
        return

    debug_port = int(os.environ.get("BROWSER_SERVER_DEBUG_PORT", "0"))
    if debug_port == 0:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            debug_port = sock.getsockname()[1]
    startup_debugger_address = f"127.0.0.1:{debug_port}"

    def launch(user_data_dir):
        log_path = os.environ.get("BROWSER_SERVER_CHROME_LOG", "/tmp/browser-server-chrome.log")
        args = [
            browser_path,
            "--new-window",
            "--no-default-browser-check",
            "--no-first-run",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--remote-debugging-host=127.0.0.1",
            f"--remote-debugging-port={debug_port}",
            f"--user-data-dir={user_data_dir}",
            f"--profile-directory={os.environ.get('CHROME_PROFILE', 'Default')}",
            url,
        ]
        log_file = open(log_path, "ab")
        return subprocess.Popen(
            args,
            stdout=log_file,
            stderr=log_file,
            start_new_session=True,
        )

    configured_dir = default_user_data_dir()
    existing_pid, existing_debugger_address = find_existing_debugger_address(configured_dir)
    if existing_debugger_address:
        startup_browser_pid = existing_pid
        startup_debugger_address = existing_debugger_address
        print(
            "Attached startup state to existing Chrome window: "
            f"{startup_debugger_address} (pid {startup_browser_pid})",
            flush=True,
        )
        return

    user_data_dir = configured_dir
    if profile_is_locked(configured_dir):
        if not allow_temporary_profile():
            print(
                "Startup Chrome profile is locked; refusing to open a "
                "temporary logged-out browser. Close the Chrome window using "
                "this profile, or set BROWSER_SERVER_ALLOW_TEMP_PROFILE=1.",
                flush=True,
            )
            return
        startup_profile_dir = tempfile.mkdtemp(prefix="browser-server-visible-")
        user_data_dir = startup_profile_dir
        print(
            "Startup Chrome profile is locked; opening visible browser with "
            f"temporary profile {startup_profile_dir!r}.",
            flush=True,
        )

    try:
        startup_browser_process = launch(user_data_dir)
        startup_browser_pid = startup_browser_process.pid
        time.sleep(2)
        if startup_browser_process.poll() is not None:
            if not allow_temporary_profile():
                print(
                    "Startup Chrome exited early with "
                    f"code {startup_browser_process.returncode}; refusing to "
                    "retry with a temporary logged-out profile. See "
                    "/tmp/browser-server-chrome.log for Chrome stderr.",
                    flush=True,
                )
                return
            if not startup_profile_dir:
                startup_profile_dir = tempfile.mkdtemp(prefix="browser-server-visible-")
            print(
                "Startup Chrome exited early with "
                f"code {startup_browser_process.returncode}; retrying with "
                f"temporary profile {startup_profile_dir!r}. "
                "See /tmp/browser-server-chrome.log for Chrome stderr.",
                flush=True,
            )
            startup_browser_process = launch(startup_profile_dir)
            startup_browser_pid = startup_browser_process.pid

        print(
            f"Opened startup browser window: {url} "
            f"(debugger {startup_debugger_address})",
            flush=True,
        )
    except OSError as exc:
        print(f"Initial browser open failed: {exc}", file=sys.stderr)


@app.route('/health', methods=['GET'])
def health():
    startup_alive = (
        startup_browser_process is not None
        and startup_browser_process.poll() is None
    ) or (startup_debugger_address is not None and debugger_is_ready(startup_debugger_address))
    return jsonify({
        "status": "ok",
        "browser_started": driver is not None or startup_alive,
        "startup_debugger_address": startup_debugger_address if startup_alive else None,
    })


@app.route('/open', methods=['POST'])
def open_url():
    try:
        url = request.json.get('url', 'https://chatgpt.com/')
        get_driver().get(url)
        return jsonify({"status": "opened", "url": url})
    except TimeoutException as exc:
        return jsonify({"status": "error", "error": "page_load_timeout", "details": str(exc)}), 504
    except WebDriverException as exc:
        return jsonify({"status": "error", "error": "webdriver_error", "details": str(exc)}), 500


@app.route('/debug_state', methods=['GET'])
def debug_state():
    d = get_driver()
    selector_counts = {}
    selectors = [
        "#prompt-textarea",
        'div[contenteditable="true"]#prompt-textarea',
        'div.ProseMirror[contenteditable="true"]',
        'div[contenteditable="true"][data-placeholder]',
        'textarea[data-testid="prompt-textarea"]',
        '[data-message-author-role]',
    ]
    windows = []

    for handle in d.window_handles:
        try:
            d.switch_to.window(handle)
            counts = {}
            for selector in selectors:
                elements = d.find_elements(By.CSS_SELECTOR, selector)
                counts[selector] = {
                    "total": len(elements),
                    "visible": sum(1 for el in elements if el.is_displayed()),
                }
            windows.append({
                "handle": handle,
                "title": d.title,
                "url": d.current_url,
                "selectors": counts,
            })
        except WebDriverException as exc:
            windows.append({
                "handle": handle,
                "error": str(exc),
            })

    ensure_chatgpt_page(d)
    return jsonify({"windows": windows, "current_url": d.current_url, "current_title": d.title})


@app.route('/new_chat', methods=['POST'])
@app.route('/new-chat', methods=['POST'])
def new_chat():
    try:
        url = current_start_url()
        get_driver().get(url)
        return jsonify({"status": "opened", "url": url})
    except TimeoutException as exc:
        return jsonify({"status": "error", "error": "page_load_timeout", "details": str(exc)}), 504
    except WebDriverException as exc:
        return jsonify({"status": "error", "error": "webdriver_error", "details": str(exc)}), 500


@app.route('/type', methods=['POST'])
def type_text():
    try:
        d = get_driver()
        ensure_chatgpt_page(d)
        text = request.json.get('text', '')
        selector = request.json.get('selector')
        if selector:
            el = WebDriverWait(d, 20).until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
        else:
            el = find_prompt_element(d)
        el.click()
        el.send_keys(text)
        return jsonify({"status": "typed", "text": text})
    except TimeoutException as exc:
        return jsonify({"status": "error", "error": "prompt_not_found", "details": str(exc)}), 504
    except WebDriverException as exc:
        return jsonify({"status": "error", "error": "webdriver_error", "details": str(exc)}), 500

@app.route('/send', methods=['POST'])
def send_message():
    d = get_driver()
    ensure_chatgpt_page(d)
    wait = WebDriverWait(d, 10)

    # Primary path: press Enter in the prompt.
    try:
        el = find_prompt_element(d, timeout=10)
        el.click()
        el.send_keys(Keys.RETURN)
        return jsonify({"status": "sent", "method": "enter"})
    except WebDriverException:
        pass

    # Fallback: send Enter to the active element.
    try:
        active = d.switch_to.active_element
        active.send_keys(Keys.RETURN)
        return jsonify({"status": "sent", "method": "active_element_enter"})
    except WebDriverException:
        pass

    # Final fallback: click common send-button selectors.
    button_selectors = [
        'button[data-testid="send-button"]',
        'button[aria-label^="Send"]',
        'button[aria-label*="Send message"]',
    ]
    for selector in button_selectors:
        try:
            btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
            btn.click()
            return jsonify({"status": "sent", "method": f"button:{selector}"})
        except WebDriverException:
            continue

    # Last resort: native Enter key at browser level.
    try:
        ActionChains(d).send_keys(Keys.RETURN).perform()
        return jsonify({"status": "sent", "method": "actionchains_enter"})
    except WebDriverException as exc:
        return jsonify({"status": "error", "error": "send_failed", "details": str(exc)}), 500

@app.route('/get_response', methods=['GET'])
def get_response():
    d = get_driver()
    ensure_chatgpt_page(d)
    timeout = request.args.get("timeout", default=25, type=int)
    timeout = max(1, min(timeout, 120))
    stable_seconds = request.args.get("stable_seconds", default=3, type=int)
    stable_seconds = max(1, min(stable_seconds, 15))
    deadline = time.time() + timeout
    last_text = None
    last_changed_at = time.time()

    while time.time() < deadline:
        messages = d.find_elements(By.CSS_SELECTOR, '[data-message-author-role="assistant"]')
        for msg in reversed(messages):
            text = (msg.text or "").strip()
            if text:
                if text != last_text:
                    last_text = text
                    last_changed_at = time.time()
                elif time.time() - last_changed_at >= stable_seconds:
                    return jsonify({"response": text})
                break
        time.sleep(1)
    return jsonify({"response": last_text})

@app.route('/read_thread', methods=['GET'])
def read_thread():
    """
    Returns the full conversation thread as a list of turns.
    Each turn has: role ('user' or 'assistant'), turn_id, and text.
    Optional query param ?last=N returns only the last N turns.
    """
    d = get_driver()
    ensure_chatgpt_page(d)

    thread = []
    bubbles = d.find_elements(By.CSS_SELECTOR, '[data-message-author-role]')
    for idx, bubble in enumerate(bubbles, start=1):
        role = (bubble.get_attribute('data-message-author-role') or '').strip()
        text = (bubble.text or '').strip()
        if role in ('user', 'assistant') and text:
            thread.append({
                "role": role,
                "turn_id": str(idx),
                "text": text,
            })

    # Support ?last=N to fetch only the most recent N turns
    last_n = request.args.get('last', type=int)
    if last_n:
        thread = thread[-last_n:]

    return jsonify({"thread": thread, "turn_count": len(thread)})

@app.route('/screenshot', methods=['GET'])
def screenshot():
    d = get_driver()
    path = "screenshot.png"
    d.save_screenshot(path)
    return jsonify({"saved": path})

@app.route('/quit', methods=['POST'])
def quit_browser():
    close_driver()
    return jsonify({"status": "closed"})

if __name__ == '__main__':
    if os.environ.get("BROWSER_SERVER_OPEN_ON_START") == "1":
        threading.Thread(target=open_initial_url, daemon=True).start()
    app.run(
        host=os.environ.get("BROWSER_SERVER_HOST", "127.0.0.1"),
        port=int(os.environ.get("BROWSER_SERVER_PORT", "5001")),
        threaded=True,
    )

    
