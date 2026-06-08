# flight_search.py - Busqueda y reserva de vuelos para JARVIS Mark XXXIX
# Archivo: C:\Users\jose1\Mark-XXXIX\actions\flight_search.py

import time
import re
import subprocess
import tempfile
import os
from pathlib import Path
from datetime import datetime, timedelta

BASE_DIR = Path(__file__).resolve().parent.parent

_estado = {
    "vuelos":     [],
    "origen":     "",
    "destino":    "",
    "fecha":      "",
    "page":       None,
    "browser":    None,
    "playwright": None,
}


def _parse_fecha(texto):
    texto = texto.lower().strip()
    hoy   = datetime.now()
    if "hoy"    in texto: return hoy.strftime("%Y-%m-%d")
    if "mañana" in texto or "manana" in texto:
        return (hoy + timedelta(days=1)).strftime("%Y-%m-%d")
    meses = {
        "enero":"01","febrero":"02","marzo":"03","abril":"04",
        "mayo":"05","junio":"06","julio":"07","agosto":"08",
        "septiembre":"09","octubre":"10","noviembre":"11","diciembre":"12",
    }
    for m, n in meses.items():
        texto = texto.replace(m, n)
    for fmt in ["%Y-%m-%d","%d/%m/%Y","%d-%m-%Y","%d %m %Y"]:
        try:
            return datetime.strptime(texto.strip(), fmt).strftime("%Y-%m-%d")
        except Exception:
            continue
    return texto


def _cerrar_anterior():
    global _estado
    for key in ["browser", "playwright"]:
        try:
            if _estado[key]:
                _estado[key].close() if key == "browser" else _estado[key].stop()
        except Exception:
            pass
        _estado[key] = None
    _estado["page"]   = None
    _estado["vuelos"] = []


def _abrir_browser():
    """Abre Playwright con perfil temporal para no conflictuar con Chrome abierto."""
    from playwright.sync_api import sync_playwright
    _cerrar_anterior()
    time.sleep(1)

    # Crear directorio temporal para el perfil
    tmp_dir = Path(tempfile.gettempdir()) / "jarvis_flights_profile"
    tmp_dir.mkdir(exist_ok=True)

    p = sync_playwright().start()

    # Usar perfil temporal — evita conflicto con Chrome abierto
    browser = p.chromium.launch_persistent_context(
        user_data_dir=str(tmp_dir),
        channel="chrome",
        headless=False,
        args=[
            "--start-maximized",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-blink-features=AutomationControlled",
            "--disable-infobars",
        ],
        no_viewport=True,
        locale="es-MX",
    )

    pages = browser.pages
    page  = pages[0] if pages else browser.new_page()

    _estado["playwright"] = p
    _estado["browser"]    = browser
    _estado["page"]       = page
    return page


def _extraer_vuelos(page):
    vuelos = []
    try:
        time.sleep(6)
        selectores = [
            "li.pIav2d",
            "[data-gs]",
            ".yR1fYc",
            "div.OgQvJf",
            "li[jsname='IWWDBc']",
        ]
        elementos = []
        for sel in selectores:
            try:
                elems = page.query_selector_all(sel)
                if len(elems) > 0:
                    elementos = elems
                    print(f"[Flights] Selector: {sel} ({len(elems)} resultados)")
                    break
            except Exception:
                continue

        for i, elem in enumerate(elementos[:6]):
            try:
                texto = elem.inner_text().strip()
                if not texto or len(texto) < 15:
                    continue
                precio    = ""
                match     = re.search(r'\$[\d,]+|[\d,]{3,}\s*MXN', texto)
                if match:
                    precio = match.group(0)
                aerolinea = ""
                for a in ["Aeromexico","Volaris","Viva Aerobus","American",
                          "United","Delta","Interjet","Air Canada","Iberia"]:
                    if a.lower() in texto.lower():
                        aerolinea = a
                        break
                horas = re.findall(r'\d{1,2}:\d{2}', texto)
                vuelos.append({
                    "numero":    i + 1,
                    "texto":     texto[:250],
                    "precio":    precio,
                    "aerolinea": aerolinea,
                    "horas":     horas[:2] if horas else [],
                    "elemento":  elem,
                })
            except Exception:
                continue
    except Exception as e:
        print(f"[Flights] Extraccion error: {e}")
    return vuelos


def _resumir(vuelos, origen, destino):
    if not vuelos:
        return f"Abrí Google Flights para {origen} → {destino}. Revise Chrome."
    lineas = [f"Vuelos de {origen} a {destino}:\n"]
    for v in vuelos[:5]:
        l = f"  {v['numero']}."
        if v.get("aerolinea"):
            l += f" {v['aerolinea']}"
        if v.get("horas") and len(v["horas"]) >= 2:
            l += f" | {v['horas'][0]} → {v['horas'][1]}"
        if v.get("precio"):
            l += f" | {v['precio']}"
        lineas.append(l)
    lineas.append('\nDiga "reserva el 1" o "reserva el 2" para continuar.')
    return "\n".join(lineas)


