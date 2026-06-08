# canva_presenter.py - Control real de Canva para JARVIS Mark XXXIX
# Archivo: C:\Users\jose1\Mark-XXXIX\actions\canva_presenter.py
# Requiere: pip install playwright pyperclip
#           python -m playwright install chromium

import time
import json
import subprocess
import pyperclip
from pathlib import Path

BASE_DIR    = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"

# ── Coordenadas del editor Canva (basadas en las capturas) ───────────────────
# Canvas center aproximado en pantalla 1920x1080
CANVAS_CENTER_X = 762
CANVAS_CENTER_Y = 455

# Panel izquierdo botones (x fijo ~34)
BTN_PLANTILLAS = (34, 180)
BTN_ELEMENTOS  = (34, 248)
BTN_TEXTO      = (34, 315)

# Dentro del panel Texto
BTN_AGREGAR_TITULO    = (231, 479)
BTN_AGREGAR_SUBTITULO = (231, 539)
BTN_AGREGAR_TEXTO     = (231, 593)
BTN_CAJA_TEXTO        = (238, 245)

# Boton agregar pagina
BTN_AGREGAR_PAGINA = (748, 651)


def _get_gemini_key():
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8")).get("gemini_api_key", "")
    except Exception:
        return ""


def _investigar_tema(tema, num_slides=6):
    """Genera contenido estructurado para las diapositivas usando Gemini."""
    try:
        import sys
        sys.path.insert(0, str(BASE_DIR / "actions"))
        from gemini_helper import ask_gemini_json

        prompt = f"""Eres experto en presentaciones escolares elegantes.
Genera contenido para {num_slides} diapositivas sobre: "{tema}"

Responde SOLO JSON valido:
{{
  "titulo": "Titulo atractivo del tema",
  "subtitulo": "Subtitulo descriptivo",
  "diapositivas": [
    {{
      "num": 1,
      "tipo": "portada",
      "titulo": "Titulo grande",
      "subtitulo": "subtitulo",
      "puntos": [],
      "buscar_imagen": "keyword in english"
    }},
    {{
      "num": 2,
      "tipo": "contenido",
      "titulo": "Introduccion",
      "subtitulo": "",
      "puntos": ["Punto 1 corto", "Punto 2 corto", "Punto 3 corto"],
      "buscar_imagen": "keyword in english"
    }}
  ]
}}

Reglas:
- Diapo 1: portada (solo titulo y subtitulo grandes)
- Diapos 2 a {num_slides-1}: contenido con titulo + 3-4 puntos breves
- Diapo {num_slides}: conclusion con titulo + 2-3 puntos
- Puntos max 6 palabras cada uno
- buscar_imagen: 1-2 palabras en ingles para buscar en Canva
- Idioma: espanol"""

        return ask_gemini_json(prompt)
    except Exception as e:
        print("[Canva] Gemini error: " + str(e))
        return None


def _pegar(page, texto):
    """Pega texto usando clipboard (evita problemas con caracteres especiales)."""
    try:
        pyperclip.copy(str(texto))
        page.keyboard.press("Control+a")
        time.sleep(0.2)
        page.keyboard.press("Control+v")
        time.sleep(0.3)
    except Exception:
        page.keyboard.type(str(texto), delay=40)


def _click_panel_texto(page):
    """Abre el panel de Texto en el sidebar izquierdo."""
    try:
        # Buscar icono T en sidebar
        texto_btn = page.query_selector("text=Texto")
        if texto_btn:
            texto_btn.click()
        else:
            page.mouse.click(BTN_TEXTO[0], BTN_TEXTO[1])
        time.sleep(1.5)
    except Exception as e:
        print("[Canva] click_panel_texto: " + str(e))


