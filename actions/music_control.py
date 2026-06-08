# music_control.py - Música via YouTube con aprendizaje de preferencias
# Archivo: C:\Users\jose1\Mark-XXXIX\actions\music_control.py
#
# CÓMO FUNCIONA speak():
#   speak("instrucción") → Gemini Live reformula con la personalidad activa
#   NUNCA hardcodeamos frases literales para el usuario.
#   Usamos instrucciones descriptivas que Gemini interpreta y adapta.

import subprocess
import urllib.parse
import time
import json
from datetime import datetime
from pathlib import Path


# ── Helpers del sistema ───────────────────────────────────────────────────────

def _edge(url: str):
    try:
        subprocess.Popen(f'start msedge "{url}"', shell=True)
        time.sleep(0.5)
    except Exception as e:
        print(f"[Musica] Error abriendo Edge: {e}")


def _media_key(code: int):
    try:
        subprocess.run(
            ["powershell", "-Command",
             f"$w = New-Object -com 'WScript.Shell'; $w.SendKeys([char]{code})"],
            capture_output=True, timeout=4
        )
    except Exception as e:
        print(f"[Musica] Error tecla multimedia {code}: {e}")


def _play_youtube(query: str):
    if not query or not query.strip():
        _edge("https://www.youtube.com")
        return
    q   = urllib.parse.quote(query.strip())
    url = f"https://www.youtube.com/results?search_query={q}"
    _edge(url)


# ── Preferencias del usuario ──────────────────────────────────────────────────

