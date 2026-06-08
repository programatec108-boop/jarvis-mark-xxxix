# smart_home.py - Domotica IoT para JARVIS Mark XXXIX
# Archivo: C:\Users\jose1\Mark-XXXIX\actions\smart_home.py
# Requiere: pip install tuya-connector-python

import json
from pathlib import Path
from tuya_connector import TuyaOpenAPI

BASE_DIR    = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"

# IDs fijos de tus dispositivos
DEVICE_IDS = {
    "sala":             "ebd878f04f47272967ocgl",
    "sala tele":        "ebf839dd5b6b241d5fkhgn",
    "cuarto emmanuel":  "eb7e78460a542027727lds",
    "cuarto":           "eb7e78460a542027727lds",
    "emmanuel":         "eb7e78460a542027727lds",
    "fuente":           "ebc134b34166734fb1qrg1",
}

COLOR_MAP = {
    "rojo":     {"h": 0,   "s": 1000, "v": 1000},
    "azul":     {"h": 240, "s": 1000, "v": 1000},
    "verde":    {"h": 120, "s": 1000, "v": 1000},
    "blanco":   {"h": 0,   "s": 0,    "v": 1000},
    "amarillo": {"h": 60,  "s": 1000, "v": 1000},
    "naranja":  {"h": 30,  "s": 1000, "v": 1000},
    "morado":   {"h": 270, "s": 1000, "v": 1000},
    "rosa":     {"h": 330, "s": 700,  "v": 1000},
    "cyan":     {"h": 180, "s": 1000, "v": 1000},
    "calido":   {"h": 30,  "s": 400,  "v": 1000},
    "frio":     {"h": 210, "s": 200,  "v": 1000},
}


def _get_api():
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        api  = TuyaOpenAPI(
            data.get("tuya_base_url", "https://openapi.tuyaus.com"),
            data.get("tuya_access_id", ""),
            data.get("tuya_access_secret", ""),
        )
        api.connect()
        return api
    except Exception as e:
        print("[SmartHome] API error: " + str(e))
        return None


def _find_device_id(name_query):
    key = name_query.lower().strip()
    if key in DEVICE_IDS:
        return DEVICE_IDS[key], key
    for k, v in DEVICE_IDS.items():
        if key in k or k in key:
            return v, k
    return None, None


def _send_commands(api, device_id, commands):
    try:
        r = api.post("/v1.0/devices/" + device_id + "/commands",
                     {"commands": commands})
        return r.get("success", False)
    except Exception as e:
        print("[SmartHome] Command error: " + str(e))
        return False


def smart_home(parameters, player=None, speak=None):
    global DEVICES
    DEVICES = _load_devices()  # Recargar siempre por si el usuario agrego nuevos
    action = parameters.get("action", "").lower().strip()
    device = parameters.get("device", "").lower().strip()
    value  = parameters.get("value", None)

    api = _get_api()
    if not api:
        return "No pude conectar con Tuya, jefe."

    # Listar dispositivos
    if action == "list":
        names = list(dict.fromkeys(DEVICE_IDS.keys()))
        nombres = ["sala", "sala tele", "cuarto Emmanuel", "fuente"]
        return "Dispositivos disponibles: " + ", ".join(nombres) + "."

    if not device:
        return "Dime que dispositivo quieres controlar, jefe."

    device_id, matched = _find_device_id(device)
    if not device_id:
        return "No encontre '" + device + "'. Dispositivos: sala, sala tele, cuarto Emmanuel, fuente."

    device_name = matched.title()

    # ENCENDER
    if action in ("turn_on", "encender", "on", "enciende"):
        # Focos usan switch_led, enchufes usan switch_1
        ok = _send_commands(api, device_id, [{"code": "switch_led", "value": True}])
        if not ok:
            ok = _send_commands(api, device_id, [{"code": "switch_1", "value": True}])
        return device_name + (" encendido." if ok else ": no pude encenderlo, puede estar desconectado.")

    # APAGAR
    elif action in ("turn_off", "apagar", "off", "apaga"):
        ok = _send_commands(api, device_id, [{"code": "switch_led", "value": False}])
        if not ok:
            ok = _send_commands(api, device_id, [{"code": "switch_1", "value": False}])
        return device_name + (" apagado." if ok else ": no pude apagarlo, puede estar desconectado.")

    # BRILLO
    elif action in ("brightness", "brillo"):
        if value is None:
            return "Dime el nivel de brillo del 0 al 100, jefe."
        try:
            level      = max(10, min(1000, int(float(str(value))) * 10))
            ok = _send_commands(api, device_id, [{"code": "bright_value_v2", "value": level}])
            if not ok:
                ok = _send_commands(api, device_id, [{"code": "bright_value", "value": level}])
            return device_name + (" al " + str(level // 10) + "% de brillo." if ok else ": no pude cambiar el brillo.")
        except Exception:
            return "Valor de brillo invalido."

    # COLOR
    elif action in ("color", "colour"):
        if value is None:
            return "Dime el color, jefe. Opciones: rojo, azul, verde, blanco, amarillo, naranja, morado, rosa, cyan."
        color_key = str(value).lower().strip()
        if color_key not in COLOR_MAP:
            return "Color '" + color_key + "' no reconocido. Usa: " + ", ".join(COLOR_MAP.keys()) + "."
        hsv = COLOR_MAP[color_key]
        # Cambiar a modo color primero
        ok = _send_commands(api, device_id, [
            {"code": "work_mode", "value": "colour"},
            {"code": "colour_data_v2", "value": hsv}
        ])
        return device_name + (" cambiado a " + color_key + "." if ok else ": no pude cambiar el color.")

    # ESTADO
    elif action in ("status", "estado"):
        try:
            r = api.get("/v1.0/devices/" + device_id)
            if r.get("success"):
                online = r["result"].get("online", False)
                status = r["result"].get("status", [])
                encendido = next((s["value"] for s in status if s["code"] in ("switch_led", "switch_1")), None)
                estado = "encendido" if encendido else "apagado"
                conexion = "online" if online else "desconectado"
                return device_name + " esta " + estado + " y " + conexion + "."
        except Exception as e:
            return "No pude obtener el estado: " + str(e)

    else:
        return "Accion '" + action + "' no reconocida. Usa: turn_on, turn_off, brightness, color, list, status."
