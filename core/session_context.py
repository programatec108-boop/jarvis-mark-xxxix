# session_context.py - Contexto de sesión y historial del día para JARVIS Mark XXXIX
# Archivo: C:\Users\jose1\Mark-XXXIX\core\session_context.py
#
# DOS CAPAS:
#   1. Sesión activa  — RAM — lo que pasó desde "Jarvis" hasta que se durmió
#   2. Historial día  — disco — todo el día, se limpia a medianoche
#
# Se inyecta en el system prompt de cada reconexión a Gemini.

import json
import threading
import time
import os
from datetime import datetime, date
from pathlib import Path
from collections import deque


# ── Configuración ─────────────────────────────────────────────────────────────

_MAX_SESSION_TURNS  = 30    # turnos máximos en sesión activa (RAM)
_MAX_DAY_TURNS      = 120   # turnos máximos en historial del día (disco)
_MAX_PROMPT_CHARS   = 3000  # límite de caracteres que se inyectan al prompt
_HISTORY_FILE_NAME  = "context_today.json"


def _get_history_path() -> Path:
    appdata = os.environ.get("APPDATA", str(Path.home()))
    d = Path(appdata) / "JARVIS_Mark39"
    d.mkdir(parents=True, exist_ok=True)
    return d / _HISTORY_FILE_NAME


# ── Estructura de un turno ────────────────────────────────────────────────────
#
# {
#   "ts":      "14:32",           # hora HH:MM
#   "user":    "pon Bad Bunny",   # lo que dijo el usuario
#   "jarvis":  "Poniendo Bad Bunny...",  # lo que respondió JARVIS
#   "tool":    "music_control",   # tool usada (opcional)
#   "session": "abc123"           # id de sesión (opcional)
# }


# ── SessionContext ─────────────────────────────────────────────────────────────

