# study_mode.py - Modo estudio para JARVIS Mark XXXIX
# Archivo: C:\Users\jose1\Mark-XXXIX\actions\study_mode.py

import json
import time
import threading
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Estado global del estudio
_estado = {
    "activo": False,
    "tema": "",
    "preguntas": [],
    "indice": 0,
    "correctas": 0,
    "incorrectas": 0,
    "modo": "preguntas",  # preguntas | flashcards | examen
    "respuesta_esperada": "",
}


def _generar_preguntas(contenido: str, modo: str) -> list:
    """Usa Gemini para generar preguntas del contenido."""
    import sys
    sys.path.insert(0, str(BASE_DIR / "actions"))
    from gemini_helper import ask_gemini_json

    if modo == "flashcards":
        prompt = f"""Eres un tutor experto. Analiza este contenido y crea 10 flashcards.

CONTENIDO:
{contenido[:3000]}

Responde SOLO JSON:
{{
  "tema": "Nombre del tema",
  "items": [
    {{
      "frente": "Concepto o pregunta corta",
      "reverso": "Definicion o respuesta corta"
    }}
  ]
}}"""
    elif modo == "examen":
        prompt = f"""Eres un tutor experto. Crea un examen de 10 preguntas sobre este contenido.

CONTENIDO:
{contenido[:3000]}

Responde SOLO JSON:
{{
  "tema": "Nombre del tema",
  "items": [
    {{
      "pregunta": "Pregunta clara y especifica",
      "respuesta": "Respuesta correcta",
      "pistas": "Una pista si el estudiante falla"
    }}
  ]
}}"""
    else:  # preguntas progresivas
        prompt = f"""Eres un tutor experto. Crea 10 preguntas progresivas (facil a dificil) sobre este contenido.

CONTENIDO:
{contenido[:3000]}

Responde SOLO JSON:
{{
  "tema": "Nombre del tema",
  "items": [
    {{
      "pregunta": "Pregunta clara",
      "respuesta": "Respuesta esperada",
      "nivel": "facil|medio|dificil",
      "explicacion": "Explicacion si falla"
    }}
  ]
}}"""

    return ask_gemini_json(prompt)


def _leer_archivo(ruta: str) -> str:
    """Lee el contenido de un archivo (PDF, Word, TXT)."""
    path = Path(ruta)
    ext  = path.suffix.lower()

    try:
        if ext == ".txt" or ext == ".md":
            return path.read_text(encoding="utf-8")

        elif ext == ".pdf":
            try:
                import fitz  # PyMuPDF
                doc  = fitz.open(str(path))
                text = ""
                for page in doc:
                    text += page.get_text()
                return text
            except ImportError:
                # Fallback sin PyMuPDF
                return f"[PDF: {path.name}] No se pudo leer el contenido. Instala: pip install pymupdf"

        elif ext in (".docx", ".doc"):
            from docx import Document
            doc  = Document(str(path))
            text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
            return text

        else:
            return path.read_text(encoding="utf-8", errors="ignore")

    except Exception as e:
        return f"Error leyendo archivo: {e}"


