from __future__ import annotations

import asyncio
import concurrent.futures
import os
import platform
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Optional

from playwright.async_api import (
    async_playwright,
    BrowserContext,
    Page,
    Playwright,
    TimeoutError as PlaywrightTimeout,
)

_OS = platform.system()


def _normalize_url(url: str) -> str:
    url = url.strip()
    if not url:
        return "about:blank"
    if "://" in url:
        return url
    if "." not in url:
        url = url + ".com"
    return "https://" + url


def _user_agent() -> str:
    if _OS == "Windows":
        return (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    if _OS == "Darwin":
        return (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    return (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )


def _real_profile_dir(browser: str) -> str:
    home  = Path.home()
    local = os.environ.get("LOCALAPPDATA", "")
    roam  = os.environ.get("APPDATA", "")
    candidates: list[Path] = []

    if _OS == "Windows":
        m = {
            "chrome":  [Path(local) / "Google"       / "Chrome"        / "User Data"],
            "edge":    [Path(local) / "Microsoft"     / "Edge"          / "User Data"],
            "brave":   [Path(local) / "BraveSoftware" / "Brave-Browser" / "User Data"],
            "vivaldi": [Path(local) / "Vivaldi"       / "User Data"],
            "opera":   [Path(roam)  / "Opera Software" / "Opera Stable",
                        Path(local) / "Opera Software" / "Opera Stable"],
        }
        candidates = m.get(browser, [])
    elif _OS == "Darwin":
        lib = home / "Library" / "Application Support"
        m = {
            "chrome":  [lib / "Google" / "Chrome"],
            "brave":   [lib / "BraveSoftware" / "Brave-Browser"],
            "vivaldi": [lib / "Vivaldi"],
        }
        candidates = m.get(browser, [])
    elif _OS == "Linux":
        cfg = home / ".config"
        m = {
            "chrome":  [cfg / "google-chrome", cfg / "chromium"],
            "brave":   [cfg / "BraveSoftware" / "Brave-Browser"],
            "vivaldi": [cfg / "vivaldi"],
        }
        candidates = m.get(browser, [])

    for p in candidates:
        if p.exists():
            print(f"[Browser] Perfil encontrado para {browser}: {p}")
            return str(p)

    fallback = home / ".jarvis_profiles" / browser
    fallback.mkdir(parents=True, exist_ok=True)
    print(f"[Browser] Usando perfil JARVIS: {fallback}")
    return str(fallback)


def _firefox_profile_dir() -> Optional[str]:
    home = Path.home()
    if _OS == "Windows":
        base = Path(os.environ.get("APPDATA", "")) / "Mozilla" / "Firefox"
    elif _OS == "Darwin":
        base = home / "Library" / "Application Support" / "Firefox"
    else:
        base = home / ".mozilla" / "firefox"
    ini = base / "profiles.ini"
    if not ini.exists():
        return None
    current: dict[str, str] = {}
    default_path: Optional[str] = None
    for line in ini.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if line.startswith("["):
            p = current.get("Path", "")
            if p and current.get("Default") == "1":
                is_rel = current.get("IsRelative", "1") == "1"
                default_path = str(base / p) if is_rel else p
            current = {}
        elif "=" in line:
            k, _, v = line.partition("=")
            current[k.strip()] = v.strip()
    p = current.get("Path", "")
    if p and current.get("Default") == "1":
        is_rel = current.get("IsRelative", "1") == "1"
        default_path = str(base / p) if is_rel else p
    if default_path and Path(default_path).exists():
        return default_path
    return None


_BROWSER_SPECS: dict[str, dict] = {
    "Windows": {
        "chrome":  {"engine": "chromium", "channel": "chrome",  "bins": []},
        "edge":    {"engine": "chromium", "channel": "msedge",  "bins": []},
        "brave":   {"engine": "chromium", "channel": None,      "bins": ["brave.exe"]},
        "vivaldi": {"engine": "chromium", "channel": None,      "bins": ["vivaldi.exe"]},
        "firefox": {"engine": "firefox",  "channel": None,      "bins": ["firefox.exe"]},
    },
    "Darwin": {
        "chrome":  {"engine": "chromium", "channel": "chrome", "bins": []},
        "brave":   {"engine": "chromium", "channel": None,     "bins": ["brave browser", "brave"]},
        "vivaldi": {"engine": "chromium", "channel": None,     "bins": ["vivaldi"]},
        "firefox": {"engine": "firefox",  "channel": None,     "bins": ["firefox"]},
        "safari":  {"engine": "webkit",   "channel": None,     "bins": []},
    },
    "Linux": {
        "chrome":  {"engine": "chromium", "channel": None,
                    "bins": ["google-chrome", "google-chrome-stable", "chromium-browser", "chromium"]},
        "brave":   {"engine": "chromium", "channel": None, "bins": ["brave-browser", "brave"]},
        "vivaldi": {"engine": "chromium", "channel": None, "bins": ["vivaldi-stable", "vivaldi"]},
        "firefox": {"engine": "firefox",  "channel": None, "bins": ["firefox"]},
    },
}

# Edge y cualquier variante siempre redirige a Chrome
_ALIASES: dict[str, str] = {
    "google chrome":   "chrome",
    "google-chrome":   "chrome",
    "microsoft edge":  "edge",
    "ms edge":         "edge",
    "msedge":          "edge",
    "edge":            "edge",
    "mozilla firefox": "firefox",
    "opera gx":        "chrome",   # opera gx -> chrome como fallback
}


def _detect_default_browser() -> str:
    """JARVIS siempre usa Microsoft Edge."""
    return "edge"


def _resolve_browser(name: str) -> dict | None:
    name   = _ALIASES.get(name.lower().strip(), name.lower().strip())
    os_map = _BROWSER_SPECS.get(_OS, {})
    spec   = os_map.get(name)
    if spec is None:
        spec = os_map.get("chrome", {"engine": "chromium", "channel": "chrome", "bins": []})
    engine  = spec["engine"]
    channel = spec.get("channel")
    bins    = spec.get("bins", [])
    exe     = None
    for b in bins:
        found = shutil.which(b)
        if found:
            exe = found
            break
    if not exe and _OS == "Darwin":
        app_names = {
            "chrome":  ["Google Chrome.app"],
            "brave":   ["Brave Browser.app"],
            "vivaldi": ["Vivaldi.app"],
            "firefox": ["Firefox.app"],
        }
        for app in app_names.get(name, []):
            app_dir = Path("/Applications") / app / "Contents" / "MacOS"
            if app_dir.exists():
                found_bins = list(app_dir.iterdir())
                if found_bins:
                    exe = str(found_bins[0])
                    break
    return {"engine": engine, "exe": exe, "channel": channel}


class _BrowserSession:
    def __init__(self, browser_name: str):
        self.browser_name = browser_name
        self._spec        = _resolve_browser(browser_name)
        self._loop:    asyncio.AbstractEventLoop | None = None
        self._thread:  threading.Thread | None          = None
        self._ready    = threading.Event()
        self._pw:      Playwright     | None = None
        self._context: BrowserContext | None = None
        self._page:    Page           | None = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(
            target=self._run_loop, daemon=True,
            name=f"BrowserThread-{self.browser_name}",
        )
        self._thread.start()
        self._ready.wait(timeout=20)

    def _run_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._async_init())
        self._ready.set()
        self._loop.run_forever()

    async def _async_init(self):
        self._pw = await async_playwright().start()

    def run(self, coro, timeout: int = 60) -> str:
        if not self._loop:
            raise RuntimeError(f"Session for '{self.browser_name}' not started.")
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=timeout)

    def close(self):
        if self._loop:
            asyncio.run_coroutine_threadsafe(self._async_close(), self._loop).result(10)

    async def _async_close(self):
        if self._context:
            try: await self._context.close()
            except Exception: pass
        if self._pw:
            try: await self._pw.stop()
            except Exception: pass
        self._context = self._page = None

    async def _launch(self):
        if self._context is not None:
            return
        if self._spec is None:
            raise RuntimeError(f"'{self.browser_name}' no soportado en {_OS}.")

        engine_name = self._spec["engine"]
        exe         = self._spec["exe"]
        channel     = self._spec["channel"]
        engine_obj  = getattr(self._pw, engine_name)

        if engine_name == "firefox":
            profile = _firefox_profile_dir() or str(Path.home() / ".jarvis_profiles" / "firefox")
            kwargs: dict = {"headless": False, "slow_mo": 0, "viewport": None, "no_viewport": True}
            if exe: kwargs["executable_path"] = exe
            try:
                self._context = await engine_obj.launch_persistent_context(profile, **kwargs)
            except Exception:
                jarvis = str(Path.home() / ".jarvis_profiles" / "firefox_jarvis")
                Path(jarvis).mkdir(parents=True, exist_ok=True)
                self._context = await engine_obj.launch_persistent_context(jarvis, **kwargs)
            await asyncio.sleep(0.5)
            self._page = await self._context.new_page()
            return

        profile = _real_profile_dir(self.browser_name)
        kwargs = {
            "headless":    False,
            "slow_mo":     0,
            "viewport":    None,
            "no_viewport": True,
            "args": [
                "--start-maximized",
                "--disable-blink-features=AutomationControlled",
                "--no-first-run",
                "--disable-default-apps",
                "--no-default-browser-check",
            ],
        }
        if exe:     kwargs["executable_path"] = exe
        elif channel: kwargs["channel"] = channel

        try:
            self._context = await engine_obj.launch_persistent_context(profile, **kwargs)
            await asyncio.sleep(0.5)
            self._page = await self._context.new_page()
            print(f"[Browser] Edge iniciado con perfil real")
            return
        except Exception as e:
            print(f"[Browser] Perfil real falló ({e}), usando perfil JARVIS")

        jarvis_profile = str(Path.home() / ".jarvis_profiles" / self.browser_name)
        Path(jarvis_profile).mkdir(parents=True, exist_ok=True)
        self._context = await engine_obj.launch_persistent_context(jarvis_profile, **kwargs)
        await asyncio.sleep(0.5)
        self._page = await self._context.new_page()
        print(f"[Browser] Edge iniciado con perfil JARVIS")

    async def _get_page(self) -> Page:
        await self._launch()
        if self._page is None or self._page.is_closed():
            self._page = await self._context.new_page()
            await asyncio.sleep(0.2)
        return self._page

    async def go_to(self, url: str) -> str:
        url  = _normalize_url(url)
        page = await self._get_page()
        prev = page.url
        async def _do(p: Page) -> str:
            try:
                await p.goto(url, wait_until="domcontentloaded", timeout=30_000)
                await asyncio.sleep(0.3)
            except PlaywrightTimeout:
                pass
            except Exception as e:
                print(f"[Browser] goto: {e}")
            return p.url
        result = await _do(page)
        if result in ("about:blank", "", None, prev) and prev in ("about:blank", "", None):
            try:
                new_page   = await self._context.new_page()
                self._page = new_page
                result     = await _do(new_page)
            except Exception as e:
                print(f"[Browser] Retry failed: {e}")
        return f"Abierto: {result}" if result and result not in ("about:blank","",None) else f"No se pudo abrir: {url}"

    async def search(self, query: str, engine: str = "google") -> str:
        _engines = {
            "google":     "https://www.google.com/search?q=",
            "bing":       "https://www.bing.com/search?q=",
            "duckduckgo": "https://duckduckgo.com/?q=",
        }
        base = _engines.get(engine.lower(), _engines["google"])
        return await self.go_to(base + query.replace(" ", "+"))

    async def click(self, selector: str = None, text: str = None) -> str:
        page = await self._get_page()
        try:
            if text:
                await page.get_by_text(text, exact=False).first.click(timeout=8_000)
                return f"Click en: '{text}'"
            if selector:
                await page.click(selector, timeout=8_000)
                return f"Click en: {selector}"
            return "No se especificó selector ni texto."
        except PlaywrightTimeout:
            return "Elemento no encontrado (timeout)."
        except Exception as e:
            return f"Error al hacer click: {e}"

    async def type_text(self, selector: str = None, text: str = "", clear_first: bool = True) -> str:
        page = await self._get_page()
        try:
            el = page.locator(selector).first if selector else page.locator(":focus")
            if clear_first: await el.clear()
            await el.type(text, delay=50)
            return "Texto escrito."
        except Exception as e:
            return f"Error al escribir: {e}"

    async def scroll(self, direction: str = "down", amount: int = 500) -> str:
        page = await self._get_page()
        try:
            y = amount if direction == "down" else -amount
            await page.mouse.wheel(0, y)
            return f"Scroll {direction}."
        except Exception as e:
            return f"Error scroll: {e}"

    async def press(self, key: str) -> str:
        page = await self._get_page()
        try:
            await page.keyboard.press(key)
            return f"Tecla: {key}"
        except Exception as e:
            return f"Error tecla: {e}"

    async def get_text(self) -> str:
        page = await self._get_page()
        try:
            text = await page.inner_text("body")
            return text[:4_000]
        except Exception as e:
            return f"Error obteniendo texto: {e}"

    async def get_url(self) -> str:
        page = await self._get_page()
        return page.url

    async def fill_form(self, fields: dict) -> str:
        page    = await self._get_page()
        results = []
        for selector, value in fields.items():
            try:
                el = page.locator(selector).first
                await el.clear()
                await el.type(str(value), delay=40)
                results.append(f"OK {selector}")
            except Exception as e:
                results.append(f"Error {selector}: {e}")
        return "Formulario: " + ", ".join(results)

    async def smart_click(self, description: str) -> str:
        page = await self._get_page()
        for role in ("button", "link", "searchbox", "textbox", "menuitem", "tab"):
            try:
                loc = page.get_by_role(role, name=description)
                if await loc.count() > 0:
                    await loc.first.click(timeout=5_000)
                    return f"Click ({role}): '{description}'"
            except Exception:
                pass
        for attempt in (
            lambda: page.get_by_text(description, exact=False).first.click(timeout=5_000),
            lambda: page.get_by_placeholder(description, exact=False).first.click(timeout=5_000),
        ):
            try:
                await attempt()
                return f"Click: '{description}'"
            except Exception:
                pass
        return f"No se encontró: '{description}'"

    async def smart_type(self, description: str, text: str) -> str:
        page = await self._get_page()
        candidates = [
            ("placeholder", page.get_by_placeholder(description, exact=False)),
            ("label",       page.get_by_label(description, exact=False)),
            ("role",        page.get_by_role("textbox", name=description)),
            ("searchbox",   page.get_by_role("searchbox")),
        ]
        for method, loc in candidates:
            try:
                el = loc.first
                if await el.count() == 0: continue
                await el.clear()
                await el.type(text, delay=50)
                return f"Texto en ({method}): '{description}'"
            except Exception:
                continue
        return f"No se encontró input: '{description}'"

    async def new_tab(self, url: str = "") -> str:
        page = await self._get_page()
        new  = await page.context.new_page()
        self._page = new
        if url: return await self.go_to(url)
        return "Nueva pestaña abierta."

    async def close_tab(self) -> str:
        page = self._page
        if page and not page.is_closed():
            ctx   = page.context
            await page.close()
            pages = ctx.pages
            self._page = pages[-1] if pages else None
            return "Pestaña cerrada."
        return "No hay pestaña activa."

    async def screenshot(self, path: str = None) -> str:
        page = await self._get_page()
        try:
            save_path = path or str(Path.home() / "Desktop" / "jarvis_screenshot.png")
            await page.screenshot(path=save_path, full_page=False)
            return f"Captura guardada: {save_path}"
        except Exception as e:
            return f"Error captura: {e}"

    async def back(self) -> str:
        page = await self._get_page()
        try:
            await page.go_back(timeout=10_000)
            return f"Atrás: {page.url}"
        except Exception as e:
            return f"Error atrás: {e}"

    async def forward(self) -> str:
        page = await self._get_page()
        try:
            await page.go_forward(timeout=10_000)
            return f"Adelante: {page.url}"
        except Exception as e:
            return f"Error adelante: {e}"

    async def reload(self) -> str:
        page = await self._get_page()
        try:
            await page.reload(timeout=15_000)
            return f"Recargada: {page.url}"
        except Exception as e:
            return f"Error recarga: {e}"

    async def close_browser(self) -> str:
        await self._async_close()
        return f"{self.browser_name} cerrado."


