import asyncio
import json
import os
import platform
import random
import tempfile
from typing import Optional

import mycdp.input_ as cdp_input
from seleniumbase import cdp_driver


"""
MADE BY ISMOILOFF. GOOD LUCK HAVE FUN, THIS IS JUST PROJECT, USE IT ON UR OWN RISKS!
"""


def _find_chrome() -> str:
    """Return the Chrome executable path, checking common locations per OS."""
    if os.environ.get("CHROME_PATH"):
        return os.environ["CHROME_PATH"]

    if platform.system() == "Windows":
        candidates = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(
                r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"
            ),
        ]
    else:
        candidates = [
            "/usr/bin/google-chrome-stable",
            "/usr/bin/google-chrome",
            "/usr/bin/chromium-browser",
            "/usr/bin/chromium",
        ]

    for path in candidates:
        if os.path.isfile(path):
            return path

    raise FileNotFoundError(
        "Chrome not found in default locations. "
        "Set the CHROME_PATH environment variable to your Chrome executable."
    )


def _env_flag(name: str, default: bool = False) -> bool:
    """Read a boolean environment variable."""
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _get_profile_root() -> str:
    """Return the parent directory used for isolated browser profiles."""
    root = os.environ.get("TS_PROFILE_DIR")
    if not root:
        root = os.path.join(tempfile.gettempdir(), "ezsolver_profiles")
    root = os.path.abspath(os.path.expanduser(root))
    os.makedirs(root, exist_ok=True)
    return root


def _browser_options() -> dict:
    """Build SeleniumBase options for headless or Xvfb compatibility mode."""
    use_xvfb = platform.system() == "Linux" and _env_flag("USE_XVFB")
    true_headless = _env_flag("TRUE_HEADLESS", default=True) and not use_xvfb
    return {
        "headless": true_headless,
        "headed": not true_headless and not use_xvfb,
        "xvfb": use_xvfb,
    }


async def _dispatch_mouse_event(
    page,
    event_type: str,
    x: float,
    y: float,
    *,
    pressed: bool = False,
) -> None:
    """Send a viewport-relative mouse event through Chrome DevTools."""
    kwargs = {
        "type_": event_type,
        "x": x,
        "y": y,
        "buttons": 1 if pressed else 0,
        "pointer_type": "mouse",
    }
    if event_type in {"mousePressed", "mouseReleased"}:
        kwargs["button"] = cdp_input.MouseButton("left")
        kwargs["click_count"] = 1
    await page.send(cdp_input.dispatch_mouse_event(**kwargs))


async def _stop_browser(browser) -> None:
    """Close CDP and wait until Chrome releases its profile files."""
    process = getattr(browser, "_process", None)
    connection = getattr(browser, "connection", None)
    try:
        if connection:
            await connection.aclose()
    finally:
        browser.stop()

    if process and process.returncode is None:
        try:
            await asyncio.wait_for(process.wait(), timeout=5)
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()


