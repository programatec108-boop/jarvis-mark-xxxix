# geo_location.py - Geolocalizacion REAL para JARVIS Mark XXXIX
# Archivo: C:\Users\jose1\Mark-XXXIX\actions\geo_location.py

import requests
import webbrowser
import threading
import time

# GPS real via Windows Location API
_cached_location = None
_cache_time = 0
CACHE_SECONDS = 30


def _get_gps_location():
    """Intenta obtener ubicacion GPS real via Windows."""
    global _cached_location, _cache_time

    # Si tenemos cache reciente la usamos
    if _cached_location and (time.time() - _cache_time) < CACHE_SECONDS:
        return _cached_location

    # Intentar GPS real via Windows.Devices.Geolocation
    try:
        import asyncio
        import winrt.windows.devices.geolocation as wdg

        async def _get():
            locator = wdg.Geolocator()
            locator.desired_accuracy = wdg.PositionAccuracy.HIGH
            pos = await locator.get_geoposition_async()
            coord = pos.coordinate
            return {
                "lat": coord.latitude,
                "lon": coord.longitude,
                "accuracy": coord.accuracy,
                "source": "GPS"
            }

        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(_get())
        loop.close()

        if result:
            _cached_location = result
            _cache_time = time.time()
            return result
    except Exception as e:
        print("[Geo] GPS error: " + str(e))

    # Fallback: IP con el mejor proveedor disponible
    try:
        # ipinfo da mejor precision que ip-api
        r = requests.get("https://ipinfo.io/json", timeout=6)
        data = r.json()
        loc_str = data.get("loc", "")
        if loc_str and "," in loc_str:
            lat, lon = loc_str.split(",")
            result = {
                "lat": float(lat),
                "lon": float(lon),
                "city": data.get("city", ""),
                "region": data.get("region", ""),
                "country": data.get("country", ""),
                "source": "IP"
            }
            _cached_location = result
            _cache_time = time.time()
            return result
    except Exception as e:
        print("[Geo] ipinfo error: " + str(e))

    # Ultimo fallback
    try:
        r = requests.get("http://ip-api.com/json/", timeout=5)
        data = r.json()
        if data.get("status") == "success":
            result = {
                "lat": data.get("lat"),
                "lon": data.get("lon"),
                "city": data.get("city", ""),
                "region": data.get("regionName", ""),
                "country": data.get("country", ""),
                "source": "IP-fallback"
            }
            _cached_location = result
            _cache_time = time.time()
            return result
    except Exception as e:
        print("[Geo] ip-api error: " + str(e))

    return None


def _get_address_from_coords(lat, lon):
    """Convierte coordenadas a direccion legible (reverse geocoding)."""
    try:
        headers = {"User-Agent": "JARVIS-XXXIX/1.0"}
        url = (
            "https://nominatim.openstreetmap.org/reverse"
            "?format=json"
            "&lat=" + str(lat) +
            "&lon=" + str(lon) +
            "&zoom=18&addressdetails=1"
        )
        r = requests.get(url, headers=headers, timeout=6)
        data = r.json()
        address = data.get("address", {})

        parts = []
        road    = address.get("road") or address.get("pedestrian") or address.get("footway")
        number  = address.get("house_number", "")
        suburb  = address.get("suburb") or address.get("neighbourhood") or address.get("quarter")
        city    = address.get("city") or address.get("town") or address.get("village") or address.get("municipality")
        state   = address.get("state")
        country = address.get("country")

        if road:
            parts.append(road + (" " + number if number else ""))
        if suburb:
            parts.append(suburb)
        if city:
            parts.append(city)
        if state:
            parts.append(state)
        if country:
            parts.append(country)

        return ", ".join(parts) if parts else data.get("display_name", "")
    except Exception as e:
        print("[Geo] Reverse geocode error: " + str(e))
        return None


def _open_maps_coords(lat, lon, zoom=17):
    url = "https://www.google.com/maps/@" + str(lat) + "," + str(lon) + "," + str(zoom) + "z"
    webbrowser.open(url)


def _open_maps_search(query):
    url = "https://www.google.com/maps/search/" + requests.utils.quote(query)
    webbrowser.open(url)


def _open_directions(origin, destination):
    o = requests.utils.quote(origin)
    d = requests.utils.quote(destination)
    url = "https://www.google.com/maps/dir/" + o + "/" + d
    webbrowser.open(url)


def geo_location(parameters, player=None, speak=None):
    action = parameters.get("action", "where_am_i").lower()

    if action in ("where_am_i", "coordinates"):
        loc = _get_gps_location()
        if not loc:
            return "No pude obtener tu ubicacion, jefe. Verifica tu conexion a internet."

        lat = loc["lat"]
        lon = loc["lon"]
        source = loc.get("source", "IP")

        # Reverse geocoding para direccion exacta
        address = _get_address_from_coords(lat, lon)

        # Abrir maps en la ubicacion real
        _open_maps_coords(lat, lon)

        if action == "coordinates":
            return "Coordenadas: " + str(round(lat, 6)) + ", " + str(round(lon, 6)) + ". " + (address or "")

        if address:
            result = "Estas en: " + address + "."
        else:
            result = "Estas en: " + loc.get("city", "") + ", " + loc.get("region", "") + ", " + loc.get("country", "") + "."

        if source == "IP":
            result += " (Ubicacion aproximada por IP, el GPS no esta disponible en este momento.)"

        if player:
            try:
                player.write_log("GEO: " + result)
            except Exception:
                pass

        return result

    elif action == "find_nearby":
        place_type = parameters.get("place_type", "")
        if not place_type:
            return "Dime que tipo de lugar buscas, jefe."

        loc = _get_gps_location()
        if loc:
            lat = loc["lat"]
            lon = loc["lon"]
            # Busqueda near con coordenadas exactas
            url = (
                "https://www.google.com/maps/search/" +
                requests.utils.quote(place_type) +
                "/@" + str(lat) + "," + str(lon) + ",15z"
            )
            webbrowser.open(url)
            return "Buscando " + place_type + " cerca de ti en Google Maps."
        else:
            _open_maps_search(place_type + " cerca de mi")
            return "Abriendo Google Maps para buscar " + place_type + "."

    elif action == "open_maps":
        query = parameters.get("query", "")
        if query:
            _open_maps_search(query)
            return "Abriendo Google Maps: " + query
        else:
            loc = _get_gps_location()
            if loc:
                _open_maps_coords(loc["lat"], loc["lon"])
                return "Abriendo Google Maps en tu ubicacion actual."
            return "No pude obtener tu ubicacion."

    elif action == "directions":
        destination = parameters.get("destination", "")
        if not destination:
            return "Dime a donde quieres ir, jefe."

        origin = parameters.get("origin", "")
        if not origin:
            loc = _get_gps_location()
            if loc:
                lat = loc["lat"]
                lon = loc["lon"]
                origin = str(lat) + "," + str(lon)
            else:
                origin = "mi ubicacion actual"

        _open_directions(origin, destination)
        return "Abriendo ruta hacia " + destination + " en Google Maps."

    else:
        return "Accion no reconocida: " + action