class SessionContext:
    """
    Mantiene el contexto conversacional en dos capas:
    - _session : deque en RAM — sesión activa actual
    - _day     : lista en disco — historial completo del día
    """

    def __init__(self):
        self._lock        = threading.Lock()
        self._session     = deque(maxlen=_MAX_SESSION_TURNS)
        self._day: list   = []
        self._session_id  = datetime.now().strftime("%H%M%S")
        self._today       = date.today()
        self._load_day()

    # ── Carga / guardado en disco ─────────────────────────────────────────────

    def _load_day(self):
        """Carga el historial del día desde disco. Si es de otro día, descarta."""
        try:
            path = _get_history_path()
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                saved_date = data.get("date", "")
                if saved_date == str(self._today):
                    self._day = data.get("turns", [])[-_MAX_DAY_TURNS:]
                    print(f"[Context] Historial cargado: {len(self._day)} turnos de hoy")
                else:
                    print(f"[Context] Día nuevo — historial anterior descartado")
                    self._day = []
        except Exception as e:
            print(f"[Context] Error cargando historial: {e}")
            self._day = []

    def _save_day(self):
        """Persiste el historial del día en disco."""
        try:
            path = _get_history_path()
            path.write_text(
                json.dumps({
                    "date":  str(self._today),
                    "turns": self._day[-_MAX_DAY_TURNS:],
                }, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
        except Exception as e:
            print(f"[Context] Error guardando historial: {e}")

    # ── Nueva sesión ──────────────────────────────────────────────────────────

    def new_session(self):
        """Llamar cuando JARVIS se activa (wake word). Limpia la sesión activa."""
        with self._lock:
            self._session.clear()
            self._session_id = datetime.now().strftime("%H%M%S")
            # Verificar si cambió el día
            today = date.today()
            if today != self._today:
                self._today = today
                self._day   = []
                print("[Context] Medianoche — historial del día reiniciado")
        print(f"[Context] Nueva sesión: {self._session_id}")

    # ── Registrar turno ───────────────────────────────────────────────────────

    def add_turn(self, user: str, jarvis: str, tool: str = ""):
        """
        Registra un turno completo (usuario + respuesta JARVIS).
        Llamar cuando turn_complete=True en _receive_audio.
        """
        if not user.strip() and not jarvis.strip():
            return

        turn = {
            "ts":      datetime.now().strftime("%H:%M"),
            "user":    user.strip()[:400],    # limitar largo
            "jarvis":  jarvis.strip()[:400],
            "session": self._session_id,
        }
        if tool:
            turn["tool"] = tool

        with self._lock:
            self._session.append(turn)
            self._day.append(turn)

        # Guardar en disco en hilo separado para no bloquear audio
        threading.Thread(target=self._save_day, daemon=True).start()
        print(f"[Context] Turno guardado — sesión: {len(self._session)}, día: {len(self._day)}")

    # ── Formatear para prompt ─────────────────────────────────────────────────

    def format_for_prompt(self) -> str:
        """
        Genera el bloque de contexto que se inyecta en el system prompt.
        Prioriza la sesión activa, luego historial reciente del día.
        Respeta el límite de _MAX_PROMPT_CHARS.
        """
        with self._lock:
            session_turns = list(self._session)
            day_turns     = list(self._day)

        if not session_turns and not day_turns:
            return ""

        lines = []

        # ── Sesión activa ─────────────────────────────────────────────────────
        if session_turns:
            lines.append("[CONTEXTO DE ESTA SESIÓN — Lo que pasó en esta conversación]")
            for t in session_turns:
                tool_str = f" [usé: {t['tool']}]" if t.get("tool") else ""
                if t.get("user"):
                    lines.append(f"  {t['ts']} Usuario: {t['user']}")
                if t.get("jarvis"):
                    lines.append(f"  {t['ts']} JARVIS: {t['jarvis']}{tool_str}")

        # ── Historial del día (turnos fuera de la sesión activa) ──────────────
        session_ids_in_day = {t.get("session") for t in session_turns}
        prev_turns = [
            t for t in day_turns
            if t.get("session") not in session_ids_in_day
               or t.get("session") != self._session_id
        ]
        # Quitar los que ya están en sesión activa
        session_set = set(
            (t["ts"], t.get("user","")) for t in session_turns
        )
        prev_turns = [
            t for t in prev_turns
            if (t["ts"], t.get("user","")) not in session_set
        ]

        if prev_turns:
            # Solo los últimos 10 del día fuera de sesión activa
            recent_prev = prev_turns[-10:]
            lines.append("\n[HISTORIAL DE HOY — Conversaciones anteriores de este día]")
            for t in recent_prev:
                tool_str = f" [usé: {t['tool']}]" if t.get("tool") else ""
                if t.get("user"):
                    lines.append(f"  {t['ts']} Usuario: {t['user']}")
                if t.get("jarvis"):
                    lines.append(f"  {t['ts']} JARVIS: {t['jarvis']}{tool_str}")

        lines.append(
            "\nUsa este contexto para:\n"
            "- Entender referencias como 'lo mismo de antes', 'el restaurante que me dijiste', 'eso que pedí'\n"
            "- Continuar tareas sin que el usuario repita información\n"
            "- Responder '¿qué te pedí antes?' con el historial real\n"
            "NO menciones explícitamente que 'tienes un historial' — úsalo de forma natural.\n"
        )

        full = "\n".join(lines)

        # Respetar límite de caracteres — truncar desde el inicio si es muy largo
        if len(full) > _MAX_PROMPT_CHARS:
            full = "...[contexto truncado]\n" + full[-_MAX_PROMPT_CHARS:]

        return full

    # ── Consultas ─────────────────────────────────────────────────────────────

    def get_last_user_message(self) -> str:
        """Último mensaje del usuario en la sesión activa."""
        with self._lock:
            if self._session:
                return list(self._session)[-1].get("user", "")
        return ""

    def get_last_tool_used(self) -> str:
        """Última tool usada en la sesión activa."""
        with self._lock:
            for t in reversed(list(self._session)):
                if t.get("tool"):
                    return t["tool"]
        return ""

    def get_session_summary(self) -> str:
        """Resumen legible para logs — cuántos turnos en sesión y día."""
        with self._lock:
            return (
                f"Sesión: {len(self._session)} turnos | "
                f"Hoy: {len(self._day)} turnos"
            )

    def clear_session(self):
        """Llamar cuando JARVIS se duerme."""
        with self._lock:
            self._session.clear()
        print("[Context] Sesión activa limpiada")


# ── Instancia global ──────────────────────────────────────────────────────────
# Se importa desde main.py como: from core.session_context import session_ctx

session_ctx = SessionContext()
