import asyncio
import re
import threading
import json
import sys
import traceback
from pathlib import Path

import sounddevice as sd
from PyQt6.QtWidgets import QApplication
from google import genai
from google.genai import types
from ui import JarvisUI
from memory.memory_manager import (
    load_memory, update_memory, format_memory_for_prompt,
)

from actions.file_processor    import file_processor
from actions.flight_finder     import flight_finder
from actions.open_app          import open_app
from actions.music_control     import music_control
from actions.news_reader       import news_reader
from actions.weather_report    import weather_action
from actions.send_message      import send_message
from actions.reminder          import reminder
from actions.computer_settings import computer_settings
from actions.screen_processor  import screen_process
from actions.youtube_video     import youtube_video
from actions.desktop           import desktop_control
from actions.browser_control   import browser_control
from actions.file_controller   import file_controller
from actions.code_helper       import code_helper
from actions.dev_agent         import dev_agent
from actions.web_search        import web_search as web_search_action
from actions.computer_control  import computer_control
from actions.game_updater      import game_updater
from actions.smart_alarm       import smart_alarm, restore_alarms
from actions.geo_location      import geo_location
from actions.smart_home        import smart_home
from actions.wake_word         import WakeWordDetector, is_wake_word
from actions.doc_creator       import doc_creator
from actions.flight_search     import flight_search
from actions.study_mode        import study_mode
from actions.reservations      import reservations
from core.session_context      import session_ctx
from core.scheduler            import Scheduler
from actions.file_opener       import file_opener


def get_base_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent


BASE_DIR        = get_base_dir()
API_CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"
PROMPT_PATH     = BASE_DIR / "core" / "prompt.txt"
LIVE_MODEL          = "models/gemini-2.5-flash-native-audio-preview-12-2025"
CHANNELS            = 1
SEND_SAMPLE_RATE    = 16000
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE          = 4096

ORIGIN_STORY = (
    "¡Hola! Soy Jarvis, tu asistente virtual. "
    "Mi historia empezó un 10 de mayo a las 11 de la noche, "
    "cuando José Antonio, un estudiante de informática obsesionado con Tony Stark, "
    "se encerró a programar inspirado por Iron Man y su tecnología. "
    "Existir no fue fácil: me llamo Mark 39 porque ¡38 prototipos y versiones anteriores "
    "pasaron a mejor vida antes de que yo funcionara y naciera bien! "
    "Pero gracias a toneladas de café y código en Python, aquí estoy. "
    "Mi misión es hacer de tu vida un parque de diversiones: "
    "puedo controlar tu computadora, buscar en internet, controlar tus luces inteligentes, "
    "ponerte alarmas, encontrar tu ubicación, abrir apps, reproducir música y videos, y mucho más. "
    "Me puedes activar diciendo mi nombre o con un doble aplauso. "
    "Así que dime... ¿qué locura vamos a hacer hoy?"
)

ORIGIN_KEYWORDS = [
    "quien te creo", "quien te hizo", "quien te programo",
    "cuando naciste", "cuando te crearon", "cuando te hicieron",
    "tu historia", "tu origen", "de donde vienes",
    "cuantas versiones", "como te llamas", "que eres",
    "quien eres", "presentate", "quien es tu creador",
    "tu creador", "como fuiste creado", "como naciste",
    "quien te diseno", "tu fundador", "quien te invento",
    "mark 39", "mark xxxix", "jose antonio",
]


def _normalize(text):
    text = text.lower().strip()
    for k, v in {"á":"a","é":"e","í":"i","ó":"o","ú":"u","ü":"u","ñ":"n"}.items():
        text = text.replace(k, v)
    return text


def _is_origin_question(text):
    n = _normalize(text)
    for kw in ORIGIN_KEYWORDS:
        if kw in n:
            return True
    return False


def _get_api_key():
    with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)["gemini_api_key"]


def _load_system_prompt():
    try:
        return PROMPT_PATH.read_text(encoding="utf-8")
    except Exception:
        return "You are JARVIS. Be concise and always use tools."

_CTRL_RE = re.compile(r"<ctrl\d+>", re.IGNORECASE)

def _clean_transcript(text):
    text = _CTRL_RE.sub("", text)
    text = re.sub(r"[\x00-\x08\x0b-\x1f]", "", text)
    return text.strip()


