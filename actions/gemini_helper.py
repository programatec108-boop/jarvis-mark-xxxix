# gemini_helper.py - Helper IA para JARVIS Mark XXXIX
# Usa Gemini primero, si no hay cuota usa Ollama local (sin limite)
# Archivo: C:\Users\jose1\Mark-XXXIX\actions\gemini_helper.py

import json
import requests
from pathlib import Path

BASE_DIR    = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"

GEMINI_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.0-flash-lite",
    "gemini-2.0-flash",
    "gemini-flash-lite-latest",
    "gemini-flash-latest",
]

OLLAMA_MODEL   = "llama3.2"
OLLAMA_URL     = "http://localhost:11434/api/generate"


def _get_key():
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8")).get("gemini_api_key", "")
    except Exception:
        return ""


def _ask_gemini_http(prompt, key):
    """Intenta todos los modelos de Gemini via HTTP."""
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 8192}
    }
    for model in GEMINI_MODELS:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
        try:
            r    = requests.post(url, json=body, timeout=30)
            data = r.json()
            if r.status_code == 200:
                parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
                if parts:
                    print(f"[AI] Gemini ({model}) OK")
                    return parts[0].get("text", "")
            elif r.status_code == 429:
                print(f"[AI] Gemini {model}: cuota agotada, probando siguiente...")
                continue
            elif r.status_code == 404:
                continue
            else:
                msg = data.get("error", {}).get("message", "")
                print(f"[AI] Gemini {model} error {r.status_code}: {msg[:80]}")
                continue
        except Exception as e:
            print(f"[AI] Gemini {model} excepcion: {e}")
            continue
    return None


def _ask_ollama(prompt):
    """Usa Ollama local como fallback — sin cuota, sin internet."""
    try:
        r = requests.post(
            OLLAMA_URL,
            json={
                "model":  OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.7, "num_predict": 4096}
            },
            timeout=120
        )
        if r.status_code == 200:
            texto = r.json().get("response", "")
            if texto:
                print(f"[AI] Ollama ({OLLAMA_MODEL}) OK")
                return texto
    except requests.exceptions.ConnectionError:
        print("[AI] Ollama no esta corriendo. Iniciando...")
        try:
            import subprocess
            subprocess.Popen(
                ["ollama", "serve"],
                creationflags=subprocess.CREATE_NO_WINDOW
                if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
            )
            import time
            time.sleep(3)
            # Reintentar
            r = requests.post(
                OLLAMA_URL,
                json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
                timeout=120
            )
            if r.status_code == 200:
                texto = r.json().get("response", "")
                if texto:
                    print(f"[AI] Ollama ({OLLAMA_MODEL}) OK (reintento)")
                    return texto
        except Exception as e2:
            print(f"[AI] No pude iniciar Ollama: {e2}")
    except Exception as e:
        print(f"[AI] Ollama error: {e}")
    return None


def ask_gemini(prompt, model=None):
    """
    Pide respuesta a la IA.
    1. Intenta Gemini (todos los modelos)
    2. Si todos fallan por cuota → usa Ollama local
    """
    key = _get_key()

    # Intentar Gemini primero
    if key:
        resultado = _ask_gemini_http(prompt, key)
        if resultado:
            return resultado

    # Fallback: Ollama local
    print("[AI] Gemini sin cuota. Usando Ollama local...")
    resultado = _ask_ollama(prompt)
    if resultado:
        return resultado

    print("[AI] Todos los motores fallaron.")
    return None


def ask_gemini_json(prompt, model=None):
    """
    Pide respuesta JSON a la IA.
    Funciona con Gemini Y con Ollama.
    """
    full_prompt = (
        prompt +
        "\n\nIMPORTANTE: Responde SOLO con JSON valido. "
        "Sin markdown, sin backticks, sin texto adicional antes o despues. "
        "Solo el JSON puro empezando con { o [."
    )
    texto = ask_gemini(full_prompt, model)
    if not texto:
        return None

    try:
        texto = texto.strip()
        # Limpiar markdown si viene
        if "```" in texto:
            partes = texto.split("```")
            for parte in partes:
                parte = parte.strip()
                if parte.startswith("json"):
                    parte = parte[4:].strip()
                if parte.startswith("{") or parte.startswith("["):
                    texto = parte
                    break
        # Encontrar primer { o [
        inicio = -1
        for i, c in enumerate(texto):
            if c in "{[":
                inicio = i
                break
        if inicio > 0:
            texto = texto[inicio:]

        return json.loads(texto)
    except Exception as e:
        print(f"[AI] JSON parse error: {e}")
        print(f"[AI] Raw: {texto[:300]}")
        return None
