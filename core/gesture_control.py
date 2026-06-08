# gesture_control.py - Control por gestos para JARVIS Mark XXXIX
# Archivo: C:\Users\jose1\Mark-XXXIX\core\gesture_control.py
#
# GESTOS BASE:
#   ✋ Mano abierta (5 dedos)  → activa/desactiva JARVIS
#   ✊ Puño cerrado (0 dedos)  → silencia/reactiva micrófono
#   👍 Pulgar arriba           → acción positiva / confirmar
#   🤙 Llamada (pulgar+meñique)→ acción personalizable desde Ajustes
#
# DEPENDENCIAS:
#   pip install mediapipe opencv-python
#
# ARQUITECTURA:
#   - Corre en hilo daemon separado — no bloquea la UI
#   - Solo activa la cámara cuando JARVIS está despierto
#   - Requiere confirmación de gesto (N frames consecutivos) para evitar falsos positivos
#   - Cooldown entre gestos para no disparar múltiples veces

import threading
import time
import json
import os
from pathlib import Path
from datetime import datetime


# ── Configuración por defecto ─────────────────────────────────────────────────

_DEFAULT_CONFIG = {
    "enabled":          False,       # desactivado por defecto — el usuario lo activa
    "camera_index":     0,           # índice de cámara (0 = predeterminada)
    "confirm_frames":   12,          # frames consecutivos para confirmar gesto
    "cooldown_secs":    2.0,         # segundos entre gestos
    "show_preview":     False,       # mostrar ventana de preview de la cámara
    "gestures": {
        "open_hand":    "toggle_wake",   # mano abierta → activar/desactivar
        "fist":         "toggle_mute",   # puño → silenciar/reactivar
        "thumbs_up":    "confirm",       # pulgar arriba → confirmar
        "call_sign":    "custom",        # 🤙 → acción personalizable
    },
    "custom_action":    "pon música",   # comando para el gesto custom
}


def _load_gesture_config() -> dict:
    try:
        appdata = os.environ.get("APPDATA", str(Path.home()))
        cfg_path = Path(appdata) / "JARVIS_Mark39" / "gesture_config.json"
        if cfg_path.exists():
            data = json.loads(cfg_path.read_text(encoding="utf-8"))
            merged = dict(_DEFAULT_CONFIG)
            merged.update(data)
            return merged
    except Exception as e:
        print(f"[Gesture] Error cargando config: {e}")
    return dict(_DEFAULT_CONFIG)


