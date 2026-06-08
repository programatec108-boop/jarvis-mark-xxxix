# file_opener.py - Abre archivos y software en cualquier parte de la PC
# Archivo: C:\Users\jose1\Mark-XXXIX\actions\file_opener.py
#
# CAPACIDADES:
#   - Abre software por nombre (Chrome, Word, Photoshop, etc.)
#   - Busca y abre archivos en Escritorio, Documentos, Descargas y toda la PC
#   - Aprende rutas frecuentes y las guarda en memoria
#   - Funciona con nombres parciales, sin extensión, con errores tipográficos

import os
import subprocess
import json
import time
import difflib
from pathlib import Path
from datetime import datetime


# ── Configuración ─────────────────────────────────────────────────────────────

USER = os.environ.get("USERNAME", "jose1")
BASE_USER = Path(f"C:/Users/{USER}")

# Lugares donde buscar primero (orden de prioridad)
PRIORITY_DIRS = [
    BASE_USER / "Desktop",
    BASE_USER / "Documents",
    BASE_USER / "Downloads",
    BASE_USER / "OneDrive" / "Escritorio",
    BASE_USER / "OneDrive" / "Documentos",
    Path("C:/Users/Public/Desktop"),
]

# Extensiones que JARVIS puede abrir
OPENABLE_EXTS = {
    # Documentos
    ".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt",
    ".txt", ".md", ".csv", ".json", ".xml",
    # Imágenes
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg",
    # Video/Audio
    ".mp4", ".avi", ".mkv", ".mov", ".mp3", ".wav", ".flac",
    # Código
    ".py", ".js", ".ts", ".html", ".css", ".cpp", ".java", ".cs",
    # Otros
    ".zip", ".rar", ".7z", ".exe", ".lnk",
}