def flight_search(parameters, player=None, speak=None):
    global _estado

    origen       = parameters.get("origen","").strip()
    destino      = parameters.get("destino","").strip()
    fecha_ida    = parameters.get("fecha_ida", parameters.get("fecha","")).strip()
    fecha_vuelta = parameters.get("fecha_vuelta","").strip()
    pasajeros    = int(parameters.get("pasajeros", 1))
    accion       = parameters.get("accion","buscar").lower()
    num_vuelo    = int(parameters.get("numero_vuelo", 1))

    # ── RESERVAR ─────────────────────────────────────────────────────────────
    if accion == "reservar":
        vuelos = _estado.get("vuelos", [])
        page   = _estado.get("page")
        if not vuelos or not page:
            return "Jefe, primero busquemos vuelos."
        idx   = max(0, min(num_vuelo - 1, len(vuelos) - 1))
        vuelo = vuelos[idx]
        if speak:
            speak(f"Seleccionando el vuelo {num_vuelo}, jefe.")
        try:
            elem = vuelo.get("elemento")
            if elem:
                elem.scroll_into_view_if_needed()
                time.sleep(0.5)
                elem.click()
                time.sleep(3)
                for sel in ["text=Seleccionar","text=Select","text=Reservar",
                            "text=Elegir","text=Ver oferta","text=Continuar"]:
                    try:
                        btn = page.query_selector(sel)
                        if btn and btn.is_visible():
                            btn.click()
                            time.sleep(3)
                            break
                    except Exception:
                        continue
                if speak:
                    speak(f"Listo jefe, seleccioné el vuelo {num_vuelo}. Complete sus datos para confirmar.")
                return f"Vuelo {num_vuelo} seleccionado. Proceda con sus datos."
            else:
                return "No pude hacer clic. Haga clic manualmente en Chrome."
        except Exception as e:
            return f"Error al seleccionar: {str(e)[:100]}"

    # ── BUSCAR ────────────────────────────────────────────────────────────────
    if not origen or not destino or not fecha_ida:
        return "Jefe, necesito origen, destino y fecha."

    fecha_fmt = _parse_fecha(fecha_ida)

    if speak:
        speak(f"Buscando vuelos de {origen} a {destino} para el {fecha_ida}, jefe. Abriendo Chrome.")
    if player:
        player.write_log(f"[Flights] {origen} → {destino} | {fecha_fmt}")

    try:
        page = _abrir_browser()

        # Google Flights
        url_gf = (
            f"https://www.google.com/travel/flights?"
            f"hl=es&q=vuelos+{origen.replace(' ','+')}+"
            f"{destino.replace(' ','+')}+{fecha_fmt}"
        )
        if player:
            player.write_log(f"[Flights] Abriendo: {url_gf}")

        page.goto(url_gf, timeout=30000)
        page.wait_for_load_state("domcontentloaded", timeout=15000)
        time.sleep(5)

        vuelos = _extraer_vuelos(page)
        _estado["vuelos"]  = vuelos
        _estado["origen"]  = origen
        _estado["destino"] = destino
        _estado["fecha"]   = fecha_fmt

        # Kayak pestaña nueva
        try:
            p2 = _estado["browser"].new_page()
            p2.goto(
                f"https://www.kayak.com.mx/flights/"
                f"{origen.replace(' ','-')}-{destino.replace(' ','-')}/{fecha_fmt}",
                timeout=20000
            )
            time.sleep(2)
        except Exception as e:
            print(f"[Flights] Kayak: {e}")

        # Skyscanner pestaña nueva
        try:
            p3 = _estado["browser"].new_page()
            p3.goto(
                f"https://www.skyscanner.com.mx/transport/flights/"
                f"{origen.replace(' ','-')}/{destino.replace(' ','-')}/"
                f"{fecha_fmt.replace('-','')}/ ",
                timeout=20000
            )
            time.sleep(2)
        except Exception as e:
            print(f"[Flights] Skyscanner: {e}")

        # Volver a Google Flights
        page.bring_to_front()

        resumen = _resumir(vuelos, origen, destino)

        if speak:
            if vuelos:
                v0  = vuelos[0]
                msg = f"Encontré {len(vuelos)} vuelos de {origen} a {destino}. "
                if v0.get("precio"):
                    msg += f"Desde {v0['precio']}. "
                if v0.get("aerolinea"):
                    msg += f"Con {v0['aerolinea']}. "
                msg += "También abrí Kayak y Skyscanner. ¿Cuál le interesa? Dígame el número."
            else:
                msg = (
                    f"Abrí Google Flights, Kayak y Skyscanner para {origen} a {destino}, jefe. "
                    f"Revise los resultados. Cuando vea el que le gusta dígame el número."
                )
            speak(msg)

        return resumen

    except Exception as e:
        print(f"[Flights] Error: {e}")
        import traceback
        traceback.print_exc()
        # Fallback con subprocess
        try:
            url = f"https://www.google.com/travel/flights?q=vuelos+{origen}+{destino}"
            subprocess.Popen([
                "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
                url
            ])
            if speak:
                speak(f"Abrí Chrome con la búsqueda, jefe.")
        except Exception:
            pass
        return f"Abrí Chrome con la búsqueda. Error: {str(e)[:80]}"