def _save_gesture_config(cfg: dict):
    try:
        appdata = os.environ.get("APPDATA", str(Path.home()))
        d = Path(appdata) / "JARVIS_Mark39"
        d.mkdir(parents=True, exist_ok=True)
        (d / "gesture_config.json").write_text(
            json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception as e:
        print(f"[Gesture] Error guardando config: {e}")


# ── Detector de gestos con MediaPipe ─────────────────────────────────────────

class GestureDetector:
    """
    Detecta gestos de la mano usando MediaPipe Hands.
    Corre en hilo daemon — no bloquea la UI.
    """

    # Nombre legible para logs
    GESTURE_NAMES = {
        "open_hand": "✋ Mano abierta",
        "fist":      "✊ Puño cerrado",
        "thumbs_up": "👍 Pulgar arriba",
        "call_sign": "🤙 Llamada",
        "none":      "Sin gesto",
    }

    def __init__(self,
                 on_wake_toggle,
                 on_mute_toggle,
                 on_confirm=None,
                 on_custom=None,
                 is_jarvis_active_fn=None):
        """
        on_wake_toggle    : callable — activa/desactiva JARVIS
        on_mute_toggle    : callable — silencia/reactiva micrófono
        on_confirm        : callable — acción de confirmación
        on_custom         : callable(str) — acción custom con el comando
        is_jarvis_active_fn : callable → bool — True si JARVIS está despierto
        """
        self._on_wake_toggle    = on_wake_toggle
        self._on_mute_toggle    = on_mute_toggle
        self._on_confirm        = on_confirm or (lambda: None)
        self._on_custom         = on_custom  or (lambda cmd: None)
        self._is_active         = is_jarvis_active_fn or (lambda: True)

        self._running           = False
        self._thread            = None
        self._config            = _load_gesture_config()
        self._last_gesture_time = 0.0
        self._gesture_buffer    = []   # últimos N frames de gesto detectado
        self._last_fired        = "none"

    # ── Control ───────────────────────────────────────────────────────────────

    def start(self):
        if not self._config.get("enabled", False):
            print("[Gesture] Desactivado en config — no iniciando")
            return
        if self._running:
            return
        self._running = True
        self._thread  = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        print("[Gesture] Detector de gestos iniciado")

    def stop(self):
        self._running = False
        print("[Gesture] Detector de gestos detenido")

    def reload_config(self):
        """Recarga config desde disco — llamar cuando el usuario guarda ajustes."""
        self._config = _load_gesture_config()
        print(f"[Gesture] Config recargada — enabled: {self._config.get('enabled')}")

    def enable(self, enabled: bool):
        self._config["enabled"] = enabled
        _save_gesture_config(self._config)
        if enabled and not self._running:
            self.start()
        elif not enabled:
            self.stop()

    # ── Clasificador de gestos ────────────────────────────────────────────────

    @staticmethod
    def _classify(hand_landmarks) -> str:
        """
        Clasifica la posición de la mano en un gesto.
        Usa las posiciones relativas de los landmarks de MediaPipe.

        Landmarks clave:
          4  = punta pulgar
          8  = punta índice
          12 = punta medio
          16 = punta anular
          20 = punta meñique
          3,6,10,14,18 = nudillos base de cada dedo
        """
        lm = hand_landmarks.landmark

        # Wrist y MCP (base de los dedos)
        wrist_y = lm[0].y

        # Detectar si cada dedo está extendido
        # Pulgar: comparar x (horizontal) — especial
        thumb_up   = lm[4].y < lm[3].y  # punta más arriba que base

        # Demás dedos: punta más arriba (y menor) que su nudillo
        index_up   = lm[8].y  < lm[6].y
        middle_up  = lm[12].y < lm[10].y
        ring_up    = lm[16].y < lm[14].y
        pinky_up   = lm[20].y < lm[18].y

        fingers = [index_up, middle_up, ring_up, pinky_up]
        count   = sum(fingers)

        # ── PUÑO: ningún dedo extendido ──────────────────────────────────────
        if count == 0 and not thumb_up:
            return "fist"

        # ── MANO ABIERTA: todos los dedos extendidos ─────────────────────────
        if count == 4 and thumb_up:
            return "open_hand"

        # ── PULGAR ARRIBA: solo pulgar, resto cerrado ─────────────────────────
        if thumb_up and count == 0:
            return "thumbs_up"

        # ── LLAMADA 🤙: pulgar + meñique extendidos, resto cerrado ───────────
        if thumb_up and pinky_up and not index_up and not middle_up and not ring_up:
            return "call_sign"

        return "none"

    # ── Ejecutar acción de gesto ──────────────────────────────────────────────

    def _fire(self, gesture: str):
        """Ejecuta la acción asociada al gesto detectado."""
        cfg      = self._config
        gestures = cfg.get("gestures", _DEFAULT_CONFIG["gestures"])
        action   = gestures.get(gesture, "none")

        print(f"[Gesture] 🔥 {self.GESTURE_NAMES.get(gesture, gesture)} → {action}")

        if action == "toggle_wake":
            threading.Thread(target=self._on_wake_toggle, daemon=True).start()
        elif action == "toggle_mute":
            threading.Thread(target=self._on_mute_toggle, daemon=True).start()
        elif action == "confirm":
            threading.Thread(target=self._on_confirm, daemon=True).start()
        elif action == "custom":
            cmd = cfg.get("custom_action", "")
            if cmd:
                threading.Thread(target=self._on_custom, args=(cmd,), daemon=True).start()

    # ── Loop principal ────────────────────────────────────────────────────────

    def _run(self):
        """Hilo principal de detección — requiere mediapipe y opencv."""
        try:
            import cv2
            import mediapipe as mp
        except ImportError as e:
            print(f"[Gesture] Dependencia faltante: {e}")
            print("[Gesture] Instala con: pip install mediapipe opencv-python")
            self._running = False
            return

        cfg     = self._config
        cam_idx = cfg.get("camera_index", 0)
        n_conf  = cfg.get("confirm_frames", 12)
        cooldown= cfg.get("cooldown_secs", 2.0)
        show    = cfg.get("show_preview", False)

        mp_hands   = mp.solutions.hands
        mp_drawing = mp.solutions.drawing_utils

        cap = cv2.VideoCapture(cam_idx)
        if not cap.isOpened():
            print(f"[Gesture] No se pudo abrir cámara {cam_idx}")
            self._running = False
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  320)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
        cap.set(cv2.CAP_PROP_FPS,          15)

        print(f"[Gesture] Cámara {cam_idx} abierta — resolución 320x240")

        with mp_hands.Hands(
            static_image_mode       = False,
            max_num_hands           = 1,
            min_detection_confidence= 0.7,
            min_tracking_confidence = 0.6,
        ) as hands:

            while self._running:
                # Solo procesar cuando JARVIS está despierto
                if not self._is_active():
                    time.sleep(0.2)
                    continue

                ok, frame = cap.read()
                if not ok:
                    time.sleep(0.05)
                    continue

                # Convertir a RGB para MediaPipe
                rgb    = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                result = hands.process(rgb)

                current_gesture = "none"
                if result.multi_hand_landmarks:
                    hand = result.multi_hand_landmarks[0]
                    current_gesture = self._classify(hand)

                    if show:
                        mp_drawing.draw_landmarks(
                            frame, hand, mp_hands.HAND_CONNECTIONS
                        )

                # Buffer de confirmación — requiere N frames seguidos del mismo gesto
                self._gesture_buffer.append(current_gesture)
                if len(self._gesture_buffer) > n_conf:
                    self._gesture_buffer.pop(0)

                # Confirmar si todos los frames del buffer son el mismo gesto
                if (len(self._gesture_buffer) == n_conf and
                        current_gesture != "none" and
                        all(g == current_gesture for g in self._gesture_buffer)):

                    now = time.time()
                    # Cooldown + no repetir el mismo gesto inmediatamente
                    if (now - self._last_gesture_time >= cooldown and
                            current_gesture != self._last_fired):
                        self._last_gesture_time = now
                        self._last_fired        = current_gesture
                        self._gesture_buffer    = []
                        self._fire(current_gesture)
                else:
                    # Resetear "último disparado" si la mano cambia de posición
                    if current_gesture == "none":
                        self._last_fired = "none"

                # Preview opcional
                if show:
                    label = self.GESTURE_NAMES.get(current_gesture, current_gesture)
                    cv2.putText(frame, label, (10, 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                    cv2.imshow("JARVIS Gesture Control", frame)
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        break

        cap.release()
        if show:
            cv2.destroyAllWindows()
        print("[Gesture] Cámara liberada")
        self._running = False
