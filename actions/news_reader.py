# news_reader.py - Noticias del día para JARVIS
# Archivo: C:\Users\jose1\Mark-XXXIX\actions\news_reader.py

import urllib.request
import urllib.parse
import json
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Cache de noticias para no pedir cada vez
_cache = {"time": 0, "data": [], "categoria": ""}
_CACHE_TTL = 1800  # 30 minutos


def _fetch_news_rss(categoria: str = "general") -> list:
    """Obtiene noticias via RSS - sin API key necesaria."""
    feeds = {
        "general":      "https://feeds.bbci.co.uk/mundo/rss.xml",
        "tecnologia":   "https://feeds.bbci.co.uk/mundo/ciencia_y_tecnologia/rss.xml",
        "deportes":     "https://feeds.bbci.co.uk/mundo/deportes/rss.xml",
        "mexico":       "https://www.eluniversal.com.mx/rss.xml",
        "ciencia":      "https://feeds.bbci.co.uk/mundo/ciencia_y_tecnologia/rss.xml",
    }

    url = feeds.get(categoria, feeds["general"])
    noticias = []

    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 JARVIS/1.0"}
        )
        with urllib.request.urlopen(req, timeout=8) as r:
            content = r.read().decode("utf-8", errors="ignore")

        import re
        titles = re.findall(r'<title><!\[CDATA\[(.*?)\]\]></title>', content)
        if not titles:
            titles = re.findall(r'<title>(.*?)</title>', content)

        descs = re.findall(r'<description><!\[CDATA\[(.*?)\]\]></description>', content)
        if not descs:
            descs = re.findall(r'<description>(.*?)</description>', content)

        # Saltar el primer titulo (es el del feed)
        for i, title in enumerate(titles[1:8], 0):
            title = re.sub(r'<[^>]+>', '', title).strip()
            desc  = re.sub(r'<[^>]+>', '', descs[i]).strip() if i < len(descs) else ""
            if title and len(title) > 5:
                noticias.append({"titulo": title, "desc": desc[:120]})

    except Exception as e:
        print(f"[News] Error: {e}")

    return noticias


def news_reader(parameters: dict, player=None, speak=None) -> str:
    """
    Lee noticias del día.

    Acciones:
        leer      - Lee las noticias principales
        resumen   - Resumen breve de 3 noticias
        categoria - Noticias de categoría específica
    """
    global _cache

    accion    = parameters.get("accion", "leer").lower()
    categoria = parameters.get("categoria", "general").lower()
    cantidad  = int(parameters.get("cantidad", 5))

    now = time.time()

    # Usar cache si es reciente y misma categoria
    if (now - _cache["time"] < _CACHE_TTL and
            _cache["categoria"] == categoria and
            _cache["data"]):
        noticias = _cache["data"]
    else:
        if speak:
            speak("Dame un momento, buscando las noticias más recientes.")
        if player:
            player.write_log(f"[Noticias] Obteniendo noticias: {categoria}")

        noticias = _fetch_news_rss(categoria)
        _cache = {"time": now, "data": noticias, "categoria": categoria}

    if not noticias:
        msg = "No pude obtener las noticias en este momento. Verifica tu conexión."
        if speak: speak(msg)
        return msg

    # Formatear respuesta
    cantidad = min(cantidad, len(noticias))
    seleccion = noticias[:cantidad]

    if accion == "resumen":
        # Resumen muy breve
        titulos = [f"{i+1}. {n['titulo']}" for i, n in enumerate(seleccion[:3])]
        msg = "Las 3 noticias más importantes: " + ". ".join(titulos)
    else:
        # Lectura completa
        partes = [f"Aquí están las {cantidad} noticias principales de hoy:"]
        for i, n in enumerate(seleccion, 1):
            partes.append(f"Noticia {i}: {n['titulo']}.")
        msg = " ".join(partes)

    if player:
        for n in seleccion:
            player.write_log(f"[Noticia] {n['titulo'][:70]}")

    if speak:
        speak(msg)

    return msg