# Catálogo de software conocido → rutas comunes
SOFTWARE_CATALOG = {
    # Navegadores
    "chrome":       [r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                     r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"],
    "firefox":      [r"C:\Program Files\Mozilla Firefox\firefox.exe"],
    "edge":         [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"],
    "opera":        [r"C:\Users\{user}\AppData\Local\Programs\Opera\opera.exe"],

    # Ofimática
    "word":         [r"C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE",
                     r"C:\Program Files (x86)\Microsoft Office\root\Office16\WINWORD.EXE"],
    "excel":        [r"C:\Program Files\Microsoft Office\root\Office16\EXCEL.EXE",
                     r"C:\Program Files (x86)\Microsoft Office\root\Office16\EXCEL.EXE"],
    "powerpoint":   [r"C:\Program Files\Microsoft Office\root\Office16\POWERPNT.EXE"],
    "outlook":      [r"C:\Program Files\Microsoft Office\root\Office16\OUTLOOK.EXE"],
    "onenote":      [r"C:\Program Files\Microsoft Office\root\Office16\ONENOTE.EXE"],

    # Diseño / Video
    "photoshop":    [r"C:\Program Files\Adobe\Adobe Photoshop 2024\Photoshop.exe",
                     r"C:\Program Files\Adobe\Adobe Photoshop 2023\Photoshop.exe",
                     r"C:\Program Files\Adobe\Adobe Photoshop 2025\Photoshop.exe"],
    "illustrator":  [r"C:\Program Files\Adobe\Adobe Illustrator 2024\Support Files\Contents\Windows\Illustrator.exe"],
    "premiere":     [r"C:\Program Files\Adobe\Adobe Premiere Pro 2024\Adobe Premiere Pro.exe"],
    "after effects":[r"C:\Program Files\Adobe\Adobe After Effects 2024\Support Files\AfterFX.exe"],
    "lightroom":    [r"C:\Program Files\Adobe\Adobe Lightroom Classic\lightroom.exe"],
    "capcut":       [rf"C:\Users\{USER}\AppData\Local\Programs\CapCut\CapCut.exe"],
    "canva":        ["canva"],  # abre en navegador

    # Código / Dev
    "vscode":       [r"C:\Users\{user}\AppData\Local\Programs\Microsoft VS Code\Code.exe",
                     r"C:\Program Files\Microsoft VS Code\Code.exe"],
    "visual studio code": [r"C:\Users\{user}\AppData\Local\Programs\Microsoft VS Code\Code.exe"],
    "pycharm":      [rf"C:\Users\{USER}\AppData\Local\JetBrains\Toolbox\apps\PyCharm-P\ch-0\pycharm64.exe"],
    "notepad":      [r"C:\Windows\System32\notepad.exe"],
    "notepad++":    [r"C:\Program Files\Notepad++\notepad++.exe",
                     r"C:\Program Files (x86)\Notepad++\notepad++.exe"],
    "git bash":     [r"C:\Program Files\Git\git-bash.exe"],
    "terminal":     ["wt"],   # Windows Terminal
    "cmd":          ["cmd"],
    "powershell":   ["powershell"],

    # Comunicación
    "discord":      [rf"C:\Users\{USER}\AppData\Local\Discord\Update.exe --processStart Discord.exe",
                     rf"C:\Users\{USER}\AppData\Roaming\discord\Discord.exe"],
    "whatsapp":     [rf"C:\Users\{USER}\AppData\Local\WhatsApp\WhatsApp.exe"],
    "telegram":     [rf"C:\Users\{USER}\AppData\Roaming\Telegram Desktop\Telegram.exe"],
    "teams":        [r"C:\Program Files\Microsoft\Teams\current\Teams.exe",
                     rf"C:\Users\{USER}\AppData\Local\Microsoft\Teams\current\Teams.exe"],
    "zoom":         [rf"C:\Users\{USER}\AppData\Roaming\Zoom\bin\Zoom.exe"],
    "slack":        [rf"C:\Users\{USER}\AppData\Local\slack\slack.exe"],

    # Música / Media
    "spotify":      [rf"C:\Users\{USER}\AppData\Roaming\Spotify\Spotify.exe"],
    "vlc":          [r"C:\Program Files\VideoLAN\VLC\vlc.exe",
                     r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe"],
    "windows media player": ["wmplayer"],

    # Sistema
    "explorador":   ["explorer"],
    "explorador de archivos": ["explorer"],
    "task manager": ["taskmgr"],
    "administrador de tareas": ["taskmgr"],
    "panel de control": ["control"],
    "configuracion": ["ms-settings:"],
    "calculadora":  ["calc"],
    "paint":        ["mspaint"],
    "recortes":     ["snippingtool"],

    # Juegos / Steam
    "steam":        [r"C:\Program Files (x86)\Steam\steam.exe"],
    "epic":         [rf"C:\Users\{USER}\AppData\Local\EpicGamesLauncher\Portal\Binaries\Win64\EpicGamesLauncher.exe"],

    # Nvidia
    "nvidia":       [rf"C:\Users\{USER}\AppData\Local\NVIDIA Corporation\NVIDIA app\CEF\NVIDIA app.exe"],
    "geforce":      ["nvidia-geforce-experience://"],
}


# ── Memoria de rutas frecuentes ───────────────────────────────────────────────

def _get_memory_path() -> Path:
    appdata = os.environ.get("APPDATA", str(Path.home()))
    d = Path(appdata) / "JARVIS_Mark39"
    d.mkdir(parents=True, exist_ok=True)
    return d / "file_paths.json"


def _load_path_memory() -> dict:
    try:
        p = _get_memory_path()
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save_path_memory(mem: dict):
    try:
        _get_memory_path().write_text(
            json.dumps(mem, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    except Exception as e:
        print(f"[FileOpener] Error guardando rutas: {e}")


def _register_path(name: str, path: str):
    """Guarda una ruta usada para recordarla la próxima vez."""
    mem = _load_path_memory()
    key = name.lower().strip()
    if key not in mem:
        mem[key] = {"path": path, "veces": 1, "ultimo": datetime.now().strftime("%Y-%m-%d %H:%M")}
    else:
        mem[key]["veces"] = mem[key].get("veces", 1) + 1
        mem[key]["ultimo"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        mem[key]["path"] = path  # actualizar por si cambió
    _save_path_memory(mem)


def _get_cached_path(name: str) -> str:
    """Busca en memoria si ya conocemos la ruta de este archivo."""
    mem = _load_path_memory()
    key = name.lower().strip()
    if key in mem:
        cached = mem[key]["path"]
        if Path(cached).exists():
            return cached
    return ""


# ── Abrir software ────────────────────────────────────────────────────────────

def _normalize(text: str) -> str:
    return text.lower().strip().replace("_", " ").replace("-", " ")


def _find_software(name: str) -> tuple[str, str]:
    """
    Busca el ejecutable del software.
    Retorna (método, ruta_o_comando).
    método: 'start' | 'exec' | 'url' | 'not_found'
    """
    n = _normalize(name)

    # 1. Buscar en catálogo (coincidencia exacta)
    if n in SOFTWARE_CATALOG:
        paths = SOFTWARE_CATALOG[n]
        for p in paths:
            p = p.replace("{user}", USER)
            if p.startswith("ms-") or p.endswith("://"):
                return "url", p
            if len(p) < 20 and not "\\" in p:  # comando corto tipo "calc", "cmd"
                return "start", p
            if Path(p).exists():
                return "exec", p

    # 2. Fuzzy match en catálogo
    candidates = list(SOFTWARE_CATALOG.keys())
    close = difflib.get_close_matches(n, candidates, n=1, cutoff=0.65)
    if close:
        paths = SOFTWARE_CATALOG[close[0]]
        for p in paths:
            p = p.replace("{user}", USER)
            if len(p) < 20 and not "\\" in p:
                return "start", p
            if Path(p).exists():
                return "exec", p

    # 3. Buscar en Program Files y AppData
    search_dirs = [
        Path("C:/Program Files"),
        Path("C:/Program Files (x86)"),
        BASE_USER / "AppData" / "Local" / "Programs",
        BASE_USER / "AppData" / "Roaming",
        BASE_USER / "AppData" / "Local",
    ]
    keywords = n.split()
    for sd in search_dirs:
        if not sd.exists():
            continue
        try:
            for exe in sd.rglob("*.exe"):
                exe_n = _normalize(exe.stem)
                if all(kw in exe_n for kw in keywords):
                    return "exec", str(exe)
        except PermissionError:
            continue

    # 4. Último recurso: usar 'start' directo de Windows
    return "start", name


def _open_software(name: str) -> tuple[bool, str]:
    """Abre una aplicación en hilo separado — no bloquea. Retorna (éxito, ruta)."""
    import threading
    method, target = _find_software(name)
    try:
        def _launch():
            try:
                if method == "url":
                    subprocess.Popen(f'start "" "{target}"', shell=True)
                elif method == "exec":
                    subprocess.Popen(f'"{target}"', shell=True)
                else:
                    subprocess.Popen(f'start "" {target}', shell=True)
            except Exception as e:
                print(f"[FileOpener] Error hilo '{name}': {e}")
        t = threading.Thread(target=_launch, daemon=True)
        t.start()
        t.join(timeout=4)
        return True, target
    except Exception as e:
        print(f"[FileOpener] Error abriendo '{name}': {e}")
        return False, str(e)


# ── Buscar archivos ───────────────────────────────────────────────────────────

def _score_match(filename: str, query: str) -> float:
    """Puntúa qué tan bien coincide un nombre de archivo con la búsqueda."""
    fn = _normalize(Path(filename).stem)
    q  = _normalize(query)
    if fn == q:
        return 1.0
    if q in fn:
        return 0.85
    # Fuzzy
    ratio = difflib.SequenceMatcher(None, fn, q).ratio()
    # Bonus por palabras coincidentes
    fn_words = set(fn.split())
    q_words  = set(q.split())
    word_hit = len(fn_words & q_words) / max(len(q_words), 1)
    return max(ratio, word_hit * 0.8)


def _find_file(name: str, extension: str = "") -> list[dict]:
    """
    Busca un archivo en la PC.
    Retorna lista de {path, score, modified} ordenada por relevancia.
    """
    results = []
    query   = _normalize(name)
    ext_filter = extension.lower().strip(".")

    # 1. Revisar caché de memoria
    cached = _get_cached_path(name)
    if cached:
        results.append({"path": cached, "score": 1.1, "source": "cache"})

    # 2. Buscar en directorios prioritarios primero
    all_dirs = list(PRIORITY_DIRS)

    for d in all_dirs:
        if not d.exists():
            continue
        try:
            pattern = f"*.{ext_filter}" if ext_filter else "*"
            for f in d.rglob(pattern):
                if f.is_file() and f.suffix.lower() in OPENABLE_EXTS:
                    score = _score_match(f.name, query)
                    if score >= 0.55:
                        results.append({
                            "path":     str(f),
                            "score":    score,
                            "modified": f.stat().st_mtime,
                            "source":   "priority",
                        })
        except (PermissionError, OSError):
            continue

    # 3. Si no encontró nada bueno, buscar en toda la PC (con timeout de 15s)
    if not results or max(r["score"] for r in results) < 0.75:
        import threading as _th
        deadline = time.time() + 15   # máximo 15 segundos de búsqueda
        system_dirs = [BASE_USER, Path("C:/")]
        for sd in system_dirs:
            if not sd.exists() or time.time() > deadline:
                continue
            try:
                pattern = f"*.{ext_filter}" if ext_filter else "*"
                for f in sd.rglob(pattern):
                    if time.time() > deadline:
                        print("[FileOpener] Timeout en full_scan — usando resultados parciales")
                        break
                    parts = [p.lower() for p in f.parts]
                    if any(skip in parts for skip in
                           ["windows", "system32", "syswow64", "programdata",
                            "$recycle.bin", "winsxs", "drivers"]):
                        continue
                    if f.is_file() and f.suffix.lower() in OPENABLE_EXTS:
                        score = _score_match(f.name, query)
                        if score >= 0.70:
                            results.append({
                                "path":     str(f),
                                "score":    score,
                                "modified": f.stat().st_mtime,
                                "source":   "full_scan",
                            })
            except (PermissionError, OSError):
                continue

    # Ordenar por score desc, luego por modificación reciente
    results.sort(key=lambda x: (x["score"], x.get("modified", 0)), reverse=True)
    return results[:5]  # top 5


def _open_file(path: str) -> bool:
    """Abre un archivo en hilo separado — no bloquea."""
    import threading
    def _launch():
        try:
            os.startfile(path)
        except Exception:
            try:
                subprocess.Popen(f'start "" "{path}"', shell=True)
            except Exception as e:
                print(f"[FileOpener] Error abriendo archivo: {e}")
    t = threading.Thread(target=_launch, daemon=True)
    t.start()
    t.join(timeout=4)
    return True


# ── Función principal ─────────────────────────────────────────────────────────

def file_opener(parameters: dict, player=None, speak=None) -> str:
    """
    Abre archivos y software de la PC de forma inteligente.

    Parámetros:
        accion    : abrir | buscar | recientes
        nombre    : nombre del archivo o software
        tipo      : software | archivo | auto (default)
        extension : filtrar por extensión (pdf, docx, py, etc.)
        ruta      : ruta exacta si se conoce
    """
    from pathlib import Path
    import json

    accion    = (parameters.get("accion") or "abrir").lower().strip()
    nombre    = (parameters.get("nombre") or "").strip()
    tipo      = (parameters.get("tipo") or "auto").lower().strip()
    extension = (parameters.get("extension") or "").strip()
    ruta      = (parameters.get("ruta") or "").strip()

    # Cargar preferencias para apelativo
    try:
        base = Path(__file__).resolve().parent.parent
        pref = base / "config" / "preferences.json"
        call_me = json.loads(pref.read_text(encoding="utf-8")).get("call_me", "jefe") if pref.exists() else "jefe"
    except Exception:
        call_me = "jefe"

    if player:
        player.write_log(f"[FileOpener] accion='{accion}' nombre='{nombre}' tipo='{tipo}'")

    # ── RUTA EXACTA ───────────────────────────────────────────────────────────
    if ruta and Path(ruta).exists():
        ok = _open_file(ruta)
        if ok:
            _register_path(nombre or Path(ruta).name, ruta)
            if speak:
                speak(
                    f"Dile al usuario ({call_me}) que abriste el archivo en {ruta}. "
                    f"Con tu personalidad, breve."
                )
            return f"Abierto: {ruta}"
        else:
            if speak:
                speak(f"Dile al usuario ({call_me}) que no pudiste abrir {ruta}. Con tu personalidad.")
            return f"Error abriendo: {ruta}"

    if not nombre:
        if speak:
            speak(
                f"Pregúntale al usuario ({call_me}) qué archivo o programa quiere abrir. "
                f"Con tu personalidad."
            )
        return "Falta el nombre del archivo o programa."

    # ── ABRIR SOFTWARE ────────────────────────────────────────────────────────
    if tipo == "software" or (tipo == "auto" and not extension and
                              any(kw in _normalize(nombre) for kw in [
                                  "chrome", "firefox", "edge", "word", "excel",
                                  "powerpoint", "photoshop", "illustrator", "premiere",
                                  "spotify", "discord", "whatsapp", "telegram", "vscode",
                                  "notepad", "steam", "capcut", "canva", "vlc", "zoom",
                                  "terminal", "cmd", "calculadora", "explorador", "nvidia",
                              ])):
        ok, target = _open_software(nombre)
        if ok:
            if speak:
                speak(
                    f"Dile al usuario ({call_me}) que ya abriste {nombre}. "
                    f"Con tu personalidad, muy breve."
                )
            return f"Software abierto: {nombre} → {target}"
        else:
            if speak:
                speak(
                    f"Dile al usuario ({call_me}) que no encontraste {nombre} instalado. "
                    f"Con tu personalidad."
                )
            return f"No encontrado: {nombre}"

    # ── BUSCAR Y ABRIR ARCHIVO ────────────────────────────────────────────────
    if speak:
        speak(
            f"Dile al usuario ({call_me}) que ya vas a buscar '{nombre}' en la computadora. "
            f"Con tu personalidad, breve."
        )

    resultados = _find_file(nombre, extension)

    if not resultados:
        if speak:
            speak(
                f"Dile al usuario ({call_me}) que no encontraste ningún archivo llamado "
                f"'{nombre}' en la computadora. Con tu personalidad."
            )
        return f"Archivo no encontrado: '{nombre}'"

    mejor = resultados[0]

    # Score alto (>0.85) → abrir directo
    if mejor["score"] >= 0.85:
        ok = _open_file(mejor["path"])
        if ok:
            _register_path(nombre, mejor["path"])
            nombre_corto = Path(mejor["path"]).name
            if speak:
                speak(
                    f"Dile al usuario ({call_me}) que encontraste y abriste '{nombre_corto}'. "
                    f"Con tu personalidad."
                )
            return f"Abierto: {mejor['path']}"
        else:
            if speak:
                speak(f"Dile al usuario ({call_me}) que encontraste el archivo pero no pudiste abrirlo. Con tu personalidad.")
            return f"Error abriendo: {mejor['path']}"

    # Score medio (0.55-0.84) → confirmar con el usuario
    opciones = "\n".join(
        f"  {i+1}. {Path(r['path']).name} ({Path(r['path']).parent.name}/)"
        for i, r in enumerate(resultados[:3])
    )
    if speak:
        speak(
            f"Dile al usuario ({call_me}) que encontraste {len(resultados[:3])} archivos "
            f"parecidos a '{nombre}': {', '.join(Path(r['path']).name for r in resultados[:3])}. "
            f"Pregúntale cuál quiere abrir. Con tu personalidad."
        )
    return f"Archivos encontrados para '{nombre}':\n{opciones}"

    # ── ARCHIVOS RECIENTES ────────────────────────────────────────────────────
    if accion == "recientes":
        mem = _load_path_memory()
        if not mem:
            if speak:
                speak(
                    f"Dile al usuario ({call_me}) que todavía no tienes registros de archivos recientes. "
                    f"Con tu personalidad."
                )
            return "Sin archivos recientes registrados."
        # Ordenar por último acceso
        recientes = sorted(mem.items(), key=lambda x: x[1].get("ultimo", ""), reverse=True)[:5]
        lista = ", ".join(f"'{k}'" for k, _ in recientes)
        if speak:
            speak(
                f"Dile al usuario ({call_me}) que los archivos recientes son: {lista}. "
                f"Pregúntale cuál quiere abrir. Con tu personalidad."
            )
        return f"Recientes: {lista}"