def study_mode(parameters, player=None, speak=None):
    """
    Modo estudio de JARVIS.

    Acciones:
        iniciar   - Inicia sesion de estudio con archivo
        responder - El usuario responde una pregunta
        siguiente - Pasa a la siguiente pregunta
        resultado - Muestra calificacion final
        salir     - Termina el modo estudio
    """
    global _estado

    accion   = parameters.get("accion", "iniciar").lower()
    archivo  = parameters.get("archivo", "").strip()
    respuesta= parameters.get("respuesta", "").strip()
    modo     = parameters.get("modo", "preguntas").lower()  # preguntas | flashcards | examen

    # ── SALIR ────────────────────────────────────────────────────────────────
    if accion == "salir":
        _estado["activo"] = False
        if speak:
            speak("Modo estudio terminado. ¡Buen trabajo!")
        return "Modo estudio finalizado."

    # ── RESULTADO ─────────────────────────────────────────────────────────────
    if accion == "resultado":
        total     = _estado["correctas"] + _estado["incorrectas"]
        correctas = _estado["correctas"]
        pct       = int((correctas / total * 100)) if total > 0 else 0
        if pct >= 90:   calif = "A — ¡Excelente! Dominas el tema."
        elif pct >= 70: calif = "B — Bien. Repasa los puntos fallados."
        elif pct >= 50: calif = "C — Regular. Necesitas repasar más."
        else:           calif = "F — Repasa el material completo."

        msg = (f"Resultado final: {correctas}/{total} correctas ({pct}%). "
               f"Calificación: {calif}")
        if speak:
            speak(msg)
        _estado["activo"] = False
        return msg

    # ── INICIAR ───────────────────────────────────────────────────────────────
    if accion == "iniciar":
        if not archivo:
            # Buscar archivo más reciente
            from pathlib import Path as P
            desktop = P("C:\\Users\\jose1\\Desktop")
            docs    = P("C:\\Users\\jose1\\Documents")
            archivos= []
            for lugar in [desktop, docs]:
                if lugar.exists():
                    for ext in [".pdf",".docx",".txt",".md"]:
                        archivos.extend(lugar.glob(f"*{ext}"))
            if archivos:
                archivo = str(max(archivos, key=lambda f: f.stat().st_mtime))
            else:
                return "No encontré ningún archivo. Dime cuál quieres estudiar."

        if speak:
            speak(f"Leyendo el archivo. Dame un momento para preparar las preguntas.")
        if player:
            player.write_log(f"[Estudio] Leyendo: {Path(archivo).name}")

        contenido = _leer_archivo(archivo)
        if not contenido or len(contenido) < 50:
            return f"No pude leer el contenido de {Path(archivo).name}."

        if speak:
            speak("Analizando el contenido y generando preguntas...")

        data = _generar_preguntas(contenido, modo)
        if not data or not data.get("items"):
            return "No pude generar preguntas del contenido. Intenta con otro archivo."

        _estado.update({
            "activo":    True,
            "tema":      data.get("tema", Path(archivo).stem),
            "preguntas": data["items"],
            "indice":    0,
            "correctas": 0,
            "incorrectas": 0,
            "modo":      modo,
        })

        total = len(data["items"])
        tema  = _estado["tema"]

        if player:
            player.write_log(f"[Estudio] {total} preguntas sobre: {tema}")

        # Primera pregunta
        return _hacer_pregunta(speak, player)

    # ── RESPONDER ─────────────────────────────────────────────────────────────
    if accion == "responder":
        if not _estado["activo"] or not _estado["preguntas"]:
            return "No hay sesión de estudio activa. Di 'Jarvis, modo estudio' para comenzar."

        idx    = _estado["indice"]
        item   = _estado["preguntas"][idx]
        modo_a = _estado["modo"]

        if modo_a == "flashcards":
            # En flashcards solo mostrar el reverso
            reverso = item.get("reverso", "")
            if speak:
                speak(f"La respuesta es: {reverso}")
            _estado["indice"] += 1
            if _estado["indice"] >= len(_estado["preguntas"]):
                return _terminar(speak)
            return _hacer_pregunta(speak, player)

        # Evaluar respuesta con IA
        import sys
        sys.path.insert(0, str(BASE_DIR / "actions"))
        from gemini_helper import ask_gemini

        respuesta_correcta = item.get("respuesta", item.get("reverso", ""))
        prompt = (
            f"Evalua si esta respuesta del estudiante es correcta.\n"
            f"Pregunta: {item.get('pregunta', item.get('frente',''))}\n"
            f"Respuesta correcta: {respuesta_correcta}\n"
            f"Respuesta del estudiante: {respuesta}\n\n"
            f"Responde SOLO: CORRECTO o INCORRECTO, luego una coma, "
            f"luego feedback breve de maximo 20 palabras."
        )

        evaluacion = ask_gemini(prompt) or "INCORRECTO, No pude evaluar."
        es_correcto = evaluacion.upper().startswith("CORRECTO")
        feedback    = evaluacion.split(",", 1)[1].strip() if "," in evaluacion else ""

        if es_correcto:
            _estado["correctas"] += 1
            prefijo = "¡Correcto! "
        else:
            _estado["incorrectas"] += 1
            prefijo = f"Incorrecto. La respuesta era: {respuesta_correcta}. "

        msg = prefijo + feedback

        _estado["indice"] += 1
        if _estado["indice"] >= len(_estado["preguntas"]):
            if speak:
                speak(msg + " Esa fue la última pregunta.")
            return _terminar(speak) + " | " + msg

        if speak:
            speak(msg)

        time.sleep(1.5)
        return _hacer_pregunta(speak, player)

    return "Accion no reconocida. Di 'iniciar', 'responder', 'siguiente', 'resultado' o 'salir'."


def _hacer_pregunta(speak, player):
    """Formula la pregunta actual."""
    idx   = _estado["indice"]
    items = _estado["preguntas"]
    modo  = _estado["modo"]
    total = len(items)
    item  = items[idx]

    num = idx + 1
    if modo == "flashcards":
        pregunta = f"Flashcard {num} de {total}: {item.get('frente','')}"
        hint     = "Di 'siguiente' para ver la respuesta."
    elif modo == "examen":
        pregunta = f"Pregunta {num} de {total}: {item.get('pregunta','')}"
        hint     = ""
    else:
        nivel    = item.get("nivel","")
        nivel_str= f"[{nivel.upper()}] " if nivel else ""
        pregunta = f"Pregunta {num} de {total} {nivel_str}: {item.get('pregunta','')}"
        hint     = ""

    if player:
        player.write_log(f"[Estudio] P{num}: {pregunta[:80]}")

    if speak:
        speak(pregunta)

    return pregunta


def _terminar(speak):
    """Calcula y anuncia resultado final."""
    total     = _estado["correctas"] + _estado["incorrectas"]
    correctas = _estado["correctas"]
    pct       = int((correctas / total * 100)) if total > 0 else 0

    if pct >= 90:   calif = "¡Excelente! Dominas el tema perfectamente."
    elif pct >= 70: calif = "Bien hecho. Repasa los puntos que fallaste."
    elif pct >= 50: calif = "Regular. Te recomiendo repasar el material."
    else:           calif = "Necesitas repasar más. ¡Tú puedes!"

    msg = (f"Sesión terminada. {correctas} de {total} correctas, "
           f"{pct}% de aciertos. {calif}")

    if speak:
        speak(msg)

    _estado["activo"] = False
    return msg
