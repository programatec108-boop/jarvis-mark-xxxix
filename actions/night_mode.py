# night_mode.py - Modo nocturno automático para JARVIS
# Archivo: C:\Users\jose1\Mark-XXXIX\actions\night_mode.py

import subprocess
import time
import threading
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

_estado = {
    "activo": False,
    "hora_inicio": "22:00",
    "hora_fin": "07:00",
    "brillo_dia": 100,
    "brillo_noche": 30,
    "volumen_noche": 40,
    "en_modo_noche": False,
    "_monitor_thread": None,
}


def _set_brightness(level: int):
    """Ajusta brillo de pantalla en Windows (0-100)."""
    try:
        subprocess.run(
            ["powershell", "-Command",
             f"(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1,{level})"],
            capture_output=True, timeout=5
        )
        return True
    except Exception as e:
        print(f"[NightMode] Error brillo: {e}")
        return False


def _set_volume(level: int):
    """Ajusta volumen del sistema (0-100)."""
    try:
        script = f"""
        $vol = {level / 100}
        $wshell = New-Object -com 'WScript.Shell'
        $obj = New-Object -com 'Shell.Application'
        [Audio]::Volume = $vol
        """
        # Metodo alternativo via nircmd si esta disponible
        nircmd = Path("C:/Windows/System32/nircmd.exe")
        if nircmd.exists():
            subprocess.run([str(nircmd), "setsysvolume", str(int(level * 655.35))],
                          capture_output=True, timeout=3)
        else:
            # Via powershell con objeto COM
            subprocess.run(
                ["powershell", "-Command",
                 f"$obj = New-Object -ComObject WScript.Shell; "
                 f"for($i=0; $i -lt 50; $i++){{$obj.SendKeys([char]174)}}; "
                 f"for($i=0; $i -lt {int(level/2)}; $i++){{$obj.SendKeys([char]175)}}"],
                capture_output=True, timeout=5
            )
        return True
    except Exception as e:
        print(f"[NightMode] Error volumen: {e}")
        return False


def _is_night_time(hora_inicio: str, hora_fin: str) -> bool:
    """Determina si es hora nocturna."""
    now = datetime.now()
    current = now.hour * 60 + now.minute

    h_i, m_i = map(int, hora_inicio.split(":"))
    h_f, m_f = map(int, hora_fin.split(":"))

    inicio = h_i * 60 + m_i
    fin    = h_f * 60 + m_f

    if inicio > fin:  # cruza medianoche (ej: 22:00 - 07:00)
        return current >= inicio or current < fin
    else:
        return inicio <= current < fin


def _activate_night(speak=None, player=None):
    """Activa modo nocturno."""
    if _estado["en_modo_noche"]:
        return
    _estado["en_modo_noche"] = True
    _set_brightness(_estado["brillo_noche"])
    _set_volume(_estado["volumen_noche"])
    if player:
        player.write_log("[NightMode] Modo nocturno activado")
    if speak:
        speak("Modo nocturno activado. Reduciendo brillo y volumen.")
    print("[NightMode] NOCHE activada")


def _deactivate_night(speak=None, player=None):
    """Desactiva modo nocturno."""
    if not _estado["en_modo_noche"]:
        return
    _estado["en_modo_noche"] = False
    _set_brightness(_estado["brillo_dia"])
    if player:
        player.write_log("[NightMode] Modo diurno activado")
    if speak:
        speak("Buenos días. Restaurando configuración diurna.")
    print("[NightMode] DIA activado")


def _monitor_loop(speak, player):
    """Hilo que monitorea la hora y activa/desactiva modo nocturno."""
    print("[NightMode] Monitor iniciado")
    while _estado["activo"]:
        try:
            es_noche = _is_night_time(_estado["hora_inicio"], _estado["hora_fin"])
            if es_noche and not _estado["en_modo_noche"]:
                _activate_night(speak, player)
            elif not es_noche and _estado["en_modo_noche"]:
                _deactivate_night(speak, player)
        except Exception as e:
            print(f"[NightMode] Error monitor: {e}")
        time.sleep(60)  # Verificar cada minuto
    print("[NightMode] Monitor detenido")


def night_mode(parameters: dict, player=None, speak=None) -> str:
    """
    Modo nocturno automático.

    Acciones:
        activar    - Activar modo nocturno automático
        desactivar - Desactivar modo nocturno
        configurar - Cambiar hora de inicio/fin
        estado     - Ver configuración actual
        ahora      - Activar modo nocturno manualmente ahora
    """
    accion      = parameters.get("accion", "estado").lower()
    hora_inicio = parameters.get("hora_inicio", "").strip()
    hora_fin    = parameters.get("hora_fin", "").strip()
    brillo      = parameters.get("brillo", 0)
    volumen     = parameters.get("volumen", 0)

    # ── ACTIVAR AUTOMATICO ────────────────────────────────────────────────
    if accion in ("activar", "encender", "iniciar"):
        if hora_inicio:
            _estado["hora_inicio"] = hora_inicio
        if hora_fin:
            _estado["hora_fin"] = hora_fin
        if brillo:
            _estado["brillo_noche"] = int(brillo)
        if volumen:
            _estado["volumen_noche"] = int(volumen)

        if not _estado["activo"]:
            _estado["activo"] = True
            t = threading.Thread(
                target=_monitor_loop,
                args=(speak, player),
                daemon=True
            )
            _estado["_monitor_thread"] = t
            t.start()

        msg = (f"Modo nocturno automático activado. "
               f"Se activará a las {_estado['hora_inicio']} "
               f"y desactivará a las {_estado['hora_fin']}.")
        if speak: speak(msg)
        if player: player.write_log(f"[NightMode] {msg}")
        return msg

    # ── DESACTIVAR ────────────────────────────────────────────────────────
    elif accion in ("desactivar", "apagar", "detener"):
        _estado["activo"] = False
        if _estado["en_modo_noche"]:
            _deactivate_night(speak, player)
        msg = "Modo nocturno desactivado."
        if speak: speak(msg)
        return msg

    # ── ACTIVAR AHORA MANUALMENTE ─────────────────────────────────────────
    elif accion in ("ahora", "manual", "activar ahora"):
        _activate_night(speak, player)
        return "Modo nocturno activado manualmente."

    elif accion in ("dia", "diurno", "modo dia"):
        _deactivate_night(speak, player)
        return "Modo diurno activado."

    # ── CONFIGURAR ────────────────────────────────────────────────────────
    elif accion == "configurar":
        if hora_inicio: _estado["hora_inicio"] = hora_inicio
        if hora_fin:    _estado["hora_fin"] = hora_fin
        if brillo:      _estado["brillo_noche"] = int(brillo)
        if volumen:     _estado["volumen_noche"] = int(volumen)
        msg = f"Configurado: noche {_estado['hora_inicio']}-{_estado['hora_fin']}, brillo {_estado['brillo_noche']}%."
        if speak: speak(msg)
        return msg

    # ── ESTADO ────────────────────────────────────────────────────────────
    else:
        es_noche = _is_night_time(_estado["hora_inicio"], _estado["hora_fin"])
        estado_str = "nocturno" if _estado["en_modo_noche"] else "diurno"
        auto_str   = "activado" if _estado["activo"] else "desactivado"
        msg = (f"Modo actual: {estado_str}. "
               f"Monitor automático: {auto_str}. "
               f"Horario nocturno: {_estado['hora_inicio']} a {_estado['hora_fin']}.")
        if speak: speak(msg)
        return msg