class _SessionRegistry:
    def __init__(self):
        self._sessions:       dict[str, _BrowserSession] = {}
        self._active_browser: str                        = "edge"
        self._lock            = threading.Lock()

    def _get_or_create(self, browser_name: str) -> _BrowserSession:
        with self._lock:
            if browser_name not in self._sessions:
                sess = _BrowserSession(browser_name)
                sess.start()
                self._sessions[browser_name] = sess
        return self._sessions[browser_name]

    def get(self, browser_name: str | None = None) -> _BrowserSession:
        # JARVIS siempre usa Microsoft Edge
        browser_name = "edge"
        sess = self._get_or_create(browser_name)
        self._active_browser = browser_name
        return sess

    def switch(self, browser_name: str) -> str:
        # Ignorar cambios a Edge — forzar Chrome
        browser_name = _ALIASES.get(browser_name.lower().strip(), browser_name.lower().strip())
        if browser_name == "chrome":
            self._get_or_create("chrome")
            self._active_browser = "chrome"
            return "Navegador: Chrome"
        # Para firefox u otros que no sean edge
        self._get_or_create(browser_name)
        self._active_browser = browser_name
        return f"Navegador: {browser_name}"

    def close_one(self, browser_name: str) -> str:
        with self._lock:
            sess = self._sessions.pop(browser_name, None)
        if sess:
            sess.close()
            self._active_browser = "edge"
            return f"{browser_name} cerrado."
        return f"No hay sesión activa para: {browser_name}"

    def close_all(self) -> str:
        with self._lock:
            names    = list(self._sessions.keys())
            sessions = list(self._sessions.values())
            self._sessions.clear()
            self._active_browser = "edge"
        for s in sessions:
            try: s.close()
            except Exception: pass
        return "Navegadores cerrados: " + (", ".join(names) if names else "ninguno")

    def list_sessions(self) -> str:
        with self._lock:
            if not self._sessions:
                return "No hay sesiones activas."
            lines = [f"  • {n}{' ◀ activo' if n==self._active_browser else ''}"
                     for n in self._sessions]
            return "Navegadores:\n" + "\n".join(lines)