def _load_user_prefs() -> dict:
    try:
        base = Path(__file__).resolve().parent.parent
        pref = base / "config" / "preferences.json"
        if pref.exists():
            return json.loads(pref.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[Musica] Error leyendo prefs: {e}")
    return {}


def _get_call_me() -> str:
    return _load_user_prefs().get("call_me", "jefe")


# ── Memoria musical ───────────────────────────────────────────────────────────

def _load_music_memory() -> dict:
    """
    Estructura:
    {
      "historial": [
        {"query": "Bad Bunny", "veces": 5, "ts": "2026-06-01", "ultimo": "2026-06-07 09:00"},
        ...
      ],
      "total_reproducciones": 12
    }
    """
    try:
        from memory.memory_manager import load_memory
        mem = load_memory()
        raw = mem.get("preferencias", {}).get("musica_historial", {})
        if isinstance(raw, dict) and "value" in raw:
            data = json.loads(raw["value"])
            if isinstance(data, dict) and "historial" in data:
                return data
    except Exception as e:
        print(f"[Musica] Error cargando memoria: {e}")
    return {"historial": [], "total_reproducciones": 0}


def _save_music_memory(music_mem: dict):
    try:
        from memory.memory_manager import update_memory
        update_memory({
            "preferencias": {
                "musica_historial": {
                    "value": json.dumps(music_mem, ensure_ascii=False)
                }
            }
        })
    except Exception as e:
        print(f"[Musica] Error guardando memoria: {e}")


def _register_play(query: str) -> dict:
    """Registra reproducción. Retorna memoria actualizada con veces de ese query."""
    if not query or not query.strip():
        return _load_music_memory()

    music_mem = _load_music_memory()
    historial = music_mem.get("historial", [])
    ts        = datetime.now().strftime("%Y-%m-%d %H:%M")
    q_norm    = query.lower().strip()

    encontrado = False
    for entry in historial:
        if entry.get("query", "").lower().strip() == q_norm:
            entry["veces"]  = entry.get("veces", 1) + 1
            entry["ultimo"] = ts
            encontrado = True
            break

    if not encontrado:
        historial.append({"query": query.strip(), "veces": 1, "ts": ts, "ultimo": ts})

    historial.sort(key=lambda x: x.get("veces", 1), reverse=True)
    music_mem["historial"]            = historial[:50]
    music_mem["total_reproducciones"] = music_mem.get("total_reproducciones", 0) + 1
    _save_music_memory(music_mem)
    print(f"[Musica] Registrado '{query}' — total: {music_mem['total_reproducciones']}")
    return music_mem


def _get_veces(music_mem: dict, query: str) -> int:
    """Cuántas veces se ha reproducido un query específico."""
    q_norm = query.lower().strip()
    for e in music_mem.get("historial", []):
        if e.get("query", "").lower().strip() == q_norm:
            return e.get("veces", 1)
    return 1


def _get_smart_suggestion(music_mem: dict) -> str:
    """
    Elige el mejor candidato del historial:
    - Favorito claro: el primero tiene ≥ (segundo*1.5 + 2)
    - Empate: el más reciente entre el top 3
    """
    historial = music_mem.get("historial", [])
    if not historial:
        return ""
    if len(historial) == 1:
        return historial[0]["query"]

    top = historial[:3]
    v1  = top[0].get("veces", 1)
    v2  = top[1].get("veces", 1)

    if v1 >= max(v2 * 1.5, v2 + 2):
        return top[0]["query"]

    return max(top, key=lambda x: x.get("ultimo", x.get("ts", "")))["query"]


def _top_resumen(music_mem: dict, n: int = 3) -> str:
    items = music_mem.get("historial", [])[:n]
    if not items:
        return "ninguna aún"
    return ", ".join(f"'{e['query']}' ({e.get('veces',1)}x)" for e in items)


# ── Función principal ─────────────────────────────────────────────────────────

def music_control(parameters: dict, player=None, speak=None) -> str:
    accion  = (parameters.get("accion") or "reproducir").lower().strip()
    cancion = (parameters.get("cancion") or "").strip()
    call_me = _get_call_me()

    if player:
        player.write_log(f"[Musica] accion='{accion}' cancion='{cancion}'")

    # ── CONTROLES MULTIMEDIA ──────────────────────────────────────────────────
    media_keys = {
        "siguiente": 176, "next": 176,
        "anterior":  177, "prev": 177,
        "pausa":     179, "pausar": 179, "pause": 179,
        "reanudar":  179, "resume": 179,
        "subir":     175,
        "bajar":     174,
        "mute":      173, "silenciar": 173,
    }

    respuestas_control = {
        176: f"Siguiente canción ya, {call_me}.",
        177: f"Canción anterior, {call_me}.",
        179: f"Pausa/reanudar.",
        175: f"Volumen subido.",
        174: f"Volumen bajado.",
        173: f"Silenciado.",
    }

    if accion in media_keys:
        code = media_keys[accion]
        _media_key(code)
        if speak:
            speak(
                f"Di brevemente al usuario ({call_me}) que ejecutaste la acción de "
                f"'{accion}' en la música. Con tu personalidad, muy corto."
            )
        return f"Control: {accion} (código {code})"

    # ── HISTORIAL ─────────────────────────────────────────────────────────────
    if accion in ("historial", "mis canciones", "que he escuchado"):
        music_mem = _load_music_memory()
        total     = music_mem.get("total_reproducciones", 0)
        if total == 0:
            if speak:
                speak(
                    f"Dile al usuario ({call_me}) que todavía no tienes registro de su música, "
                    f"que ponga algo y empezarás a aprender sus gustos. Con tu personalidad."
                )
            return "Sin historial aún."
        resumen = _top_resumen(music_mem, 5)
        if speak:
            speak(
                f"Dile al usuario ({call_me}) que ha escuchado {total} canciones en total "
                f"y que sus favoritas son: {resumen}. Con tu personalidad, natural."
            )
        return f"Historial: {resumen} — {total} reproducciones."

    # ── REPRODUCCIÓN ─────────────────────────────────────────────────────────
    acciones_play = {
        "buscar", "reproducir", "reproduce", "poner", "pon", "escuchar",
        "play cancion", "play", "abrir", "quiero escuchar", "quiero",
        "música", "musica", "pone", "ponme",
    }

    if accion in acciones_play or not accion:

        # ── CON CANCIÓN ESPECÍFICA ────────────────────────────────────────────
        if cancion:
            _play_youtube(cancion)
            music_mem = _register_play(cancion)
            veces     = _get_veces(music_mem, cancion)

            if veces == 1:
                # Primera vez este artista/canción
                if speak:
                    speak(
                        f"Dile al usuario ({call_me}) que ya buscaste '{cancion}' en YouTube "
                        f"y que es la primera vez que lo escucha contigo, que vas a recordar "
                        f"que le gusta y que cada vez que reproduzca música aprendes más de sus gustos. "
                        f"Con tu personalidad, breve y natural."
                    )
            elif 2 <= veces <= 4:
                if speak:
                    speak(
                        f"Dile al usuario ({call_me}) que ya pusiste '{cancion}' otra vez "
                        f"(lo ha pedido {veces} veces). Con tu personalidad, breve."
                    )
            else:
                # Favorito establecido
                if speak:
                    speak(
                        f"Dile al usuario ({call_me}) que ya pusiste '{cancion}' — "
                        f"lo ha pedido {veces} veces, ya sabes que es de sus favoritos. "
                        f"Con tu personalidad, como si ya lo conocieras bien."
                    )

            return f"Reproduciendo '{cancion}' (veces: {veces})"

        # ── SIN CANCIÓN: revisar historial ────────────────────────────────────
        music_mem  = _load_music_memory()
        total      = music_mem.get("total_reproducciones", 0)
        sugerencia = _get_smart_suggestion(music_mem)

        if total == 0:
            # ── PRIMERA VEZ ABSOLUTA ─────────────────────────────────────────
            if speak:
                speak(
                    f"Dile al usuario ({call_me}) que es su primera vez poniendo música contigo. "
                    f"Pregúntale qué artista o género quiere escuchar. "
                    f"Explícale que cada vez que reproduzca música aprenderás sus gustos "
                    f"y que luego lo pondrás automáticamente sin que te lo pida. "
                    f"Con tu personalidad, entusiasta pero breve."
                )
            if player:
                player.write_log("[Musica] Primera vez — esperando preferencia")
            return "Primera vez: esperando preferencia del usuario."

        elif sugerencia:
            # ── AUTO-PLAY: tiene favorito claro ──────────────────────────────
            _play_youtube(sugerencia)
            music_mem_updated = _register_play(sugerencia)
            veces_fav = _get_veces(music_mem_updated, sugerencia)

            if speak:
                speak(
                    f"Dile al usuario ({call_me}) que ya pusiste '{sugerencia}' "
                    f"automáticamente porque es lo que más escucha (lo has reproducido {veces_fav} veces). "
                    f"Dilo con tu personalidad — algo como 'lo mismo de siempre' o 'ya sé lo que te gusta', "
                    f"variando según tu personalidad activa. Muy breve."
                )
            if player:
                player.write_log(f"[Musica] Auto-play: '{sugerencia}' ({veces_fav}x)")
            return f"Auto-play: '{sugerencia}'"

        else:
            # ── TIENE HISTORIAL PERO SIN FAVORITO CLARO ──────────────────────
            resumen = _top_resumen(music_mem, 3)
            if speak:
                speak(
                    f"Pregúntale al usuario ({call_me}) qué quiere escuchar hoy. "
                    f"Puedes mencionar sus canciones recientes: {resumen}. "
                    f"Con tu personalidad."
                )
            return "Sin favorito claro: esperando elección del usuario."

    # ── FALLBACK ─────────────────────────────────────────────────────────────
    if cancion:
        _play_youtube(cancion)
        _register_play(cancion)
        if speak:
            speak(
                f"Dile brevemente al usuario ({call_me}) que ya pusiste '{cancion}'. "
                f"Con tu personalidad."
            )
        return f"Fallback: reproduciendo '{cancion}'"

    if speak:
        speak(
            f"Pregúntale al usuario ({call_me}) qué música quiere escuchar. "
            f"Con tu personalidad."
        )
    return "Sin acción reconocida."