def _agregar_titulo(page, texto, x, y, tamano=48, negrita=True):
    """
    Agrega un titulo en la posicion dada.
    Hace clic en 'Agregar un titulo' del panel y luego lo mueve.
    """
    try:
        _click_panel_texto(page)
        time.sleep(0.5)

        # Doble clic en "Agregar un título"
        titulo_elem = page.query_selector("text=Agregar un título")
        if titulo_elem:
            titulo_elem.dblclick()
        else:
            page.mouse.dblclick(BTN_AGREGAR_TITULO[0], BTN_AGREGAR_TITULO[1])
        time.sleep(1.5)

        # Seleccionar todo y pegar
        page.keyboard.press("Control+a")
        time.sleep(0.2)
        _pegar(page, texto)
        time.sleep(0.5)

        # Escapar para deseleccionar texto (pero mantenemos el elemento seleccionado)
        page.keyboard.press("Escape")
        time.sleep(0.5)

        return True
    except Exception as e:
        print("[Canva] agregar_titulo error: " + str(e))
        return False


def _agregar_subtitulo(page, texto):
    """Agrega un subtitulo usando el boton del panel."""
    try:
        _click_panel_texto(page)
        time.sleep(0.5)
        sub_elem = page.query_selector("text=Agregar un subtítulo")
        if sub_elem:
            sub_elem.dblclick()
        else:
            page.mouse.dblclick(BTN_AGREGAR_SUBTITULO[0], BTN_AGREGAR_SUBTITULO[1])
        time.sleep(1.5)
        page.keyboard.press("Control+a")
        time.sleep(0.2)
        _pegar(page, texto)
        time.sleep(0.5)
        page.keyboard.press("Escape")
        time.sleep(0.3)
        return True
    except Exception as e:
        print("[Canva] agregar_subtitulo error: " + str(e))
        return False


def _agregar_caja_texto(page, texto):
    """Agrega una caja de texto libre con el boton 'Agregar caja de texto'."""
    try:
        _click_panel_texto(page)
        time.sleep(0.5)
        caja_btn = page.query_selector("text=Agregar caja de texto")
        if caja_btn:
            caja_btn.click()
        else:
            page.mouse.click(BTN_CAJA_TEXTO[0], BTN_CAJA_TEXTO[1])
        time.sleep(1.5)
        page.keyboard.press("Control+a")
        time.sleep(0.2)
        _pegar(page, texto)
        time.sleep(0.5)
        page.keyboard.press("Escape")
        time.sleep(0.3)
        return True
    except Exception as e:
        print("[Canva] agregar_caja_texto error: " + str(e))
        return False


def _agregar_pagina(page):
    """Hace clic en '+ Agregar una página'."""
    try:
        btn = page.query_selector("text=Agregar una página")
        if not btn:
            btn = page.query_selector("text=+ Agregar una página")
        if btn:
            btn.click()
        else:
            page.mouse.click(BTN_AGREGAR_PAGINA[0], BTN_AGREGAR_PAGINA[1])
        time.sleep(2)
        return True
    except Exception as e:
        print("[Canva] agregar_pagina error: " + str(e))
        return False


def _buscar_plantilla(page, keyword="presentacion escolar moderna"):
    """Busca y aplica una plantilla del panel izquierdo."""
    try:
        # Clic en Plantillas
        plant_btn = page.query_selector("text=Plantillas")
        if plant_btn:
            plant_btn.click()
        else:
            page.mouse.click(BTN_PLANTILLAS[0], BTN_PLANTILLAS[1])
        time.sleep(2)

        # Buscar plantilla
        search = page.query_selector("input[placeholder*='Busca']")
        if not search:
            search = page.query_selector("input[type='search']")
        if search:
            search.click()
            time.sleep(0.5)
            page.keyboard.press("Control+a")
            _pegar(page, keyword)
            page.keyboard.press("Enter")
            time.sleep(3)

            # Clic en la primera plantilla
            plantillas = page.query_selector_all("[data-testid='template-item']")
            if not plantillas:
                # Intentar selector alternativo
                plantillas = page.query_selector_all(".templateItem")
            if plantillas and len(plantillas) > 0:
                plantillas[0].click()
                time.sleep(2)
                return True
        return False
    except Exception as e:
        print("[Canva] buscar_plantilla error: " + str(e))
        return False