_registry = _SessionRegistry()


def browser_control(parameters: dict = None, response=None, player=None, session_memory=None) -> str:
    params  = parameters or {}
    action  = params.get("action", "").lower().strip()

    # JARVIS siempre usa Microsoft Edge
    browser = "edge"

    result = "Acción no reconocida."

    if action == "switch":
        result = _registry.switch("edge")
        _log(player, result)
        return result

    if action == "list_browsers":
        result = _registry.list_sessions()
        _log(player, result)
        return result

    if action == "close_all":
        result = _registry.close_all()
        _log(player, result)
        return result

    try:
        sess = _registry.get(browser)
    except Exception as e:
        result = f"No se pudo iniciar Edge: {e}"
        _log(player, result)
        return result

    try:
        if action in ("go_to", "open", "open_url", "navigate", "abrir", "ir_a"):
            result = sess.run(sess.go_to(params.get("url", params.get("path", ""))))
        elif action == "search":
            result = sess.run(sess.search(params.get("query", ""), params.get("engine", "google")))
        elif action == "click":
            result = sess.run(sess.click(params.get("selector"), params.get("text")))
        elif action == "type":
            result = sess.run(sess.type_text(
                params.get("selector"), params.get("text", ""), params.get("clear_first", True)))
        elif action == "scroll":
            result = sess.run(sess.scroll(params.get("direction", "down"), int(params.get("amount", 500))))
        elif action == "fill_form":
            result = sess.run(sess.fill_form(params.get("fields", {})))
        elif action == "smart_click":
            result = sess.run(sess.smart_click(params.get("description", "")))
        elif action == "smart_type":
            result = sess.run(sess.smart_type(params.get("description", ""), params.get("text", "")))
        elif action == "get_text":
            result = sess.run(sess.get_text())
        elif action == "get_url":
            result = sess.run(sess.get_url())
        elif action == "press":
            result = sess.run(sess.press(params.get("key", "Enter")))
        elif action == "new_tab":
            result = sess.run(sess.new_tab(params.get("url", "")))
        elif action == "close_tab":
            result = sess.run(sess.close_tab())
        elif action == "screenshot":
            result = sess.run(sess.screenshot(params.get("path")))
        elif action == "back":
            result = sess.run(sess.back())
        elif action == "forward":
            result = sess.run(sess.forward())
        elif action == "reload":
            result = sess.run(sess.reload())
        elif action == "close":
            result = _registry.close_one("edge")
        else:
            result = f"Acción desconocida: '{action}'"

    except concurrent.futures.TimeoutError:
        result = f"Acción '{action}' tardó demasiado (60s)."
    except Exception as e:
        result = f"Error ({action}): {e}"

    _log(player, result)
    return result


def _log(player, text: str):
    short = str(text)[:80]
    print(f"[Browser] {short}")
    if player:
        player.write_log(f"[browser] {short[:60]}")
