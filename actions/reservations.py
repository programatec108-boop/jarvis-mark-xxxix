# reservations.py - Sistema de reservaciones para JARVIS Mark XXXIX
# Cubre: vuelos, restaurantes, hoteles
# Archivo: C:\Users\jose1\Mark-XXXIX\actions\reservations.py

import subprocess
import urllib.parse
import json
import time
import re
from pathlib import Path
from datetime import datetime


# ── Helpers ───────────────────────────────────────────────────────────────────

def _open_browser(url: str, browser: str = "edge"):
    """Abre una URL en el navegador configurado."""
    try:
        if browser == "chrome":
            subprocess.Popen(f'start chrome "{url}"', shell=True)
        else:
            subprocess.Popen(f'start msedge "{url}"', shell=True)
        time.sleep(0.6)
    except Exception as e:
        print(f"[Reservaciones] Error abriendo navegador: {e}")


def _whatsapp_url(phone: str, mensaje: str) -> str:
    """Genera URL de WhatsApp Web con mensaje prellenado."""
    phone_clean = re.sub(r"[^\d+]", "", phone)
    if not phone_clean.startswith("+"):
        # Si no tiene código de país, asumir México (+52)
        if phone_clean.startswith("52"):
            phone_clean = "+" + phone_clean
        else:
            phone_clean = "+52" + phone_clean
    msg_encoded = urllib.parse.quote(mensaje)
    return f"https://wa.me/{phone_clean}?text={msg_encoded}"