def _buscar_imagen_elementos(page, keyword):
    """Busca imagenes en el panel Elementos y agrega la primera."""
    try:
        # Clic en Elementos
        elem_btn = page.query_selector("text=Elementos")
        if elem_btn:
            elem_btn.click()
        else:
            page.mouse.click(BTN_ELEMENTOS[0], BTN_ELEMENTOS[1])
        time.sleep(2)

        # Buscar
        search = page.query_selector("input[placeholder*='Busca']")
        if not search:
            search = page.query_selector("input[type='search']")
        if search:
            search.click()
            time.sleep(0.3)
            page.keyboard.press("Control+a")
            _pegar(page, keyword)
            page.keyboard.press("Enter")
            time.sleep(3)

            # Clic en primer resultado
            imgs = page.query_selector_all("[data-testid='element-item']")
            if not imgs:
                imgs = page.query_selector_all(".elementItem")
            if imgs and len(imgs) > 0:
                imgs[0].dblclick()
                time.sleep(1.5)
                return True
        return False
    except Exception as e:
        print("[Canva] buscar_imagen error: " + str(e))
        return False


def canva_presenter(parameters, player=None, speak=None):
    """
    Controla Canva como un humano para crear presentaciones.

    Parametros:
        tema   : tema de la presentacion
        slides : numero de diapositivas (default 6)
        estilo : moderno | elegante | colorido | minimalista
    """
    tema   = parameters.get("tema", parameters.get("topic", "")).strip()
    slides = int(parameters.get("slides", 6))
    estilo = parameters.get("estilo", "moderno")

    if not tema:
        return "Dime el tema de la presentacion, jefe."

    # Paso 1 — Investigar con Gemini
    if speak:
        speak(f"Investigando '{tema}', jefe. Un momento.")
    if player:
        player.write_log(f"[Canva] Investigando: {tema}")

    contenido = _investigar_tema(tema, slides)
    if not contenido:
        contenido = {
            "titulo": tema.title(),
            "subtitulo": f"Presentacion sobre {tema}",
            "diapositivas": [
                {
                    "num": i+1,
                    "tipo": "portada" if i == 0 else "contenido",
                    "titulo": tema.title() if i == 0 else f"Parte {i}",
                    "subtitulo": f"Subtitulo {i+1}",
                    "puntos": ["Punto importante", "Informacion clave", "Dato relevante"],
                    "buscar_imagen": tema.split()[0]
                }
                for i in range(slides)
            ]
        }

    diapos = contenido.get("diapositivas", [])
    if player:
        player.write_log(f"[Canva] {len(diapos)} diapositivas generadas.")

    # Paso 2 — Abrir Canva con Playwright usando el perfil con sesion
    try:
        from playwright.sync_api import sync_playwright

        if speak:
            speak("Listo, jefe. Abriendo Canva ahora.")

        p       = sync_playwright().start()
        browser = p.chromium.launch_persistent_context(
            user_data_dir="C:\\Users\\jose1\\AppData\\Local\\Google\\Chrome\\User Data",
            channel="chrome",
            headless=False,
            args=[
                "--profile-directory=Profile 10",
                "--start-maximized",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-blink-features=AutomationControlled",
            ],
            no_viewport=True,
        )

        pages = browser.pages
        page  = pages[0] if pages else browser.new_page()

        # Ir a Canva crear nueva presentacion
        page.goto(
            "https://www.canva.com/design?create&type=Tqvu1zX5tOc&category=tACZCji4jvU",
            timeout=30000
        )
        page.wait_for_load_state("domcontentloaded", timeout=20000)
        time.sleep(6)

        if player:
            player.write_log("[Canva] Editor abierto. Buscando plantilla...")

        # Paso 3 — Buscar plantilla segun estilo
        plantilla_keywords = {
            "moderno":      "presentacion escolar moderna azul",
            "elegante":     "presentacion elegante oscura minimalista",
            "colorido":     "presentacion colorida educativa",
            "minimalista":  "presentacion minimalista blanca limpia",
        }
        kw_plantilla = plantilla_keywords.get(estilo, "presentacion escolar moderna")
        plantilla_ok = _buscar_plantilla(page, kw_plantilla)

        if speak:
            if plantilla_ok:
                speak(f"Plantilla aplicada, jefe. Ahora voy a agregar el contenido de '{tema}'.")
            else:
                speak(f"No encontre plantilla, jefe. Creando desde cero.")

        time.sleep(2)

        # Paso 4 — Construir diapositiva por diapositiva
        for i, diapo in enumerate(diapos):
            if player:
                player.write_log(f"[Canva] Diapo {i+1}/{len(diapos)}: {diapo.get('titulo', '')}")

            # Clic en el canvas para asegurarnos de estar en la diapo correcta
            page.mouse.click(CANVAS_CENTER_X, CANVAS_CENTER_Y)
            time.sleep(1)

            titulo_diapo  = diapo.get("titulo", "")
            subtitulo_diapo = diapo.get("subtitulo", "")
            puntos        = diapo.get("puntos", [])
            tipo          = diapo.get("tipo", "contenido")
            img_kw        = diapo.get("buscar_imagen", "")

            if tipo == "portada":
                # Agregar titulo grande
                if titulo_diapo:
                    _agregar_titulo(page, titulo_diapo)
                    time.sleep(1)
                # Agregar subtitulo
                if subtitulo_diapo:
                    _agregar_subtitulo(page, subtitulo_diapo)
                    time.sleep(1)
                # Agregar imagen de fondo relacionada
                if img_kw:
                    _buscar_imagen_elementos(page, img_kw)
                    time.sleep(1)

            else:
                # Agregar titulo de seccion
                if titulo_diapo:
                    _agregar_titulo(page, titulo_diapo)
                    time.sleep(1)

                # Agregar puntos como caja de texto
                if puntos:
                    texto_puntos = "\n".join(["• " + p for p in puntos])
                    _agregar_caja_texto(page, texto_puntos)
                    time.sleep(1)

                # Agregar imagen relacionada al tema
                if img_kw and i % 2 == 0:  # Imagen en diapos pares
                    _buscar_imagen_elementos(page, img_kw)
                    time.sleep(1)

            # Agregar nueva pagina si no es la ultima
            if i < len(diapos) - 1:
                _agregar_pagina(page)
                time.sleep(1.5)

        # Paso 5 — Guardar (Canva guarda automaticamente, solo confirmamos)
        time.sleep(2)
        page.keyboard.press("Escape")
        time.sleep(1)

        if speak:
            speak(
                f"¡Lista, jefe! La presentacion de '{tema}' esta completa en Canva con {len(diapos)} diapositivas. "
                f"Canva la guardo automaticamente. Puede revisarla y ajustar lo que necesite."
            )

        # No cerramos el browser — dejamos Canva abierto
        if player:
            player.write_log("[Canva] Presentacion completada.")

        return f"Presentacion sobre '{tema}' creada exitosamente en Canva con {len(diapos)} diapositivas."

    except ImportError:
        return (
            "Jefe, necesito Playwright. Ejecute: "
            "pip install playwright && python -m playwright install chromium"
        )
    except Exception as e:
        print("[Canva] Error general: " + str(e))
        import traceback
        traceback.print_exc()
        # Abrir Canva manualmente como fallback
        try:
            subprocess.Popen([
                "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
                "--profile-directory=Profile 10",
                "https://www.canva.com/create/presentations/"
            ])
        except Exception:
            pass
        return (
            f"Jefe, tuve un problema controlando Canva: {str(e)[:100]}. "
            f"Abri Canva en Chrome para que continue manualmente."
        )
