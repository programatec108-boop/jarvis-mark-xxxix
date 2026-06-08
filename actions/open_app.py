# open_app.py - Abre aplicaciones y archivos en Windows
# Archivo: C:\Users\jose1\Mark-XXXIX\actions\open_app.py

import os
import subprocess
import difflib
import time
import threading
from pathlib import Path

USER     = os.environ.get("USERNAME", "jose1")
HOME     = Path(f"C:/Users/{USER}")
DESKTOP  = HOME / "Desktop"
DOCS     = HOME / "Documents"
DOWNLOADS= HOME / "Downloads"
ONEDRIVE_DESK = HOME / "OneDrive" / "Escritorio"
ONEDRIVE_DOCS = HOME / "OneDrive" / "Documentos"

# Software conocido — nombre → comando o ruta
APPS = {
    # Navegadores
    "chrome":        "chrome",
    "google chrome": "chrome",
    "firefox":       "firefox",
    "edge":          "msedge",
    "opera":         f"C:/Users/{USER}/AppData/Local/Programs/Opera/opera.exe",

    # Office
    "word":          "winword",
    "excel":         "excel",
    "powerpoint":    "powerpnt",
    "outlook":       "outlook",
    "onenote":       "onenote",
    "access":        "msaccess",

    # Diseño / Video
    "photoshop":     f"C:/Program Files/Adobe/Adobe Photoshop 2024/Photoshop.exe",
    "illustrator":   f"C:/Program Files/Adobe/Adobe Illustrator 2024/Support Files/Contents/Windows/Illustrator.exe",
    "premiere":      f"C:/Program Files/Adobe/Adobe Premiere Pro 2024/Adobe Premiere Pro.exe",
    "after effects": f"C:/Program Files/Adobe/Adobe After Effects 2024/Support Files/AfterFX.exe",
    "capcut":        f"C:/Users/{USER}/AppData/Local/Programs/CapCut/CapCut.exe",
    "canva":         "https://www.canva.com",
    "vlc":           "vlc",

    # Código
    "vscode":        f"C:/Users/{USER}/AppData/Local/Programs/Microsoft VS Code/Code.exe",
    "visual studio code": f"C:/Users/{USER}/AppData/Local/Programs/Microsoft VS Code/Code.exe",
    "notepad":       "notepad",
    "notepad++":     f"C:/Program Files/Notepad++/notepad++.exe",
    "pycharm":       f"C:/Users/{USER}/AppData/Local/JetBrains/Toolbox/apps/PyCharm-P/ch-0/pycharm64.exe",

    # Comunicación
    "whatsapp":      f"C:/Users/{USER}/AppData/Local/WhatsApp/WhatsApp.exe",
    "discord":       f"C:/Users/{USER}/AppData/Local/Discord/Update.exe",
    "telegram":      f"C:/Users/{USER}/AppData/Roaming/Telegram Desktop/Telegram.exe",
    "teams":         f"C:/Users/{USER}/AppData/Local/Microsoft/Teams/current/Teams.exe",
    "zoom":          f"C:/Users/{USER}/AppData/Roaming/Zoom/bin/Zoom.exe",
    "slack":         f"C:/Users/{USER}/AppData/Local/slack/slack.exe",

    # Música / Media
    "spotify":       f"C:/Users/{USER}/AppData/Roaming/Spotify/Spotify.exe",

    # Sistema
    "explorador":    "explorer",
    "explorador de archivos": "explorer",
    "task manager":  "taskmgr",
    "administrador de tareas": "taskmgr",
    "calculadora":   "calc",
    "paint":         "mspaint",
    "recortes":      "snippingtool",
    "terminal":      "wt",
    "cmd":           "cmd",
    "powershell":    "powershell",

    # Juegos
    "steam":         "C:/Program Files (x86)/Steam/steam.exe",
    "epic":          f"C:/Users/{USER}/AppData/Local/EpicGamesLauncher/Portal/Binaries/Win64/EpicGamesLauncher.exe",

    # Nvidia
    "nvidia":        f"C:/Users/{USER}/AppData/Local/NVIDIA Corporation/NVIDIA app/CEF/NVIDIA app.exe",
}