async def _solve(sitekey: str, siteurl: str, timeout: int) -> str:
    browser = None
    token: Optional[str] = None

    # Chrome cannot safely share one user-data-dir across concurrent processes.
    # Each solve therefore gets a separate profile that is removed on completion.
    with tempfile.TemporaryDirectory(
        prefix="worker-", dir=_get_profile_root()
    ) as profile_dir:
        options = _browser_options()
        browser = await cdp_driver.start_async(
            browser_executable_path=_find_chrome(),
            user_data_dir=profile_dir,
            browser_args=["--window-size=1280,900"],
            lang="en-US",
            **options,
        )

        try:
            page = await browser.get(siteurl)
            await asyncio.sleep(random.uniform(2.0, 3.0))

            # JSON encoding prevents a sitekey from breaking out of the script.
            encoded_sitekey = json.dumps(sitekey)
            await page.evaluate(
                f"""
                (() => {{
                    if (document.getElementById('_ts_box')) return;
                    window._tsToken = null;
                    const wrap = document.createElement('div');
                    wrap.id = '_ts_box';
                    wrap.style = 'position:fixed;top:20px;left:20px;z-index:2147483647;';
                    document.body.appendChild(wrap);
                    window._tsLoad = function () {{
                        turnstile.render('#_ts_box', {{
                            sitekey: {encoded_sitekey},
                            callback: function(token) {{ window._tsToken = token; }}
                        }});
                    }};
                    const s = document.createElement('script');
                    s.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js?onload=_tsLoad&render=explicit';
                    s.async = true;
                    document.head.appendChild(s);
                }})();
                """
            )

            # Give Turnstile time to load and potentially auto-complete.
            await asyncio.sleep(5.0)

            async def get_token() -> Optional[str]:
                return await page.evaluate(
                    """
                    (() => {
                        if (window._tsToken) return window._tsToken;
                        const inp = document.querySelector(
                            '#_ts_box [name="cf-turnstile-response"]'
                        );
                        return (inp && inp.value) ? inp.value : null;
                    })()
                    """
                )

            async def get_cf_iframe_rect() -> Optional[dict]:
                return await page.evaluate(
                    """
                    (() => {
                        for (const f of document.querySelectorAll('iframe')) {
                            const src = f.src || f.getAttribute('src') || '';
                            if (!src.includes('challenges.cloudflare.com')) continue;
                            const r = f.getBoundingClientRect();
                            if (r.width > 50 && r.height > 20) {
                                return {x:r.x, y:r.y, w:r.width, h:r.height};
                            }
                        }
                        return null;
                    })()
                    """
                )

            async def do_click(rect: Optional[dict]) -> None:
                if rect:
                    cx = rect["x"] + 28 + random.uniform(-3, 3)
                    cy = rect["y"] + rect["h"] / 2 + random.uniform(-3, 3)
                    print(
                        "[solver] clicking Cloudflare iframe at "
                        f"({cx:.0f}, {cy:.0f})"
                    )
                else:
                    # Widget is fixed at top:20px left:20px.
                    cx = 20 + 28 + random.uniform(-3, 3)
                    cy = 20 + 32 + random.uniform(-3, 3)
                    print(
                        "[solver] iframe not in DOM, clicking fixed position "
                        f"({cx:.0f}, {cy:.0f})"
                    )

                await _dispatch_mouse_event(
                    page, "mouseMoved", cx - 80, cy - 20
                )
                await asyncio.sleep(random.uniform(0.15, 0.25))
                await _dispatch_mouse_event(page, "mouseMoved", cx, cy)
                await asyncio.sleep(random.uniform(0.08, 0.15))
                await _dispatch_mouse_event(
                    page, "mousePressed", cx, cy, pressed=True
                )
                await asyncio.sleep(random.uniform(0.04, 0.09))
                await _dispatch_mouse_event(page, "mouseReleased", cx, cy)

            token = await get_token()
            if not token:
                # Wait up to 10s for a visible checkbox iframe to appear.
                rect = None
                for _ in range(20):
                    rect = await get_cf_iframe_rect()
                    if rect:
                        break
                    await asyncio.sleep(0.5)

                deadline = asyncio.get_running_loop().time() + timeout
                click_count = 0
                last_click = 0.0

                while asyncio.get_running_loop().time() < deadline:
                    token = await get_token()
                    if token:
                        break

                    now = asyncio.get_running_loop().time()
                    if click_count == 0 or now - last_click > 8:
                        if click_count >= 3:
                            await asyncio.sleep(0.3)
                            continue
                        await do_click(rect)
                        last_click = asyncio.get_running_loop().time()
                        click_count += 1
                        await asyncio.sleep(1.0)
                        rect = await get_cf_iframe_rect() or rect
                        continue

                    await asyncio.sleep(0.3)
        finally:
            if browser:
                await _stop_browser(browser)

    if not token:
        raise TimeoutError(f"Turnstile token not obtained within {timeout}s")

    return token


def solve(sitekey: str, siteurl: str, timeout: int = 45) -> str:
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return asyncio.run(_solve(sitekey, siteurl, timeout))


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: python solver.py <sitekey> <siteurl>")
        sys.exit(1)

    print(solve(sys.argv[1], sys.argv[2]))