def _load_user_prefs() -> dict:
    try:
        base = Path(__file__).resolve().parent.parent
        pref = base / "config" / "preferences.json"
        if pref.exists():
            return json.loads(pref.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[Reservaciones] Error prefs: {e}")
    return {}


def _get_call_me() -> str:
    return _load_user_prefs().get("call_me", "jefe")


# ── Vuelos ────────────────────────────────────────────────────────────────────

def _buscar_vuelos(origen: str, destino: str, fecha_ida: str,
                   fecha_vuelta: str = "", pasajeros: int = 1,
                   cabina: str = "economy") -> str:
    """
    Abre Google Flights, Kayak y Skyscanner en paralelo con los datos llenos.
    """
    call_me = _get_call_me()

    # ── Google Flights ────────────────────────────────────────────────────────
    # Formato de fecha Google: YYYY-MM-DD
    gf_params = f"{urllib.parse.quote(origen)}/{urllib.parse.quote(destino)}"
    gf_fecha  = fecha_ida.replace("/", "-")
    gf_url    = f"https://www.google.com/travel/flights/search?q=vuelos+de+{urllib.parse.quote(origen)}+a+{urllib.parse.quote(destino)}+{gf_fecha}"

    # ── Kayak ─────────────────────────────────────────────────────────────────
    kayak_fecha  = fecha_ida.replace("/", "-").replace(".", "-")
    kayak_vuelta = f"/{fecha_vuelta.replace('/', '-')}" if fecha_vuelta else ""
    kayak_url    = (
        f"https://www.kayak.com.mx/flights/"
        f"{urllib.parse.quote(origen)}-{urllib.parse.quote(destino)}"
        f"/{kayak_fecha}{kayak_vuelta}/{pasajeros}"
    )

    # ── Skyscanner ────────────────────────────────────────────────────────────
    sky_fecha = fecha_ida.replace("/", "").replace("-", "")[:6]  # YYYYMM
    sky_url   = (
        f"https://www.skyscanner.com.mx/vuelos/"
        f"{urllib.parse.quote(origen.lower())}/"
        f"{urllib.parse.quote(destino.lower())}/"
        f"{fecha_ida.replace('/', '-')}/"
    )

    # Abrir los tres
    _open_browser(gf_url)
    time.sleep(0.8)
    _open_browser(kayak_url)
    time.sleep(0.8)
    _open_browser(sky_url)

    info = (
        f"origen={origen}, destino={destino}, fecha={fecha_ida}"
        + (f", vuelta={fecha_vuelta}" if fecha_vuelta else "")
        + f", pasajeros={pasajeros}"
    )
    return f"Vuelos abiertos en Google Flights, Kayak y Skyscanner. {info}"


# ── Restaurantes ──────────────────────────────────────────────────────────────

def _reservar_restaurante(nombre: str, telefono: str = "", personas: int = 2,
                           fecha: str = "", hora: str = "",
                           ciudad: str = "", notas: str = "") -> str:
    """
    Si tiene teléfono → manda WhatsApp con mensaje de reservación.
    Si no → busca el restaurante en Google Maps para encontrar contacto.
    """
    call_me = _get_call_me()

    # Construir mensaje de reservación
    fecha_str  = fecha or datetime.now().strftime("%d/%m/%Y")
    hora_str   = hora  or "a confirmar"
    notas_str  = f"\nNotas: {notas}" if notas else ""

    mensaje_wa = (
        f"¡Hola! Quisiera hacer una reservación en {nombre}.\n\n"
        f"📅 Fecha: {fecha_str}\n"
        f"🕐 Hora: {hora_str}\n"
        f"👥 Personas: {personas}\n"
        f"{notas_str}\n"
        f"¿Tienen disponibilidad? Muchas gracias."
    )

    if telefono:
        # Tiene teléfono → abrir WhatsApp
        wa_url = _whatsapp_url(telefono, mensaje_wa)
        _open_browser(wa_url)
        return f"WhatsApp abierto para {nombre} ({telefono}) con mensaje de reservación listo."
    else:
        # Sin teléfono → buscar en Google Maps
        query    = f"{nombre} {ciudad} teléfono reservaciones"
        maps_url = f"https://www.google.com/maps/search/{urllib.parse.quote(query)}"
        _open_browser(maps_url)
        return f"Abrí Google Maps para encontrar el contacto de {nombre}. Búscalo y dime el número para mandar el WhatsApp."


# ── Hoteles ───────────────────────────────────────────────────────────────────

def _buscar_hoteles(ciudad: str, check_in: str, check_out: str,
                    huespedes: int = 1, estrellas: int = 0) -> str:
    """Abre Booking y Google Hotels con los parámetros dados."""

    # ── Booking.com ───────────────────────────────────────────────────────────
    booking_url = (
        f"https://www.booking.com/searchresults.es.html"
        f"?ss={urllib.parse.quote(ciudad)}"
        f"&checkin={check_in}&checkout={check_out}"
        f"&group_adults={huespedes}&no_rooms=1"
        + (f"&class={estrellas}" if estrellas else "")
    )

    # ── Google Hotels ─────────────────────────────────────────────────────────
    google_hotels = (
        f"https://www.google.com/travel/hotels/s/search"
        f"?q=hoteles+en+{urllib.parse.quote(ciudad)}"
        f"&checkin={check_in}&checkout={check_out}"
        f"&guests={huespedes}"
    )

    _open_browser(booking_url)
    time.sleep(0.8)
    _open_browser(google_hotels)

    return f"Hoteles en {ciudad} abiertos en Booking y Google Hotels. Check-in: {check_in}, Check-out: {check_out}."


# ── Función principal ─────────────────────────────────────────────────────────

def reservations(parameters: dict, player=None, speak=None) -> str:
    """
    Sistema de reservaciones de JARVIS.

    Parámetros:
        tipo        : vuelo | restaurante | hotel
        -- VUELOS --
        origen      : ciudad o aeropuerto de origen
        destino     : ciudad o aeropuerto de destino
        fecha_ida   : fecha de ida (DD/MM/YYYY o YYYY-MM-DD)
        fecha_vuelta: fecha de vuelta (opcional, para ida y vuelta)
        pasajeros   : número de pasajeros (default 1)
        cabina      : economy | business | first (default economy)
        -- RESTAURANTES --
        nombre      : nombre del restaurante
        telefono    : número de teléfono o WhatsApp (con o sin código país)
        personas    : número de personas (default 2)
        fecha       : fecha de la reservación
        hora        : hora de la reservación
        ciudad      : ciudad del restaurante (para búsqueda en Maps)
        notas       : peticiones especiales, alergias, etc.
        -- HOTELES --
        ciudad      : ciudad del hotel
        check_in    : fecha de entrada (YYYY-MM-DD)
        check_out   : fecha de salida (YYYY-MM-DD)
        huespedes   : número de huéspedes (default 1)
        estrellas   : filtro de estrellas 1-5 (opcional)
    """
    tipo     = (parameters.get("tipo") or "").lower().strip()
    call_me  = _get_call_me()

    if player:
        player.write_log(f"[Reservaciones] tipo='{tipo}' params={list(parameters.keys())}")

    # ── VUELO ─────────────────────────────────────────────────────────────────
    if tipo in ("vuelo", "vuelos", "flight", "volar", "avion", "avión"):
        origen       = parameters.get("origen", "").strip()
        destino      = parameters.get("destino", "").strip()
        fecha_ida    = parameters.get("fecha_ida", "").strip()
        fecha_vuelta = parameters.get("fecha_vuelta", "").strip()
        pasajeros    = int(parameters.get("pasajeros", 1))
        cabina       = parameters.get("cabina", "economy").strip()

        # Validar campos mínimos
        if not origen or not destino:
            if speak:
                speak(
                    f"Pregúntale al usuario ({call_me}) que te diga origen y destino "
                    f"del vuelo. Con tu personalidad."
                )
            return "Faltan origen y destino del vuelo."

        if not fecha_ida:
            if speak:
                speak(
                    f"Pregúntale al usuario ({call_me}) para qué fecha quiere el vuelo "
                    f"de {origen} a {destino}. Con tu personalidad."
                )
            return "Falta la fecha del vuelo."

        result = _buscar_vuelos(origen, destino, fecha_ida, fecha_vuelta, pasajeros, cabina)

        tipo_viaje = "ida y vuelta" if fecha_vuelta else "solo ida"
        if speak:
            speak(
                f"Dile al usuario ({call_me}) que abriste Google Flights, Kayak y Skyscanner "
                f"con vuelos de {origen} a {destino} el {fecha_ida} ({tipo_viaje}, "
                f"{pasajeros} pasajero{'s' if pasajeros > 1 else ''}). "
                f"Que compare los precios y elija. Con tu personalidad, entusiasta."
            )
        return result

    # ── RESTAURANTE ───────────────────────────────────────────────────────────
    elif tipo in ("restaurante", "restaurant", "comer", "cenar", "comida", "cena"):
        nombre   = parameters.get("nombre", "").strip()
        telefono = parameters.get("telefono", "").strip()
        personas = int(parameters.get("personas", 2))
        fecha    = parameters.get("fecha", "").strip()
        hora     = parameters.get("hora", "").strip()
        ciudad   = parameters.get("ciudad", "").strip()
        notas    = parameters.get("notas", "").strip()

        if not nombre:
            if speak:
                speak(
                    f"Pregúntale al usuario ({call_me}) el nombre del restaurante "
                    f"donde quiere reservar. Con tu personalidad."
                )
            return "Falta el nombre del restaurante."

        result = _reservar_restaurante(nombre, telefono, personas, fecha, hora, ciudad, notas)

        if telefono:
            if speak:
                speak(
                    f"Dile al usuario ({call_me}) que abriste WhatsApp con el mensaje "
                    f"de reservación para {nombre} listo — solo tiene que enviarlo. "
                    f"Con tu personalidad."
                )
        else:
            if speak:
                speak(
                    f"Dile al usuario ({call_me}) que abriste Google Maps para encontrar "
                    f"el contacto de {nombre}, que cuando tenga el número te lo diga "
                    f"y mandas el WhatsApp. Con tu personalidad."
                )
        return result

    # ── HOTEL ─────────────────────────────────────────────────────────────────
    elif tipo in ("hotel", "hoteles", "hospedaje", "alojamiento", "airbnb"):
        ciudad    = parameters.get("ciudad", "").strip()
        check_in  = parameters.get("check_in", "").strip()
        check_out = parameters.get("check_out", "").strip()
        huespedes = int(parameters.get("huespedes", 1))
        estrellas = int(parameters.get("estrellas", 0))

        if not ciudad:
            if speak:
                speak(
                    f"Pregúntale al usuario ({call_me}) en qué ciudad busca hotel. "
                    f"Con tu personalidad."
                )
            return "Falta la ciudad del hotel."

        if not check_in or not check_out:
            if speak:
                speak(
                    f"Pregúntale al usuario ({call_me}) las fechas de entrada y salida "
                    f"del hotel en {ciudad}. Con tu personalidad."
                )
            return "Faltan fechas de check-in y check-out."

        result = _buscar_hoteles(ciudad, check_in, check_out, huespedes, estrellas)

        if speak:
            speak(
                f"Dile al usuario ({call_me}) que abriste Booking y Google Hotels "
                f"con hoteles en {ciudad} del {check_in} al {check_out} "
                f"para {huespedes} huésped{'es' if huespedes > 1 else ''}. "
                f"Que compare y elija. Con tu personalidad."
            )
        return result

    # ── TIPO NO RECONOCIDO → preguntar ───────────────────────────────────────
    else:
        if speak:
            speak(
                f"Pregúntale al usuario ({call_me}) qué tipo de reservación quiere: "
                f"vuelo, restaurante u hotel. Con tu personalidad."
            )
        return f"Tipo de reservación no reconocido: '{tipo}'"
