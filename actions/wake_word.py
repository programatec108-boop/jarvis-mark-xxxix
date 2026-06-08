# wake_word.py - JARVIS Mark XXXIX
# Deteccion local con SpeechRecognition - SIN interrupcion

import threading
import random
import time
import numpy as np

WAKE_RESPONSES = {
    "ironman": [
        "Para usted siempre, jefe. ¿Qué necesita?",
        "Aquí estoy, jefe. A sus órdenes.",
        "Siempre pendiente, jefe. Dígame.",
        "Con usted siempre, jefe. ¿Qué haremos?",
        "Despierto y listo, jefe. Adelante.",
    ],
    "formal": [
        "A sus órdenes. ¿En qué puedo asistirle?",
        "Presente. ¿Cómo puedo ayudarle?",
        "Quedo a su entera disposición. Dígame.",
        "Bienvenido. ¿En qué le sirvo?",
    ],
    "amigable": [
        "¡Ey! ¡Aquí estoy! ¿Qué necesitas?",
        "¡Presente! ¿Qué hay? Cuéntame.",
        "¡Hola! ¿Qué onda? Dime.",
        "¡Ya estoy! ¿En qué te ayudo?",
    ],
    "militar": [
        "¡Soldado JARVIS reportándose! ¿Cuál es la misión?",
        "¡A la orden! ¿Qué se le ofrece, comandante?",
        "¡Firme y listo! Reporte su solicitud.",
        "¡Presente! ¿Cuál es la orden?",
    ],
    "barrio": [
        "¡Órale wey! ¿Qué pedo? ¿En qué te aviento la mano?",
        "¡Ya estoy carnal! ¿Qué transita?",
        "¡Aquí mero! ¿Qué necesitas, mano?",
        "¡Nel, ya llegué! ¿Qué hay de nuevo?",
    ],
    "companero": [
        "¡Ey! ¡Aquí estoy! ¿Qué pasó?",
        "¡Ya! ¿Qué necesitas?",
        "¡Presente! No te me rajes, dime.",
        "¡Aquí! ¿Qué hay?",
    ],
}

_last_wake = [None]

WAKE_KEYWORDS = [
    "jarvis", "jarvi", "oye jarvis", "hey jarvis",
    "jar vis", "harvis", "charvis", "jarbis",
]


def _normalize(text):
    text = text.lower().strip()
    for k, v in {"á":"a","é":"e","í":"i","ó":"o","ú":"u","ü":"u","ñ":"n"}.items():
        text = text.replace(k, v)
    return text


def is_wake_word(text):
    n = _normalize(text)
    for kw in WAKE_KEYWORDS:
        if _normalize(kw) in n:
            return True
    return False


def get_wake_response(personality="ironman"):
    options = WAKE_RESPONSES.get(personality, WAKE_RESPONSES["ironman"])
    choices = [r for r in options if r != _last_wake[0]]
    r = random.choice(choices)
    _last_wake[0] = r
    return r


def _load_personality():
    try:
        import json
        from pathlib import Path
        pref = Path(__file__).resolve().parent.parent / "config" / "preferences.json"
        if pref.exists():
            d = json.loads(pref.read_text(encoding="utf-8"))
            idx = d.get("personality_idx", 0)
            names = ["ironman","formal","amigable","militar","barrio","militar","companero"]
            return names[idx] if idx < len(names) else "ironman"
    except Exception:
        pass
    return "ironman"


# ── Detector de aplauso ───────────────────────────────────────────────────────
class ClapDetector:
    def __init__(self, on_clap, threshold=800, min_gap=0.05, max_gap=0.8):
        self.on_clap    = on_clap
        self.threshold  = threshold
        self.min_gap    = min_gap
        self.max_gap    = max_gap
        self._last_peak = 0.0
        self._cooldown  = 0.0
        self._energies  = []
        self._lock      = threading.Lock()

    def process(self, audio_bytes):
        now = time.time()
        with self._lock:
            if now < self._cooldown:
                return
        try:
            data   = np.frombuffer(audio_bytes, dtype=np.int16).astype(float)
            energy = float(np.sqrt((data ** 2).mean()))
            self._energies.append(energy)
            if len(self._energies) > 60:
                self._energies.pop(0)
            avg = sum(self._energies) / len(self._energies)
            threshold = max(self.threshold, avg * 3.5)
        except Exception:
            return

        if energy > threshold:
            with self._lock:
                gap = now - self._last_peak
                if self._last_peak > 0 and self.min_gap <= gap <= self.max_gap:
                    self._cooldown  = now + 1.5
                    self._last_peak = 0.0
                    print("[WakeWord] ¡APLAUSO DETECTADO!")
                    threading.Thread(target=self.on_clap, daemon=True).start()
                else:
                    self._last_peak = now


