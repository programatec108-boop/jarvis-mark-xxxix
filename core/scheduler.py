# scheduler.py - Motor de auto-rutinas para JARVIS Mark XXXIX
# Archivo: C:\Users\jose1\Mark-XXXIX\core\scheduler.py
#
# CÓMO FUNCIONA:
#   Lee las rutinas de preferences.json cada minuto
#   Si la hora y el día coinciden, ejecuta cada tarea via speak()
#   speak() manda la tarea a Gemini Live que la ejecuta con su personalidad
#
# ESTRUCTURA DE UNA RUTINA EN preferences.json:
#   {
#     "time":  "07:00",           # HH:MM en 24h
#     "days":  "L-V",             # Todos | L-V | L,M,X,J,V | Fines | Lunes | etc.
#     "tasks": [
#       "pon noticias del día",
#       "enciende las luces de la sala",
#       "saluda buenos días con el clima de hoy"
#     ]
#   }

import json
import threading
import time
import os
from datetime import datetime
from pathlib import Path


# ── Mapeo de días ─────────────────────────────────────────────────────────────

_WEEKDAYS = {
    "lunes":0, "l":0, "monday":0,
    "martes":1, "m":1, "tuesday":1,
    "miércoles":2, "miercoles":2, "x":2, "wednesday":2,
    "jueves":3, "j":3, "thursday":3,
    "viernes":4, "v":4, "friday":4,
    "sábado":5, "sabado":5, "s":5, "saturday":5,
    "domingo":6, "d":6, "sunday":6,
}

_RANGES = {
    "l-v":    [0,1,2,3,4],
    "lunes-viernes": [0,1,2,3,4],
    "fines":  [5,6],
    "fines de semana": [5,6],
    "weekend":[5,6],
    "todos":  [0,1,2,3,4,5,6],
    "all":    [0,1,2,3,4,5,6],
    "diario": [0,1,2,3,4,5,6],
}


def _parse_days(days_str: str) -> list[int]:
    """
    Convierte el string de días a lista de weekday integers (0=Lunes, 6=Domingo).
    Soporta: 'Todos', 'L-V', 'Fines', 'L,M,X', 'Lunes', 'Lunes,Miércoles'
    """
    if not days_str:
        return list(range(7))

    s = days_str.lower().strip()

    # Rango predefinido
    if s in _RANGES:
        return _RANGES[s]

    # Múltiples días separados por coma o espacio
    separators = [",", "/", " y ", ";"]
    parts = [s]
    for sep in separators:
        new_parts = []
        for p in parts:
            new_parts.extend(p.split(sep))
        parts = new_parts

    result = []
    for part in parts:
        part = part.strip()
        # Rango con guión tipo "L-V"
        if "-" in part:
            sub = part.split("-")
            if len(sub) == 2:
                start = _WEEKDAYS.get(sub[0].strip())
                end   = _WEEKDAYS.get(sub[1].strip())
                if start is not None and end is not None:
                    if start <= end:
                        result.extend(range(start, end+1))
                    else:
                        result.extend(range(start, 7))
                        result.extend(range(0, end+1))
        elif part in _WEEKDAYS:
            result.append(_WEEKDAYS[part])

    return list(set(result)) if result else list(range(7))


def _matches_now(time_str: str, days_str: str) -> bool:
    """True si la hora y el día de hoy coinciden con la rutina."""
    now = datetime.now()
    # Verificar hora HH:MM
    try:
        h, m = map(int, time_str.strip().split(":"))
        if now.hour != h or now.minute != m:
            return False
    except Exception:
        return False
    # Verificar día (0=Lunes en Python)
    today = now.weekday()
    allowed = _parse_days(days_str)
    return today in allowed


# ── Scheduler ─────────────────────────────────────────────────────────────────