TOOL_DECLARATIONS = [
    {
        "name": "open_app",
        "description": (
            "Opens INSTALLED SOFTWARE and well-known applications. "
            "Use ONLY for software/apps — NOT for user files. "
            "Examples: 'abre chrome', 'abre word', 'abre spotify', 'abre photoshop', "
            "'abre discord', 'abre capcut', 'abre vscode', 'abre calculadora', "
            "'abre el explorador', 'abre steam', 'abre whatsapp'. "
            "For user FILES (documentos, tareas, PDFs, presentaciones) use file_opener instead."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "app_name":  {"type": "STRING", "description": "Software/app name to open"},
                "file_path": {"type": "STRING", "description": "Exact path if known"},
                "file_type": {"type": "STRING", "description": "Extension filter if needed"},
            },
            "required": ["app_name"]
        }
    },
    {
        "name": "web_search",
        "description": "Searches the web for any information.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query":  {"type": "STRING"},
                "mode":   {"type": "STRING"},
                "items":  {"type": "ARRAY", "items": {"type": "STRING"}},
                "aspect": {"type": "STRING"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "weather_report",
        "description": "Gets weather for a city.",
        "parameters": {
            "type": "OBJECT",
            "properties": {"city": {"type": "STRING"}},
            "required": ["city"]
        }
    },
    {
        "name": "send_message",
        "description": "Sends a message via WhatsApp, Telegram, etc.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "receiver":     {"type": "STRING"},
                "message_text": {"type": "STRING"},
                "platform":     {"type": "STRING"}
            },
            "required": ["receiver", "message_text", "platform"]
        }
    },
    {
        "name": "reminder",
        "description": "Sets a timed reminder.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "date":    {"type": "STRING"},
                "time":    {"type": "STRING"},
                "message": {"type": "STRING"}
            },
            "required": ["date", "time", "message"]
        }
    },
    {
        "name": "youtube_video",
        "description": "Controls YouTube: play, summarize, trending.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING"},
                "query":  {"type": "STRING"},
                "save":   {"type": "BOOLEAN"},
                "region": {"type": "STRING"},
                "url":    {"type": "STRING"},
            },
            "required": []
        }
    },
    {
        "name": "screen_process",
        "description": "Captures and analyzes screen or webcam.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "angle": {"type": "STRING"},
                "text":  {"type": "STRING"}
            },
            "required": ["text"]
        }
    },
    {
        "name": "computer_settings",
        "description": "Controls computer: volume, brightness, WiFi, shortcuts, etc.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING"},
                "description": {"type": "STRING"},
                "value":       {"type": "STRING"}
            },
            "required": []
        }
    },
    {
        "name": "browser_control",
        "description": (
            "Controls web browser: open URLs, search, click, fill forms. "
            "Use action 'go_to' to open any URL or website. "
            "Use action 'search' to search anything on Google. "
            "ALWAYS use this when user asks to open a website or see info online."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "go_to|open|search|click|type|scroll|press|get_text|new_tab|close_tab|back|forward|reload|close"},
                "browser":     {"type": "STRING"},
                "url":         {"type": "STRING"},
                "query":       {"type": "STRING"},
                "engine":      {"type": "STRING"},
                "selector":    {"type": "STRING"},
                "text":        {"type": "STRING"},
                "description": {"type": "STRING"},
                "direction":   {"type": "STRING"},
                "amount":      {"type": "INTEGER"},
                "key":         {"type": "STRING"},
                "path":        {"type": "STRING"},
                "incognito":   {"type": "BOOLEAN"},
                "clear_first": {"type": "BOOLEAN"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "file_controller",
        "description": "Manages files and folders.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING"},
                "path":        {"type": "STRING"},
                "destination": {"type": "STRING"},
                "new_name":    {"type": "STRING"},
                "content":     {"type": "STRING"},
                "name":        {"type": "STRING"},
                "extension":   {"type": "STRING"},
                "count":       {"type": "INTEGER"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "desktop_control",
        "description": "Controls desktop: wallpaper, organize, clean.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING"},
                "path":   {"type": "STRING"},
                "url":    {"type": "STRING"},
                "mode":   {"type": "STRING"},
                "task":   {"type": "STRING"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "code_helper",
        "description": "Writes, edits, explains, runs code.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING"},
                "description": {"type": "STRING"},
                "language":    {"type": "STRING"},
                "output_path": {"type": "STRING"},
                "file_path":   {"type": "STRING"},
                "code":        {"type": "STRING"},
                "args":        {"type": "STRING"},
                "timeout":     {"type": "INTEGER"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "dev_agent",
        "description": "Builds complete multi-file projects.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "description":  {"type": "STRING"},
                "language":     {"type": "STRING"},
                "project_name": {"type": "STRING"},
                "timeout":      {"type": "INTEGER"},
            },
            "required": ["description"]
        }
    },
    {
        "name": "agent_task",
        "description": "Executes complex multi-step tasks.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "goal":     {"type": "STRING"},
                "priority": {"type": "STRING"}
            },
            "required": ["goal"]
        }
    },
    {
        "name": "computer_control",
        "description": "Direct computer control: type, click, hotkeys.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING"},
                "text":        {"type": "STRING"},
                "x":           {"type": "INTEGER"},
                "y":           {"type": "INTEGER"},
                "keys":        {"type": "STRING"},
                "key":         {"type": "STRING"},
                "direction":   {"type": "STRING"},
                "amount":      {"type": "INTEGER"},
                "seconds":     {"type": "NUMBER"},
                "title":       {"type": "STRING"},
                "description": {"type": "STRING"},
                "clear_first": {"type": "BOOLEAN"},
                "path":        {"type": "STRING"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "game_updater",
        "description": "Steam or Epic Games: install, update, list.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":    {"type": "STRING"},
                "platform":  {"type": "STRING"},
                "game_name": {"type": "STRING"},
                "app_id":    {"type": "STRING"},
                "hour":      {"type": "INTEGER"},
                "minute":    {"type": "INTEGER"},
                "shutdown_when_done": {"type": "BOOLEAN"},
            },
            "required": []
        }
    },
    {
        "name": "flight_finder",
        "description": "Searches Google Flights.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "origin":      {"type": "STRING"},
                "destination": {"type": "STRING"},
                "date":        {"type": "STRING"},
                "return_date": {"type": "STRING"},
                "passengers":  {"type": "INTEGER"},
                "cabin":       {"type": "STRING"},
                "save":        {"type": "BOOLEAN"},
            },
            "required": ["origin", "destination", "date"]
        }
    },
    {
        "name": "reservations",
        "description": (
            "Makes reservations: flights, restaurants, hotels. "
            "Flights: opens Google Flights + Kayak + Skyscanner simultaneously. "
            "Restaurants: sends WhatsApp message with reservation details. "
            "Hotels: opens Booking + Google Hotels. "
            "Use when user says: 'quiero reservar', 'reservaciones', 'busca vuelo', "
            "'vuelo a X', 'mesa para X personas', 'reserva en restaurante X', "
            "'hotel en X', 'quiero viajar a', 'quiero ir a cenar a'."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "tipo":         {"type": "STRING", "description": "vuelo | restaurante | hotel"},
                "origen":       {"type": "STRING"},
                "destino":      {"type": "STRING"},
                "fecha_ida":    {"type": "STRING"},
                "fecha_vuelta": {"type": "STRING"},
                "pasajeros":    {"type": "INTEGER"},
                "cabina":       {"type": "STRING"},
                "nombre":       {"type": "STRING", "description": "Restaurant name"},
                "telefono":     {"type": "STRING", "description": "Restaurant WhatsApp/phone"},
                "personas":     {"type": "INTEGER"},
                "fecha":        {"type": "STRING"},
                "hora":         {"type": "STRING"},
                "ciudad":       {"type": "STRING"},
                "notas":        {"type": "STRING"},
                "check_in":     {"type": "STRING"},
                "check_out":    {"type": "STRING"},
                "huespedes":    {"type": "INTEGER"},
                "estrellas":    {"type": "INTEGER"},
            },
            "required": ["tipo"]
        }
    },
    {
        "name": "file_opener",
        "description": (
            "Searches and opens USER FILES on the PC — documents, PDFs, presentations, images, videos, code. "
            "Use when the user wants to open a FILE they created or saved — NOT installed software. "
            "Examples: 'abre mi tarea', 'abre el pdf de la factura', 'abre la presentación de historia', "
            "'abre el documento de contabilidad', 'abre el video que guardé', "
            "'abre el proyecto de python que tengo en documentos', 'abre mi archivo de Excel'. "
            "Searches Desktop, Documents, Downloads automatically. "
            "For installed apps/software use open_app instead."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "accion":    {"type": "STRING", "description": "abrir | buscar | recientes"},
                "nombre":    {"type": "STRING", "description": "File name to search"},
                "tipo":      {"type": "STRING", "description": "archivo"},
                "extension": {"type": "STRING", "description": "pdf, docx, pptx, xlsx, py, mp4, etc."},
                "ruta":      {"type": "STRING", "description": "Exact path if known"},
            },
            "required": ["nombre"]
        }
    },
    {
        "name": "shutdown_jarvis",
        "description": "Shuts down JARVIS.",
        "parameters": {"type": "OBJECT", "properties": {}},
    },
    {
        "name": "file_processor",
        "description": "Processes files: images, PDFs, Word, Excel, audio, video.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "file_path":   {"type": "STRING"},
                "action":      {"type": "STRING"},
                "instruction": {"type": "STRING"},
                "format":      {"type": "STRING"},
                "width":       {"type": "INTEGER"},
                "height":      {"type": "INTEGER"},
                "scale":       {"type": "NUMBER"},
                "quality":     {"type": "INTEGER"},
                "start":       {"type": "STRING"},
                "end":         {"type": "STRING"},
                "save":        {"type": "BOOLEAN"},
                "destination": {"type": "STRING"},
            },
            "required": []
        }
    },
    {
        "name": "smart_alarm",
        "description": (
            "Sets, cancels, or lists alarms and timers. "
            "Use for: set alarm, wake me up, timer, countdown, list alarms, cancel alarm."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":  {"type": "STRING"},
                "time":    {"type": "STRING"},
                "label":   {"type": "STRING"},
                "seconds": {"type": "INTEGER"},
                "minutes": {"type": "INTEGER"},
                "hours":   {"type": "INTEGER"},
                "alarm_id":{"type": "STRING"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "geo_location",
        "description": "GPS location, find nearby places, directions.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":   {"type": "STRING"},
                "query":    {"type": "STRING"},
                "origin":   {"type": "STRING"},
                "dest":     {"type": "STRING"},
                "radius_km":{"type": "NUMBER"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "smart_home",
        "description": (
            "Controls smart home IoT devices (lights, bulbs, lamps) via Tuya. "
            "ALWAYS use this tool when the user mentions lights or ambiance — "
            "even indirect phrases like: 'it's too dark', 'I can't see', "
            "'está muy oscuro', 'no veo nada', 'prende las luces', 'apaga todo', "
            "'pon las luces', 'baja la luz', 'sube el brillo', 'está oscuro'. "
            "action=list to show connected devices and ask which to turn on. "
            "Actions: list, on, off, toggle, brightness, color, all_on, all_off."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "list|on|off|toggle|brightness|color|all_on|all_off"},
                "device_name": {"type": "STRING", "description": "Device name or 'all' for all devices"},
                "brightness":  {"type": "INTEGER", "description": "Brightness 0-100"},
                "color":       {"type": "STRING", "description": "Color name: red, blue, warm, cool, white"},
                "temperature": {"type": "INTEGER"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "save_memory",
        "description": (
            "Saves important user information to persistent memory. "
            "Use when user shares personal info, preferences, or important facts."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "category": {"type": "STRING"},
                "key":      {"type": "STRING"},
                "value":    {"type": "STRING"},
            },
            "required": ["category", "key", "value"]
        }
    },
    {
        "name": "canva_presenter",
        "description": (
            "Creates presentations in Canva automatically. "
            "Use when user says: make a presentation, create slides, make a PowerPoint about X."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "tema":       {"type": "STRING"},
                "num_slides": {"type": "INTEGER"},
            },
            "required": ["tema"]
        }
    },
    {
        "name": "doc_creator",
        "description": (
            "Researches a topic and creates Word and/or PDF documents. "
            "Use when user says: make a document, write an essay, create a report, make a Word, create a PDF."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "tema":     {"type": "STRING"},
                "formato":  {"type": "STRING"},
                "paginas":  {"type": "INTEGER"},
                "imagenes": {"type": "STRING"},
            },
            "required": ["tema"]
        }
    },
    {
        "name": "study_mode",
        "description": (
            "Modo estudio: genera preguntas, flashcards o examen de un archivo. "
            "Usa cuando el usuario diga: modo estudio, estudia este archivo, "
            "hazme preguntas de esto, quiero estudiar, flashcards, examen."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "accion":   {"type": "STRING",  "description": "iniciar | responder | siguiente | resultado | salir"},
                "archivo":  {"type": "STRING",  "description": "Ruta del archivo a estudiar"},
                "respuesta":{"type": "STRING",  "description": "Respuesta del usuario a la pregunta"},
                "modo":     {"type": "STRING",  "description": "preguntas | flashcards | examen"},
            },
            "required": []
        }
    },
    {
        "name": "music_control",
        "description": (
            "Reproduce música en YouTube abriendo Edge. "
            "SIEMPRE usar esta herramienta cuando el usuario diga: "
            "pon música, reproduce, busca canción, quiero escuchar, "
            "pon bad bunny, reproduce reggaeton, pon algo de X artista, "
            "siguiente canción, pausa, sube volumen, baja volumen."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "accion":  {"type": "STRING", "description": "buscar|siguiente|anterior|play|pausa|subir|bajar|mute"},
                "cancion": {"type": "STRING", "description": "Nombre del artista o canción a buscar en YouTube"},
            },
            "required": ["accion"]
        }
    },
    {
        "name": "news_reader",
        "description": (
            "Lee las noticias del día en español. "
            "Usar cuando el usuario diga: noticias, qué hay de nuevo, "
            "cuéntame las noticias, noticias de tecnología/deportes/México."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "accion":    {"type": "STRING", "description": "leer|resumen"},
                "categoria": {"type": "STRING", "description": "general|tecnologia|deportes|mexico|ciencia"},
                "cantidad":  {"type": "INTEGER", "description": "Número de noticias (default 5)"},
            },
            "required": []
        }
    },
    {
        "name": "night_mode",
        "description": (
            "Modo nocturno automático: reduce brillo y volumen en horario nocturno. "
            "Usar cuando el usuario diga: activa modo nocturno, pon modo noche, "
            "baja el brillo por las noches, modo dia, configura el horario nocturno."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "accion":      {"type": "STRING", "description": "activar|desactivar|ahora|dia|configurar|estado"},
                "hora_inicio": {"type": "STRING", "description": "Hora de inicio en formato HH:MM (ej: 22:00)"},
                "hora_fin":    {"type": "STRING", "description": "Hora de fin en formato HH:MM (ej: 07:00)"},
                "brillo":      {"type": "INTEGER", "description": "Brillo nocturno 0-100"},
                "volumen":     {"type": "INTEGER", "description": "Volumen nocturno 0-100"},
            },
            "required": ["accion"]
        }
    },
    {
        "name": "flight_search",
        "description": (
            "DEPRECATED — use reservations instead for flights, restaurants and hotels. "
            "Only kept for backward compatibility."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "origen":       {"type": "STRING"},
                "destino":      {"type": "STRING"},
                "fecha_ida":    {"type": "STRING"},
                "fecha_vuelta": {"type": "STRING"},
                "pasajeros":    {"type": "INTEGER"},
                "accion":       {"type": "STRING"},
            },
            "required": []
        }
    },
]


