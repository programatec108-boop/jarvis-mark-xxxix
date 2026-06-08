# smart_alarm.py - Alarmas, Cronometro y Temporizador para JARVIS Mark XXXIX
# Archivo: C:\Users\jose1\Mark-XXXIX\actions\smart_alarm.py

import threading
import time
import datetime
import json
import os
import subprocess
from pathlib import Path
import sys

BASE_DIR    = Path(__file__).resolve().parent.parent
ALARMS_FILE = BASE_DIR / "memory" / "alarms.json"

_active_alarms = {}
_stopwatches   = {}
_timers        = {}
_lock = threading.Lock()


# ─── UTILIDADES ───────────────────────────────────────────────────────────────

def _load_alarms():
    if not ALARMS_FILE.exists():
        return []
    try:
        return json.loads(ALARMS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_alarms(alarms):
    ALARMS_FILE.parent.mkdir(parents=True, exist_ok=True)
    ALARMS_FILE.write_text(
        json.dumps(alarms, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _play_sound(music_path):
    """Reproduce musica o beep. Sin popups."""
    try:
        if music_path and Path(music_path).exists():
            if sys.platform == "win32":
                os.startfile(music_path)
            else:
                subprocess.Popen(["xdg-open", music_path])
        else:
            # Beep de sistema sin popup
            if sys.platform == "win32":
                import winsound
                def _beep():
                    for _ in range(6):
                        winsound.Beep(1000, 600)
                        time.sleep(0.2)
                threading.Thread(target=_beep, daemon=True).start()
    except Exception as e:
        print("[Alarm] Sound error: " + str(e))


# ─── ALARMAS ──────────────────────────────────────────────────────────────────

def _fire_alarm(alarm_id, message, music_path, player=None):
    print("[Alarm] Firing: " + alarm_id + " - " + message)

    # Solo reproducir sonido/musica, sin popup
    _play_sound(music_path)

    # Log en la UI de JARVIS
    if player:
        try:
            player.write_log("ALARM: " + message)
        except Exception:
            pass

    # Que JARVIS lo diga en voz
    # (el speak se inyecta via player si esta disponible)

    with _lock:
        _active_alarms.pop(alarm_id, None)
    alarms = _load_alarms()
    alarms = [a for a in alarms if a.get("id") != alarm_id]
    _save_alarms(alarms)


def _fire_timer(timer_id, message, player=None, speak=None):
    print("[Timer] Done: " + timer_id + " - " + message)

    # Solo beep, sin popup
    _play_sound(None)

    if player:
        try:
            player.write_log("TIMER: " + message)
        except Exception:
            pass

    with _lock:
        _timers.pop(timer_id, None)


def set_alarm(alarm_time, message="Alarma, jefe!", music_path=None, player=None):
    try:
        parts  = alarm_time.strip().split(":")
        hour   = int(parts[0])
        minute = int(parts[1])
        second = int(parts[2]) if len(parts) > 2 else 0
    except Exception:
        return "No entendi la hora. Usa formato HH:MM."

    now    = datetime.datetime.now()
    target = now.replace(hour=hour, minute=minute, second=second, microsecond=0)
    if target <= now:
        target += datetime.timedelta(days=1)

    delay_sec = (target - now).total_seconds()
    alarm_id  = "alarm_" + str(hour).zfill(2) + str(minute).zfill(2) + str(second).zfill(2)

    with _lock:
        if alarm_id in _active_alarms:
            _active_alarms[alarm_id].cancel()

    t = threading.Timer(delay_sec, _fire_alarm, args=[alarm_id, message, music_path, player])
    t.daemon = True
    t.start()

    with _lock:
        _active_alarms[alarm_id] = t

    alarms = _load_alarms()
    alarms = [a for a in alarms if a.get("id") != alarm_id]
    alarms.append({
        "id": alarm_id,
        "time": str(hour).zfill(2) + ":" + str(minute).zfill(2),
        "message": message,
        "music_path": music_path,
        "target_iso": target.isoformat(),
    })
    _save_alarms(alarms)
    return "Alarma programada para las " + target.strftime("%I:%M %p") + "."


def cancel_alarm(alarm_time):
    try:
        parts  = alarm_time.strip().split(":")
        hour   = int(parts[0])
        minute = int(parts[1])
        second = int(parts[2]) if len(parts) > 2 else 0
    except Exception:
        return "No entendi la hora."

    alarm_id = "alarm_" + str(hour).zfill(2) + str(minute).zfill(2) + str(second).zfill(2)

    with _lock:
        timer = _active_alarms.pop(alarm_id, None)
    if timer:
        timer.cancel()

    alarms = _load_alarms()
    before = len(alarms)
    alarms = [a for a in alarms if a.get("id") != alarm_id]
    _save_alarms(alarms)

    if before > len(alarms) or timer:
        return "Alarma cancelada."
    return "No encontre alarma a esa hora."


def list_alarms():
    alarms = _load_alarms()
    if not alarms:
        return "No hay alarmas programadas, jefe."
    lines = ["Alarmas activas:"]
    for a in alarms:
        lines.append("  - " + a["time"] + " - " + a["message"])
    return "\n".join(lines)


def restore_alarms(player=None):
    alarms = _load_alarms()
    now    = datetime.datetime.now()
    kept   = []
    for a in alarms:
        try:
            target = datetime.datetime.fromisoformat(a["target_iso"])
            if target <= now:
                continue
            delay = (target - now).total_seconds()
            t = threading.Timer(delay, _fire_alarm, args=[a["id"], a["message"], a.get("music_path"), player])
            t.daemon = True
            t.start()
            with _lock:
                _active_alarms[a["id"]] = t
            kept.append(a)
        except Exception as e:
            print("[Alarm] Restore error: " + str(e))
    _save_alarms(kept)


# ─── CRONOMETRO ───────────────────────────────────────────────────────────────

def stopwatch_start(name="default"):
    with _lock:
        _stopwatches[name] = {"start": time.time(), "laps": [], "elapsed": 0.0}
    return "Cronometro iniciado."


def stopwatch_lap(name="default"):
    with _lock:
        sw = _stopwatches.get(name)
    if not sw:
        return "No hay cronometro activo."
    elapsed = sw["elapsed"] + (time.time() - sw["start"])
    lap_num = len(sw["laps"]) + 1
    sw["laps"].append(elapsed)
    mins = int(elapsed // 60)
    secs = elapsed % 60
    return "Vuelta " + str(lap_num) + ": " + str(mins) + "m " + "{:.2f}".format(secs) + "s"


def stopwatch_stop(name="default"):
    with _lock:
        sw = _stopwatches.pop(name, None)
    if not sw:
        return "No habia cronometro activo."
    elapsed = sw["elapsed"] + (time.time() - sw["start"])
    mins    = int(elapsed // 60)
    secs    = elapsed % 60
    result  = "Tiempo total: " + str(mins) + "m " + "{:.2f}".format(secs) + "s"
    if sw["laps"]:
        result += ". Vueltas registradas: " + str(len(sw["laps"]))
    return result


def stopwatch_status(name="default"):
    with _lock:
        sw = _stopwatches.get(name)
    if not sw:
        return "No hay cronometro activo."
    elapsed = sw["elapsed"] + (time.time() - sw["start"])
    mins    = int(elapsed // 60)
    secs    = elapsed % 60
    return "Cronometro en curso: " + str(mins) + "m " + "{:.2f}".format(secs) + "s"


# ─── TEMPORIZADOR ─────────────────────────────────────────────────────────────

def start_timer(seconds=0, minutes=0, hours=0, message="Tiempo terminado, jefe!", player=None, speak=None):
    total_seconds = int(hours * 3600 + minutes * 60 + seconds)
    if total_seconds <= 0:
        return "Necesito una duracion valida."

    timer_id = "timer_" + str(int(time.time()))

    with _lock:
        for t in list(_timers.values()):
            t.cancel()
        _timers.clear()

    t = threading.Timer(total_seconds, _fire_timer, args=[timer_id, message, player, speak])
    t.daemon = True
    t.start()

    with _lock:
        _timers[timer_id] = t

    parts = []
    if hours > 0:
        parts.append(str(int(hours)) + "h")
    if minutes > 0:
        parts.append(str(int(minutes)) + "min")
    if seconds > 0:
        parts.append(str(int(seconds)) + "s")

    return "Temporizador de " + " ".join(parts) + " iniciado."


def cancel_timer():
    with _lock:
        if not _timers:
            return "No hay temporizador activo."
        for t in _timers.values():
            t.cancel()
        _timers.clear()
    return "Temporizador cancelado."


# ─── PUNTO DE ENTRADA ─────────────────────────────────────────────────────────

def smart_alarm(parameters, player=None, speak=None):
    action = parameters.get("action", "set").lower()

    if action == "set":
        alarm_time = parameters.get("time", "")
        if not alarm_time:
            return "Necesito una hora para la alarma, jefe."
        return set_alarm(
            alarm_time,
            parameters.get("message", "Alarma, jefe!"),
            parameters.get("music_path"),
            player=player,
        )
    elif action == "cancel":
        return cancel_alarm(parameters.get("time", ""))
    elif action == "list":
        return list_alarms()
    elif action == "stopwatch_start":
        return stopwatch_start(parameters.get("name", "default"))
    elif action == "stopwatch_lap":
        return stopwatch_lap(parameters.get("name", "default"))
    elif action == "stopwatch_stop":
        return stopwatch_stop(parameters.get("name", "default"))
    elif action == "stopwatch_status":
        return stopwatch_status(parameters.get("name", "default"))
    elif action == "timer_start":
        return start_timer(
            seconds=float(parameters.get("seconds", 0)),
            minutes=float(parameters.get("minutes", 0)),
            hours=float(parameters.get("hours", 0)),
            message=parameters.get("message", "Tiempo terminado, jefe!"),
            player=player,
            speak=speak,
        )
    elif action == "timer_cancel":
        return cancel_timer()
    else:
        return "Accion no reconocida: " + action