class Scheduler:
    """
    Ejecuta rutinas automáticamente según horario y días configurados.
    Se integra con JARVIS via speak() → Gemini Live.
    """

    def __init__(self, get_routines_fn, speak_fn, is_active_fn=None, force_activate_fn=None):
        """
        get_routines_fn   : callable → list[dict]  — lee las rutinas actuales
        speak_fn          : callable(str)           — manda texto a Gemini Live
        is_active_fn      : callable → bool         — True si JARVIS está despierto
        force_activate_fn : callable                — activa JARVIS si está dormido
        """
        self._get_routines    = get_routines_fn
        self._speak           = speak_fn
        self._is_active       = is_active_fn or (lambda: True)
        self._force_activate_fn = force_activate_fn
        self._running         = False
        self._thread          = None
        self._fired           = set()

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread  = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        print("[Scheduler] Motor de rutinas iniciado.")

    def stop(self):
        self._running = False
        print("[Scheduler] Motor de rutinas detenido.")

    def _loop(self):
        """Revisa cada 20 segundos si hay alguna rutina que ejecutar."""
        last_day = datetime.now().date()

        while self._running:
            try:
                now      = datetime.now()
                today    = now.date()

                # Limpiar fired al cambiar de día
                if today != last_day:
                    self._fired.clear()
                    last_day = today

                routines = self._get_routines()
                for r in routines:
                    time_str = r.get("time", "").strip()
                    days_str = r.get("days", "Todos").strip()
                    tasks    = r.get("tasks", [])

                    if not time_str or not tasks:
                        continue

                    # Clave única para evitar doble disparo en el mismo minuto
                    key = f"{time_str}-{today}"
                    if key in self._fired:
                        continue

                    if _matches_now(time_str, days_str):
                        self._fired.add(key)
                        print(f"[Scheduler] ✓ Rutina disparada: {time_str} — {len(tasks)} tarea(s)")
                        threading.Thread(
                            target=self._execute_routine,
                            args=(r, tasks),
                            daemon=True
                        ).start()

            except Exception as e:
                print(f"[Scheduler] Error en loop: {e}")

            time.sleep(20)   # revisar cada 20s para no perderse el minuto

    def _execute_routine(self, routine: dict, tasks: list):
        """Ejecuta todas las tareas de una rutina con pausa entre ellas."""
        time_str = routine.get("time", "")
        days_str = routine.get("days", "Todos")

        print(f"[Scheduler] Ejecutando rutina {time_str} ({days_str}): {tasks}")

        # Si JARVIS está dormido, intentar activarlo via force_activate
        if not self._is_active():
            print("[Scheduler] JARVIS dormido — intentando activar para rutina")
            # Llamar force_activate si está disponible
            if self._force_activate_fn:
                try:
                    self._force_activate_fn()
                except Exception as e:
                    print(f"[Scheduler] Error activando JARVIS: {e}")
            # Esperar a que se active (máx 8s)
            for _ in range(16):
                if self._is_active():
                    break
                time.sleep(0.5)
            if not self._is_active():
                print("[Scheduler] JARVIS no se activó — ejecutando rutina de todas formas")

        for i, task in enumerate(tasks):
            if not task.strip():
                continue
            try:
                print(f"[Scheduler] Tarea {i+1}/{len(tasks)}: '{task}'")
                instruccion = (
                    f"[RUTINA AUTOMÁTICA — {time_str}] "
                    f"Ejecuta esta tarea de forma proactiva con tu personalidad activa: "
                    f"{task}"
                )
                self._speak(instruccion)
                time.sleep(4)
            except Exception as e:
                print(f"[Scheduler] Error ejecutando tarea '{task}': {e}")

    def reload(self):
        """Fuerza recarga de rutinas — llamar cuando el usuario guarda ajustes."""
        print("[Scheduler] Rutinas recargadas desde preferences.json")


# ── Instancia global ──────────────────────────────────────────────────────────
# Se crea en main.py: scheduler = Scheduler(get_routines, speak, is_active)