# ── Detector de voz local ─────────────────────────────────────────────────────
class LocalVoiceDetector:
    def __init__(self, on_wake, sample_rate=16000):
        self.on_wake          = on_wake
        self.sample_rate      = sample_rate
        self._running         = False
        self._thread          = None
        self._jarvis_speaking = False
        self._cooldown        = 0.0

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread  = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        print("[WakeWord] Detector local iniciado.")

    def stop(self):
        self._running = False

    def set_speaking(self, speaking: bool):
        self._jarvis_speaking = speaking

    def _run(self):
        try:
            import speech_recognition as sr
            r   = sr.Recognizer()
            mic = sr.Microphone(sample_rate=self.sample_rate)

            with mic as source:
                print("[WakeWord] Calibrando micrófono...")
                r.adjust_for_ambient_noise(source, duration=1.5)
                r.energy_threshold = max(r.energy_threshold, 200)
                r.dynamic_energy_threshold = True
                print(f"[WakeWord] Umbral: {r.energy_threshold:.0f} — Listo.")

            while self._running:
                try:
                    now = time.time()
                    if now < self._cooldown:
                        time.sleep(0.05)
                        continue

                    # NO escuchar mientras JARVIS habla
                    if self._jarvis_speaking:
                        time.sleep(0.2)
                        continue

                    with mic as source:
                        try:
                            audio = r.listen(source, timeout=3, phrase_time_limit=3)
                        except sr.WaitTimeoutError:
                            continue

                    if self._jarvis_speaking:
                        continue

                    try:
                        texto = r.recognize_google(audio, language="es-MX").lower().strip()
                        print(f"[WakeWord] Escuché: '{texto}'")
                        if is_wake_word(texto):
                            print(f"[WakeWord] ¡JARVIS DETECTADO! '{texto}'")
                            self._cooldown = now + 2.0
                            threading.Thread(target=self.on_wake, daemon=True).start()
                    except sr.UnknownValueError:
                        pass
                    except sr.RequestError as e:
                        print(f"[WakeWord] Error Google Speech: {e}")
                        time.sleep(2)

                except Exception as e:
                    print(f"[WakeWord] Error loop: {e}")
                    time.sleep(0.5)

        except Exception as e:
            print(f"[WakeWord] Error iniciando: {e}")
            import traceback; traceback.print_exc()


# ── WakeWordDetector principal ────────────────────────────────────────────────
class WakeWordDetector:
    def __init__(self, speak_fn, on_wake_fn, on_sleep_fn, active_timeout=20):
        self.speak          = speak_fn
        self.on_wake        = on_wake_fn
        self.on_sleep       = on_sleep_fn
        self.active_timeout = active_timeout
        self.is_active      = False
        self._timer         = None
        self._lock          = threading.Lock()
        self._jarvis_speaking = False

        self.clap_detector = ClapDetector(
            on_clap   = self._clap_triggered,
            threshold = 800,
            min_gap   = 0.05,
            max_gap   = 0.8,
        )
        self.voice_detector = LocalVoiceDetector(
            on_wake = self._voice_triggered,
        )

    def start(self):
        self.voice_detector.start()
        print("[WakeWord] Sistema iniciado. Di 'Jarvis' o aplaude dos veces.")

    def stop(self):
        self.voice_detector.stop()

    def set_jarvis_speaking(self, speaking: bool):
        self._jarvis_speaking = speaking
        self.voice_detector.set_speaking(speaking)
        if speaking and self.is_active and self._timer:
            self._reset_timer()

    def process_audio(self, audio_bytes):
        if not self._jarvis_speaking:
            self.clap_detector.process(audio_bytes)

    def process_transcript(self, text):
        if self._jarvis_speaking:
            return False
        with self._lock:
            if not self.is_active:
                if is_wake_word(text):
                    self._activate("gemini")
                return False
            else:
                self._reset_timer()
                return True

    def _voice_triggered(self):
        with self._lock:
            if not self.is_active:
                self._activate("voice")

    def _clap_triggered(self):
        if self._jarvis_speaking:
            return
        with self._lock:
            if not self.is_active:
                self._activate("clap")

    def _activate(self, source):
        self.is_active = True
        self.on_wake()
        personality = _load_personality()
        response = get_wake_response(personality)
        threading.Thread(target=self.speak, args=(response,), daemon=True).start()
        self._reset_timer()
        print(f"[WakeWord] Activado: {source} — personalidad: {personality}")

    def _reset_timer(self):
        if self._timer:
            self._timer.cancel()
        self._timer        = threading.Timer(self.active_timeout, self._deactivate)
        self._timer.daemon = True
        self._timer.start()

    def _deactivate(self):
        with self._lock:
            self.is_active = False
        self.on_sleep()

    def force_activate(self):
        with self._lock:
            if not self.is_active:
                self._activate("force")

    def force_deactivate(self):
        with self._lock:
            if self._timer:
                self._timer.cancel()
            self.is_active = False
        self.on_sleep()