EXTS = {".pdf",".docx",".doc",".xlsx",".xls",".pptx",".ppt",
        ".txt",".md",".csv",".py",".js",".html",".css",
        ".jpg",".jpeg",".png",".mp4",".avi",".mkv",".mp3"}


def _norm(s: str) -> str:
    s = s.lower().strip()
    for a,b in {"á":"a","é":"e","í":"i","ó":"o","ú":"u","ñ":"n"}.items():
        s = s.replace(a,b)
    return s


def _launch(cmd: str):
    """Lanza un proceso en hilo separado."""
    def _go():
        try:
            if cmd.startswith("http"):
                subprocess.Popen(f'start msedge "{cmd}"', shell=True)
            elif cmd.endswith(".exe") or "/" in cmd or "\\" in cmd:
                p = Path(cmd)
                if p.exists():
                    subprocess.Popen(f'"{cmd}"', shell=True)
                else:
                    subprocess.Popen(f'start "" {Path(cmd).stem}', shell=True)
            else:
                subprocess.Popen(f'start "" {cmd}', shell=True)
        except Exception as e:
            print(f"[OpenApp] Error: {e}")
    t = threading.Thread(target=_go, daemon=True)
    t.start()
    t.join(timeout=3)


def _find_file(name: str, ext_filter: str = "") -> str:
    """
    Busca un archivo SOLO en el nivel superior de las carpetas principales.
    Rápido e instantáneo — sin escanear subcarpetas.
    """
    q     = _norm(name)
    ext_f = ext_filter.lower().strip(".")
    best_path  = ""
    best_score = 0.0

    search_dirs = [DESKTOP, ONEDRIVE_DESK, DOCS, ONEDRIVE_DOCS, DOWNLOADS]

    for d in search_dirs:
        if not d.exists():
            continue
        try:
            # Solo nivel superior — sin rglob
            for f in d.iterdir():
                if not f.is_file():
                    continue
                if f.suffix.lower() not in EXTS:
                    continue
                if ext_f and f.suffix.lower() != f".{ext_f}":
                    continue
                fn = _norm(f.stem)
                if fn == q:
                    return str(f)          # exacto → directo
                score = 0.0
                if q in fn:
                    score = 0.9
                else:
                    score = difflib.SequenceMatcher(None, fn, q).ratio()
                    q_words  = set(q.split())
                    fn_words = set(fn.split())
                    hit = len(q_words & fn_words) / max(len(q_words), 1)
                    score = max(score, hit * 0.85)
                if score > best_score:
                    best_score = score
                    best_path  = str(f)
        except (PermissionError, OSError):
            continue

    return best_path if best_score >= 0.45 else ""


def open_app(parameters: dict, response=None, player=None) -> str:
    app_name  = (parameters.get("app_name")  or "").strip()
    file_path = (parameters.get("file_path") or "").strip()
    file_type = (parameters.get("file_type") or "").strip()

    if player:
        player.write_log(f"[OpenApp] '{app_name}' file_path='{file_path}'")

    # ── Ruta exacta dada ─────────────────────────────────────────────────────
    if file_path and Path(file_path).exists():
        _launch(file_path)
        return f"Abierto: {file_path}"

    if not app_name:
        return "No se especificó qué abrir."

    n = _norm(app_name)

    # ── 1. Match exacto en catálogo de software ───────────────────────────────
    if n in APPS:
        _launch(APPS[n])
        return f"Abriendo {app_name}."

    # ── 2. Fuzzy match en catálogo de software ───────────────────────────────
    close = difflib.get_close_matches(n, list(APPS.keys()), n=1, cutoff=0.72)
    if close:
        _launch(APPS[close[0]])
        return f"Abriendo {close[0]}."

    # ── 3. Buscar archivo por nombre en carpetas del usuario ─────────────────
    found = _find_file(app_name, file_type)
    if found:
        _launch(found)
        name_short = Path(found).name
        return f"Abriendo archivo: {name_short}"

    # ── 4. Último recurso — Windows 'start' directo ──────────────────────────
    _launch(app_name)
    return f"Intentando abrir: {app_name}"