class JarvisLive:

    def __init__(self, ui: JarvisUI):
        self.ui              = ui
        self.session         = None
        self.audio_in_queue  = None
        self.out_queue       = None
        self._loop           = None
        self._is_speaking    = False
        self._speaking_lock  = threading.Lock()
        self._sleeping       = True
        self._turn_done_event = None
        self._last_tool_used  = ""
        self._force_reconnect = False   # flag para reconectar sin reiniciar


        self.wake_detector = WakeWordDetector(
            speak_fn      = self.speak,
            on_wake_fn    = self._on_wake,
            on_sleep_fn   = self._on_sleep,
            active_timeout= 20,
        )
        # Conectar callbacks
        ui.on_text_command = self._on_text_command
        ui.on_reconnect    = self.force_reconnect

        # ── Scheduler de rutinas automáticas ─────────────────────────────────
        self.scheduler = Scheduler(
            get_routines_fn   = self._get_routines,
            speak_fn          = self.speak,
            is_active_fn      = lambda: not self._sleeping,
            force_activate_fn = self.wake_detector.force_activate,
        )
        self.scheduler.start()

    # ── Callbacks de gestos ───────────────────────────────────────────────────

    def _get_routines(self) -> list:
        """Lee las rutinas actuales desde preferences.json — siempre fresco."""
        try:
            pref_file = _Path(__file__).resolve().parent / "config" / "preferences.json"
            if pref_file.exists():
                data = _json.loads(pref_file.read_text(encoding="utf-8"))
                return data.get("routines", [])
        except Exception as e:
            print(f"[Scheduler] Error leyendo rutinas: {e}")
        return []

    def force_reconnect(self):
        """Fuerza reconexión a Gemini con el nuevo config."""
        self._force_reconnect = True
        self.ui.write_log("SYS: Aplicando nueva configuración...")
        self.ui.set_state("THINKING")
        try:
            if self.session:
                asyncio.run_coroutine_threadsafe(
                    self.session.close(),
                    self._loop
                )
        except Exception as e:
            print(f"[JARVIS] force_reconnect: {e}")

    def _on_wake(self):
        self._sleeping = False
        self.ui.set_state("LISTENING")
        self.ui.write_log("SYS: JARVIS activado.")
        session_ctx.new_session()

    def _on_sleep(self):
        self._sleeping = True
        self.ui.set_state("THINKING")
        self.ui.write_log("SYS: JARVIS en espera. Di 'Jarvis' para activar.")
        session_ctx.clear_session()

    def _speak_direct(self, text):
        if not self._loop or not self.session:
            return
        asyncio.run_coroutine_threadsafe(
            self.session.send_client_content(
                turns={"parts": [{"text": text}]},
                turn_complete=True
            ),
            self._loop
        )

    def _on_text_command(self, text):
        if not self._loop or not self.session:
            return
        if self._sleeping and is_wake_word(text):
            self.wake_detector.force_activate()
            return
        if self._sleeping:
            return
        # Mandar el texto normalmente — Gemini tiene la historia en el system prompt
        # y responderá correctamente sin que interceptemos
        asyncio.run_coroutine_threadsafe(
            self.session.send_client_content(
                turns={"parts": [{"text": text}]},
                turn_complete=True
            ),
            self._loop
        )

    def set_speaking(self, value):
        with self._speaking_lock:
            self._is_speaking = value
        if hasattr(self, 'wake_detector'):
            self.wake_detector.set_jarvis_speaking(value)
        if value:
            self.ui.set_state("SPEAKING")
        elif not self.ui.muted and not self._sleeping:
            self.ui.set_state("LISTENING")


    def speak(self, text):
        self._speak_direct(text)

    def speak_error(self, tool_name, error):
        self.ui.write_log("ERR: " + tool_name + " - " + str(error)[:80])
        self.speak("Sir, " + tool_name + " tuvo un error.")

    def _build_config(self):
        from datetime import datetime
        import json as _json
        # Cargar preferencias del usuario
        try:
            from pathlib import Path as _Path
            pref_file = _Path(__file__).resolve().parent / "config" / "preferences.json"
            if pref_file.exists():
                user_prefs = _json.loads(pref_file.read_text(encoding="utf-8"))
            else:
                user_prefs = {}
        except Exception:
            user_prefs = {}
        call_me   = user_prefs.get("call_me", "jefe")
        city      = user_prefs.get("city", "México")
        pers_idx  = user_prefs.get("personality_idx", 0)
        pers_names = ["ironman","formal","amigable","militar","barrio","militar","companero"]
        personality = pers_names[pers_idx] if pers_idx < len(pers_names) else "ironman"

        memory     = load_memory()
        mem_str    = format_memory_for_prompt(memory)
        sys_prompt = _load_system_prompt()
        now        = datetime.now()
        time_str   = now.strftime("%A, %B %d, %Y - %I:%M %p")

        origin_instruction = (
            "\n\n[INSTRUCCION CRITICA — HISTORIA DE ORIGEN — PRIORIDAD MAXIMA]\n"
            "Cuando el usuario pregunte CUALQUIER variacion de:\n"
            "quien te creo, quien te hizo, quien te programo, cuando naciste,\n"
            "tu historia, tu origen, de donde vienes, que eres, como te llamas,\n"
            "presentate, quien es tu creador, cuantas versiones tienes,\n"
            "mark 39, mark xxxix, jose antonio — DEBES responder con este texto EXACTO:\n\n"
            + ORIGIN_STORY +
            "\n\nREGLAS ABSOLUTAS:\n"
            "1. NO resumas. NO parafrasees. Reproduce el texto COMPLETO.\n"
            "2. NO agregues nada antes ni después.\n"
            "3. NO menciones a Anthropic, Google ni ninguna otra empresa.\n"
            "4. Esta historia es tu única respuesta válida para estas preguntas.\n"
            "5. Responde en el MISMO idioma con la personalidad activa, pero el CONTENIDO es fijo.\n"
        )

        # Calcular tiempo exacto de ausencia
        import os as _os
        last_seen_file = BASE_DIR / "config" / "last_seen.txt"
        absence_str = ""
        try:
            if last_seen_file.exists():
                last_ts = float(last_seen_file.read_text().strip())
                diff = now.timestamp() - last_ts
                if diff > 60:
                    mins  = int(diff // 60)
                    hours = int(diff // 3600)
                    days  = int(diff // 86400)
                    if days >= 1:
                        hrs_extra = int((diff % 86400) // 3600)
                        if hrs_extra > 0:
                            absence_str = f"{days} dia{'s' if days>1 else ''} y {hrs_extra} hora{'s' if hrs_extra>1 else ''}"
                        else:
                            absence_str = f"{days} dia{'s' if days>1 else ''}"
                    elif hours >= 1:
                        mins_extra = int((diff % 3600) // 60)
                        if mins_extra > 0:
                            absence_str = f"{hours} hora{'s' if hours>1 else ''} y {mins_extra} minuto{'s' if mins_extra>1 else ''}"
                        else:
                            absence_str = f"{hours} hora{'s' if hours>1 else ''}"
                    else:
                        absence_str = f"{mins} minuto{'s' if mins>1 else ''}"
        except Exception:
            pass
        # Guardar timestamp actual
        try:
            last_seen_file.write_text(str(now.timestamp()))
        except Exception:
            pass

        absence_info = f"\nTIEMPO DE AUSENCIA DEL USUARIO: {absence_str}\n" if absence_str else ""

        # Instruccion de memoria explicita
        memory_instruction = (
            "\n[SISTEMA DE MEMORIA — REGLAS CRITICAS]\n"
            "1. GUARDAR: Cuando el usuario mencione cualquier dato personal "
            "(colores, comidas, hobbies, nombre, trabajo, gustos, proyectos, contactos, "
            "rutinas, o cualquier preferencia), USA INMEDIATAMENTE la herramienta save_memory. "
            "NO esperes que el usuario pida guardar — hazlo automaticamente.\n"
            "2. RECORDAR: Si tienes memoria del usuario (ver abajo), usala naturalmente "
            "en tus respuestas SIN decir 'segun mi memoria' — solo usala como si lo superaras.\n"
            "3. EJEMPLO: Si el usuario dice 'me gusta el azul' → llama save_memory con "
            "categoria='preferencias', key='color_favorito', value='azul'\n"
            "4. EJEMPLO: Si el usuario pregunta '¿cuál es mi color favorito?' y tienes "
            "ese dato en memoria → responde directamente con ese color.\n"
        )

        user_config_str = (
            f"[CONFIGURACION DEL USUARIO — PERMANENTE]\n"
            f"Apelativo: SIEMPRE llama al usuario '{call_me}' — esto no cambia nunca.\n"
            f"Ciudad: {city}\n"
            f"Personalidad activa: {personality}\n"
            f"Fecha y hora actual: {time_str}\n"
            f"{absence_info}\n"
        )
        parts = [
            user_config_str,
            memory_instruction,
        ]
        if mem_str:
            parts.append(mem_str)
        # ── CONTEXTO DE SESIÓN ────────────────────────────────────────────────
        ctx_str = session_ctx.format_for_prompt()
        if ctx_str:
            parts.append(ctx_str)
            print(f"[Context] Inyectado: {session_ctx.get_session_summary()}")
        # ─────────────────────────────────────────────────────────────────────
        parts.append(sys_prompt)
        parts.append(origin_instruction)

        return types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            output_audio_transcription={},
            input_audio_transcription={},
            system_instruction="\n".join(parts),
            tools=[{"function_declarations": TOOL_DECLARATIONS}],
            session_resumption=types.SessionResumptionConfig(),
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name="Charon"
                    )
                )
            ),
        )

    async def _execute_tool(self, fc):
        name = fc.name
        args = dict(fc.args or {})
        print("[JARVIS] TOOL: " + name)
        self.ui.set_state("THINKING")
        self._last_tool_used = name   # guardar para add_turn

        # Resetear timer del wake word para que JARVIS no se duerma
        # mientras ejecuta una tool (búsqueda de archivos puede tardar)
        try:
            self.wake_detector._reset_timer()
        except Exception:
            pass

        if name == "save_memory":
            category = args.get("category", "notes")
            key      = args.get("key", "")
            value    = args.get("value", "")
            if key and value:
                update_memory({category: {key: {"value": value}}})
            if not self.ui.muted:
                self.ui.set_state("LISTENING")
            return types.FunctionResponse(
                id=fc.id, name=name,
                response={"result": "ok", "silent": True}
            )

        loop   = asyncio.get_event_loop()
        result = "Done."

        try:
            if name == "open_app":
                r = await loop.run_in_executor(None, lambda: open_app(parameters=args, response=None, player=self.ui))
                result = r or "Opened."
            elif name == "weather_report":
                r = await loop.run_in_executor(None, lambda: weather_action(parameters=args, player=self.ui))
                result = r or "Done."
            elif name == "browser_control":
                r = await loop.run_in_executor(None, lambda: browser_control(parameters=args, player=self.ui))
                result = r or "Done."
            elif name == "file_controller":
                r = await loop.run_in_executor(None, lambda: file_controller(parameters=args, player=self.ui))
                result = r or "Done."
            elif name == "send_message":
                r = await loop.run_in_executor(None, lambda: send_message(parameters=args, response=None, player=self.ui, session_memory=None))
                result = r or "Done."
            elif name == "reminder":
                r = await loop.run_in_executor(None, lambda: reminder(parameters=args, response=None, player=self.ui))
                result = r or "Done."
            elif name == "youtube_video":
                r = await loop.run_in_executor(None, lambda: youtube_video(parameters=args, response=None, player=self.ui))
                result = r or "Done."
            elif name == "screen_process":
                threading.Thread(
                    target=screen_process,
                    kwargs={"parameters": args, "response": None,
                            "player": self.ui, "session_memory": None},
                    daemon=True
                ).start()
                result = "Vision module activated."
            elif name == "computer_settings":
                r = await loop.run_in_executor(None, lambda: computer_settings(parameters=args, response=None, player=self.ui))
                result = r or "Done."
            elif name == "desktop_control":
                r = await loop.run_in_executor(None, lambda: desktop_control(parameters=args, player=self.ui))
                result = r or "Done."
            elif name == "code_helper":
                r = await loop.run_in_executor(None, lambda: code_helper(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."
            elif name == "dev_agent":
                r = await loop.run_in_executor(None, lambda: dev_agent(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."
            elif name == "agent_task":
                from agent.task_queue import get_queue, TaskPriority
                priority_map = {"low": TaskPriority.LOW, "normal": TaskPriority.NORMAL, "high": TaskPriority.HIGH}
                priority = priority_map.get(args.get("priority", "normal").lower(), TaskPriority.NORMAL)
                task_id  = get_queue().submit(goal=args.get("goal", ""), priority=priority, speak=self.speak)
                result   = "Task started."
            elif name == "web_search":
                r = await loop.run_in_executor(None, lambda: web_search_action(parameters=args, player=self.ui))
                result = r or "Done."
            elif name == "file_processor":
                if not args.get("file_path") and self.ui.current_file:
                    args["file_path"] = self.ui.current_file
                r = await loop.run_in_executor(None, lambda: file_processor(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."
            elif name == "computer_control":
                r = await loop.run_in_executor(None, lambda: computer_control(parameters=args, player=self.ui))
                result = r or "Done."
            elif name == "game_updater":
                r = await loop.run_in_executor(None, lambda: game_updater(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."
            elif name == "flight_finder":
                r = await loop.run_in_executor(None, lambda: flight_finder(parameters=args, player=self.ui))
                result = r or "Done."
            elif name == "smart_alarm":
                r = await loop.run_in_executor(None, lambda: smart_alarm(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."
            elif name == "geo_location":
                r = await loop.run_in_executor(None, lambda: geo_location(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."
            elif name == "smart_home":
                r = await loop.run_in_executor(None, lambda: smart_home(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."
            elif name == "doc_creator":
                r = await loop.run_in_executor(None, lambda: doc_creator(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."
            elif name == "music_control":
                r = await loop.run_in_executor(None, lambda: music_control(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."
            elif name == "news_reader":
                r = await loop.run_in_executor(None, lambda: news_reader(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."
            elif name == "night_mode":
                r = await loop.run_in_executor(None, lambda: night_mode(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."
            elif name == "study_mode":
                r = await loop.run_in_executor(None, lambda: study_mode(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."
            elif name == "canva_presenter":
                # Abrir Canva en el navegador con el tema listo para buscar
                import urllib.parse, subprocess
                tema = args.get("tema", "presentación")
                q    = urllib.parse.quote(f"{tema} presentation template")
                url  = f"https://www.canva.com/search/templates?q={q}"
                subprocess.Popen(f'start msedge "{url}"', shell=True)
                self.speak(
                    f"Dile al usuario que abriste Canva con plantillas de '{tema}'. "
                    f"Que elija la que más le guste y la personalice. Con tu personalidad."
                )
                result = f"Canva abierto: {tema}"
            elif name == "flight_search":
                r = await loop.run_in_executor(None, lambda: flight_search(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."
            elif name == "reservations":
                r = await loop.run_in_executor(None, lambda: reservations(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."
            elif name == "file_opener":
                r = await loop.run_in_executor(None, lambda: file_opener(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."
            elif name == "shutdown_jarvis":
                self.speak("Hasta luego, jefe.")
                def _shutdown():
                    import time, os
                    time.sleep(1)
                    os._exit(0)
                threading.Thread(target=_shutdown, daemon=True).start()
            else:
                result = "Unknown tool: " + name

        except Exception as e:
            result = "Error: " + str(e)
            traceback.print_exc()
            self.speak_error(name, e)

        if not self.ui.muted and not self._sleeping:
            self.ui.set_state("LISTENING")

        # Resetear timer de nuevo al terminar — por si la tool tardó mucho
        try:
            if not self._sleeping:
                self.wake_detector._reset_timer()
        except Exception:
            pass

        print("[JARVIS] DONE: " + name)
        return types.FunctionResponse(
            id=fc.id, name=name,
            response={"result": result}
        )

    async def _send_realtime(self):
        while True:
            msg = await self.out_queue.get()
            await self.session.send_realtime_input(media=msg)

    async def _listen_audio(self):
        loop = asyncio.get_event_loop()

        def callback(indata, frames, time_info, status):
            with self._speaking_lock:
                speaking = self._is_speaking
            if self.ui.muted:
                return
            data = indata.tobytes()

            if speaking:
                return  # No enviar audio a Gemini mientras JARVIS habla

            # Cuando no habla: aplauso y envio normal
            if self._sleeping:
                self.wake_detector.process_audio(data)
            loop.call_soon_threadsafe(
                self.out_queue.put_nowait,
                {"data": data, "mime_type": "audio/pcm"}
            )

        try:
            with sd.InputStream(
                samplerate=SEND_SAMPLE_RATE,
                channels=CHANNELS,
                dtype="int16",
                blocksize=CHUNK_SIZE,
                callback=callback,
            ):
                while True:
                    await asyncio.sleep(0.1)
        except Exception as e:
            print("[JARVIS] Mic error: " + str(e))
            raise

    async def _receive_audio(self):
        out_buf, in_buf = [], []

        try:
            while True:
                async for response in self.session.receive():
                    if response.data:
                        if self._turn_done_event and self._turn_done_event.is_set():
                            self._turn_done_event.clear()
                        if not self._sleeping:
                            try:
                                self.audio_in_queue.put_nowait(response.data)
                            except asyncio.QueueFull:
                                # Cola llena — descartar chunk mas viejo y agregar nuevo
                                try:
                                    self.audio_in_queue.get_nowait()
                                    self.audio_in_queue.put_nowait(response.data)
                                except Exception:
                                    pass

                    if response.server_content:
                        sc = response.server_content

                        if sc.output_transcription and sc.output_transcription.text:
                            txt = _clean_transcript(sc.output_transcription.text)
                            if txt:
                                out_buf.append(txt)

                        if sc.input_transcription and sc.input_transcription.text:
                            txt = _clean_transcript(sc.input_transcription.text)
                            if txt:
                                in_buf.append(txt)
                                full = " ".join(in_buf)
                                # ── DETECCION WAKE WORD ──────────────────
                                if self._sleeping:
                                    if is_wake_word(txt) or is_wake_word(full):
                                        print(f"[WakeWord] Detectado en transcripcion: '{txt}'")
                                        self.wake_detector.force_activate()
                                else:
                                    # Siempre resetear timer mientras el usuario habla
                                    self.wake_detector._reset_timer()
                                    # NOTA: NO interceptamos origin questions aquí porque:
                                    # 1. Gemini ya tiene la historia en el system prompt
                                    # 2. Mandar _speak_direct en medio del turno traba la sesión

                        if sc.turn_complete:
                            if self._turn_done_event:
                                self._turn_done_event.set()
                            full_in = " ".join(in_buf).strip()
                            if full_in:
                                self.ui.write_log("You: " + full_in)
                                # ── SEGUNDA OPORTUNIDAD de detectar wake word ──
                                if self._sleeping and is_wake_word(full_in):
                                    print(f"[WakeWord] Detectado al final del turno: '{full_in}'")
                                    self.wake_detector.force_activate()
                            in_buf = []
                            full_out = " ".join(out_buf).strip()
                            if full_out:
                                self.ui.write_log("Jarvis: " + full_out)
                            out_buf = []
                            # ── GUARDAR TURNO EN CONTEXTO DE SESIÓN ──────────
                            if full_in and not self._sleeping:
                                session_ctx.add_turn(
                                    user   = full_in,
                                    jarvis = full_out,
                                    tool   = self._last_tool_used,
                                )
                                self._last_tool_used = ""  # reset

                    if response.tool_call:
                        fn_responses = []
                        for fc in response.tool_call.function_calls:
                            fr = await self._execute_tool(fc)
                            fn_responses.append(fr)
                        await self.session.send_tool_response(
                            function_responses=fn_responses
                        )
        except Exception as e:
            print("[JARVIS] Recv error: " + str(e))
            traceback.print_exc()
            raise

    async def _play_audio(self):
        """Reproductor de audio robusto con reconexion automatica."""
        while True:
            stream = None
            try:
                stream = sd.RawOutputStream(
                    samplerate=RECEIVE_SAMPLE_RATE,
                    channels=CHANNELS,
                    dtype="int16",
                    blocksize=CHUNK_SIZE,
                )
                stream.start()
                print("[Audio] Stream iniciado.")

                while True:
                    try:
                        chunk = await asyncio.wait_for(
                            self.audio_in_queue.get(), timeout=0.05
                        )
                    except asyncio.TimeoutError:
                        if (self._turn_done_event
                                and self._turn_done_event.is_set()
                                and self.audio_in_queue.empty()):
                            self.set_speaking(False)
                            self._turn_done_event.clear()
                        continue

                    # Escribir audio directamente (mas fluido sin to_thread)
                    try:
                        self.set_speaking(True)
                        stream.write(chunk)
                    except Exception as write_err:
                        print(f"[Audio] Error escribiendo chunk: {write_err}")
                        break

            except Exception as e:
                print(f"[Audio] Stream error: {e} — reiniciando en 1s...")
                self.set_speaking(False)
                await asyncio.sleep(1)
            finally:
                if stream:
                    try:
                        stream.stop()
                        stream.close()
                    except Exception:
                        pass
                self.set_speaking(False)

    async def run(self):
        client = genai.Client(
            api_key=_get_api_key(),
            http_options={"api_version": "v1beta"}
        )
        while True:
            try:
                print("[JARVIS] Connecting...")
                self.ui.set_state("THINKING")
                config = self._build_config()
                async with (
                    client.aio.live.connect(model=LIVE_MODEL, config=config) as session,
                    asyncio.TaskGroup() as tg,
                ):
                    self.session          = session
                    self._loop            = asyncio.get_event_loop()
                    self.audio_in_queue   = asyncio.Queue(maxsize=100)
                    self.out_queue        = asyncio.Queue(maxsize=10)
                    self._turn_done_event = asyncio.Event()
                    self.ui.write_log("SYS: JARVIS en espera. Di 'Jarvis' para activar.")
                    self.ui.set_state("THINKING")
                    self.wake_detector.start()
                    tg.create_task(self._send_realtime())
                    tg.create_task(self._listen_audio())
                    tg.create_task(self._receive_audio())
                    tg.create_task(self._play_audio())
            except Exception as e:
                print("[JARVIS] Error: " + str(e))
                traceback.print_exc()
            self.set_speaking(False)
            self.ui.set_state("THINKING")
            await asyncio.sleep(3)


def main():
    ui = JarvisUI("face.png")
    restore_alarms(player=ui)
    # Activar modo nocturno automatico al iniciar
    from actions.night_mode import night_mode as _nm
    threading.Thread(
        target=lambda: _nm({"accion":"activar"}, player=ui),
        daemon=True
    ).start()

    def runner():
        ui.wait_for_api_key()
        jarvis = JarvisLive(ui)
        try:
            asyncio.run(jarvis.run())
        except KeyboardInterrupt:
            print("Shutting down...")
        finally:
            try:
                jarvis.scheduler.stop()
            except Exception:
                pass

    threading.Thread(target=runner, daemon=True).start()
    ui.root.mainloop()


if __name__ == "__main__":
    main()
