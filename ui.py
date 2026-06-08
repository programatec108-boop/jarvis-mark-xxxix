from __future__ import annotations

import json
import math
import os
import platform
import random
import subprocess
import sys
import threading
import time
from pathlib import Path

import psutil

from PyQt6.QtCore import (
    QEasingCurve, QMimeData, QObject, QPointF, QRectF, QSize, Qt,
    QTimer, QUrl, pyqtSignal,
)
from PyQt6.QtGui import (
    QBrush, QColor, QDragEnterEvent, QDropEvent, QFont, QFontDatabase,
    QKeySequence, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap,
    QRadialGradient, QShortcut,
)
from PyQt6.QtWidgets import QGraphicsOpacityEffect
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QFrame, QHBoxLayout,
    QLabel, QLineEdit, QMainWindow, QPushButton, QScrollArea, QSizePolicy,
    QSlider, QSpinBox, QStackedWidget, QTextEdit, QVBoxLayout, QWidget,
    QProgressBar, QGridLayout,
)
from PyQt6.QtCore import QPropertyAnimation, QEasingCurve

def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent

BASE_DIR    = _base_dir()
CONFIG_DIR  = BASE_DIR / "config"
API_FILE    = CONFIG_DIR / "api_keys.json"
PREF_FILE   = CONFIG_DIR / "preferences.json"

_DEFAULT_W, _DEFAULT_H = 1140, 720
_MIN_W,     _MIN_H     = 960, 620
_LEFT_W  = 178          # más ancho — métricas más legibles
_RIGHT_W = 360          # más ancho — log y shortcuts con más espacio
_OS = platform.system()


# ── Colores ───────────────────────────────────────────────────────────────────
class C:
    BG        = "#00060a"
    PANEL     = "#010d14"
    PANEL2    = "#010f18"
    PANEL3    = "#020e18"          # nuevo — para secciones internas
    BORDER    = "#0d3347"
    BORDER_B  = "#1a5c7a"
    BORDER_A  = "#0f4060"
    BORDER_H  = "#00d4ff22"       # nuevo — highlight sutil
    PRI       = "#00d4ff"
    PRI_DIM   = "#007a99"
    PRI_GHO   = "#001f2e"
    PRI_GLOW  = "#00d4ff18"       # nuevo — fondo con brillo
    ACC       = "#ff6b00"
    ACC2      = "#ffcc00"
    GREEN     = "#00ff88"
    GREEN_D   = "#00aa55"
    GREEN_GHO = "#001a0d"         # nuevo
    RED       = "#ff3355"
    RED_GHO   = "#1a0008"         # nuevo
    MUTED_C   = "#ff3366"
    TEXT      = "#8ffcff"
    TEXT_DIM  = "#3a8a9a"
    TEXT_MED  = "#5ab8cc"
    TEXT_FADE = "#1e5068"         # nuevo — muy tenue
    WHITE     = "#d8f8ff"
    DARK      = "#000d14"
    DARKER    = "#000810"         # nuevo — más oscuro para headers
    BAR_BG    = "#011520"
    ORANGE    = "#ff9500"
    ORANGE_D  = "#cc7000"         # nuevo
    PURPLE    = "#cc44ff"
    TEAL      = "#00aacc"         # nuevo — alternativa al cyan


def qcol(h: str, a: int = 255) -> QColor:
    c = QColor(h); c.setAlpha(a); return c


class DarkCombo(QWidget):
    """ComboBox oscuro que siempre se ve bien en cualquier OS."""
    currentIndexChanged = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items: list[str] = []
        self._current = 0
        self._open = False
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0,0,0,0)
        lay.setSpacing(0)
        # Boton principal
        self._btn = QPushButton()
        self._btn.setFixedHeight(28)
        self._btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn.setStyleSheet(
            f"QPushButton{{background:#000d14;color:#d8f8ff;border:1px solid #0d3347;"
            f"border-radius:3px;padding:2px 8px;font-family:'Courier New';font-size:9pt;text-align:left;}}"
            f"QPushButton:hover{{border:1px solid #1a5c7a;}}"
        )
        self._btn.clicked.connect(self._toggle)
        lay.addWidget(self._btn)
        # Panel desplegable
        self._popup = QWidget(self)
        self._popup.setStyleSheet(
            f"QWidget{{background:#000d14;border:1px solid #1a5c7a;border-radius:3px;}}"
        )
        self._popup_lay = QVBoxLayout(self._popup)
        self._popup_lay.setContentsMargins(2,2,2,2)
        self._popup_lay.setSpacing(1)
        self._popup.hide()

    def addItems(self, items: list):
        self._items = items
        for i,item in enumerate(items):
            btn = QPushButton(item)
            btn.setFixedHeight(24)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                f"QPushButton{{background:transparent;color:#8ffcff;border:none;"
                f"padding:2px 8px;font-family:'Courier New';font-size:9pt;text-align:left;}}"
                f"QPushButton:hover{{background:#001f2e;color:#00d4ff;}}"
            )
            btn.clicked.connect(lambda _,idx=i: self._select(idx))
            self._popup_lay.addWidget(btn)
        if items:
            self._btn.setText("▾  " + items[0])

    def _toggle(self):
        if self._popup.isVisible():
            self._popup.hide()
        else:
            self._popup.setFixedWidth(self.width())
            item_h = 24 * len(self._items) + 6
            self._popup.setFixedHeight(min(item_h, 160))
            # Posicionar debajo del boton
            pos = self.mapToGlobal(self._btn.geometry().bottomLeft())
            self._popup.setParent(self.window())
            self._popup.move(self.window().mapFromGlobal(pos))
            self._popup.setFixedWidth(self.width())
            self._popup.show()
            self._popup.raise_()

    def _select(self, idx: int):
        self._current = idx
        self._btn.setText("▾  " + self._items[idx])
        self._popup.hide()
        self.currentIndexChanged.emit(idx)

    def currentIndex(self) -> int: return self._current
    def currentText(self) -> str:
        return self._items[self._current] if self._items else ""
    def setCurrentIndex(self, idx: int):
        if 0 <= idx < len(self._items):
            self._current = idx
            self._btn.setText("▾  " + self._items[idx])



# ── Preferencias ──────────────────────────────────────────────────────────────
_DEFAULT_PREFS = {
    "user_name":      "Jose Antonio",
    "call_me":        "jefe",
    "city":           "México",
    "personality":    "ironman",
    "clock_24h":      True,
    "voice_speed":    1.0,
    "active_timeout": 20,
    "ollama_fallback": True,
    "debug_mode":     False,
    "memory_enabled": True,
    "theme_color":    "cyan",
    "shortcuts":      ["💡 Luces","🎵 Música","🗓 Reservaciones"],
    "routines":       [
        {
            "time":  "07:00",
            "days":  "L-V",
            "tasks": [
                "da los buenos días con tu personalidad y dime el clima de hoy",
                "lee las 3 noticias más importantes del día",
                "enciende las luces de la sala",
            ]
        },
        {
            "time":  "22:00",
            "days":  "Todos",
            "tasks": [
                "da las buenas noches con tu personalidad y un resumen breve del día",
                "activa el modo nocturno ahora",
            ]
        },
    ],
    "notifications":  {"sound":True,"wake_sound":True,"error_sound":True},
}

def load_prefs() -> dict:
    try:
        if PREF_FILE.exists():
            d = json.loads(PREF_FILE.read_text(encoding="utf-8"))
            merged = dict(_DEFAULT_PREFS)
            merged.update(d)
            return merged
    except Exception:
        pass
    return dict(_DEFAULT_PREFS)

def save_prefs(prefs: dict):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        PREF_FILE.write_text(json.dumps(prefs, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"[Prefs] Error: {e}")

_prefs = load_prefs()


# ── Métricas del sistema ──────────────────────────────────────────────────────
class _SysMetrics:
    def __init__(self):
        self.cpu = self.mem = self.net = 0.0
        self.gpu = self.tmp = -1.0
        self._lock = threading.Lock()
        self._last_net = psutil.net_io_counters()
        self._last_net_t = time.time()
        self._running = True
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        while self._running:
            try: self._update()
            except Exception: pass
            time.sleep(1.5)

    def _update(self):
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory().percent
        nc  = psutil.net_io_counters()
        now = time.time()
        dt  = now - self._last_net_t
        net = ((nc.bytes_sent - self._last_net.bytes_sent) + (nc.bytes_recv - self._last_net.bytes_recv)) / dt / (1024*1024) if dt > 0 else 0.0
        self._last_net = nc; self._last_net_t = now
        gpu = self._get_gpu()
        tmp = self._get_temp()
        with self._lock:
            self.cpu = cpu; self.mem = mem; self.net = net; self.gpu = gpu; self.tmp = tmp

    def _get_gpu(self) -> float:
        try:
            r = subprocess.run(["nvidia-smi","--query-gpu=utilization.gpu","--format=csv,noheader,nounits"],
                capture_output=True,text=True,timeout=2)
            if r.returncode==0:
                vals=[float(v.strip()) for v in r.stdout.strip().split("\n") if v.strip()]
                if vals: return sum(vals)/len(vals)
        except Exception: pass
        return -1.0

    def _get_temp(self) -> float:
        try:
            temps = psutil.sensors_temperatures()
            for name in ["coretemp","k10temp","cpu_thermal","acpitz"]:
                if name in temps and temps[name]:
                    return temps[name][0].current
        except Exception: pass
        if _OS == "Windows":
            try:
                r = subprocess.run(["powershell","-Command",
                    "(Get-WmiObject MSAcpi_ThermalZoneTemperature -Namespace root/wmi).CurrentTemperature"],
                    capture_output=True,text=True,timeout=3)
                if r.returncode==0 and r.stdout.strip():
                    return (float(r.stdout.strip().split("\n")[0])/10.0)-273.15
            except Exception: pass
        return -1.0

    def snapshot(self) -> dict:
        with self._lock:
            return {"cpu":self.cpu,"mem":self.mem,"net":self.net,"gpu":self.gpu,"tmp":self.tmp}

_metrics = _SysMetrics()


# ── HUD Canvas ────────────────────────────────────────────────────────────────
class HudCanvas(QWidget):
    def __init__(self, face_path: str, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.setMinimumSize(300, 300)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Estado
        self.muted = False; self.speaking = False; self.state = "INITIALISING"

        # Animación core
        self._tick = 0; self._scale = 1.0; self._tgt_scale = 1.0
        self._halo = 55.0; self._tgt_halo = 55.0; self._last_t = time.time()
        self._blink = True; self._blink_tick = 0

        # Anillos giratorios — 5 capas: (velocidad, fracción radio, grosor, arco, hueco, color)
        self._rings = [
            {"ang": 0.0,   "spd": 0.55,  "spd_s": 1.8,  "r": 0.485, "w": 2.5, "arc": 110, "gap": 70,  "col": C.PRI},
            {"ang": 120.0, "spd": -0.38, "spd_s": -1.4, "r": 0.415, "w": 1.8, "arc": 80,  "gap": 52,  "col": C.PRI},
            {"ang": 240.0, "spd": 0.90,  "spd_s": 2.5,  "r": 0.345, "w": 1.2, "arc": 55,  "gap": 40,  "col": C.TEAL},
            {"ang": 60.0,  "spd": -1.10, "spd_s": -3.0, "r": 0.275, "w": 1.0, "arc": 35,  "gap": 28,  "col": C.ACC2},
            {"ang": 300.0, "spd": 0.65,  "spd_s": 1.5,  "r": 0.210, "w": 0.8, "arc": 28,  "gap": 22,  "col": C.PURPLE},
        ]

        # Escáneres (arcos girando solos)
        self._scan  = 0.0;   self._scan2 = 180.0
        self._scan3 = 90.0;  self._scan4 = 270.0

        # Pulsos — ondas expansivas desde el centro
        self._pulses: list[float] = [0.0, 55.0, 110.0]

        # Partículas
        self._particles: list[list[float]] = []

        # Hexágonos decorativos girando
        self._hex_ang = 0.0

        # Datos del sistema para mostrar en HUD
        self._hud_metrics = {"cpu": 0, "mem": 0, "net": "0KB/s"}

        # Efecto de glitch ocasional
        self._glitch = 0.0

        # Face
        self._face_px: QPixmap | None = None
        self._load_face(face_path)

        # Timer a 60fps
        self._tmr = QTimer(self); self._tmr.timeout.connect(self._step); self._tmr.start(16)

    # ── Carga de foto de perfil ───────────────────────────────────────────────

    def _load_face(self, path: str):
        try:
            from PIL import Image, ImageDraw
            import io
            img = Image.open(path).convert("RGBA")
            sz = min(img.size); img = img.resize((sz, sz), Image.LANCZOS)
            mk = Image.new("L", (sz, sz), 0)
            ImageDraw.Draw(mk).ellipse((2, 2, sz-2, sz-2), fill=255)
            img.putalpha(mk)
            buf = io.BytesIO(); img.save(buf, format="PNG")
            px = QPixmap(); px.loadFromData(buf.getvalue())
            self._face_px = px
        except Exception:
            self._face_px = None

    # ── Actualizar métricas del sistema ──────────────────────────────────────

    def update_metrics(self, cpu: int, mem: int, net: str):
        self._hud_metrics = {"cpu": cpu, "mem": mem, "net": net}

    # ── Loop de animación ─────────────────────────────────────────────────────

    def _step(self):
        self._tick += 1
        now = time.time()
        spk = self.speaking

        # Actualizar halo y escala
        if now - self._last_t > (0.10 if spk else 0.45):
            if spk:
                self._tgt_scale = random.uniform(1.07, 1.16)
                self._tgt_halo  = random.uniform(150, 200)
            elif self.muted:
                self._tgt_scale = random.uniform(0.997, 1.002)
                self._tgt_halo  = random.uniform(12, 25)
            else:
                self._tgt_scale = random.uniform(1.001, 1.009)
                self._tgt_halo  = random.uniform(50, 72)
            self._last_t = now
        ease = 0.40 if spk else 0.14
        self._scale += (self._tgt_scale - self._scale) * ease
        self._halo  += (self._tgt_halo  - self._halo)  * ease

        # Girar anillos
        for rg in self._rings:
            spd = rg["spd_s"] if spk else rg["spd"]
            rg["ang"] = (rg["ang"] + spd) % 360

        # Escáneres
        self._scan  = (self._scan  + (3.5 if spk else 1.4)) % 360
        self._scan2 = (self._scan2 + (-2.2 if spk else -0.8)) % 360
        self._scan3 = (self._scan3 + (1.8 if spk else 0.6)) % 360
        self._scan4 = (self._scan4 + (-1.2 if spk else -0.45)) % 360

        # Hexágono
        self._hex_ang = (self._hex_ang + (0.6 if spk else 0.2)) % 360

        # Pulsos
        fw = min(self.width(), self.height()); lim = fw * 0.76
        pspd = 4.8 if spk else 2.2
        self._pulses = [r + pspd for r in self._pulses if r + pspd < lim]
        max_p = 4 if spk else 3
        prob  = 0.09 if spk else 0.028
        if len(self._pulses) < max_p and random.random() < prob:
            self._pulses.append(0.0)

        # Partículas
        if spk and random.random() < 0.32:
            cx, cy = self.width() / 2, self.height() / 2
            ang = random.uniform(0, 2 * math.pi)
            r_s = fw * random.uniform(0.18, 0.30)
            self._particles.append([
                cx + math.cos(ang) * r_s,
                cy + math.sin(ang) * r_s,
                math.cos(ang) * random.uniform(0.8, 2.8),
                math.sin(ang) * random.uniform(0.8, 2.8) - 0.3,
                1.0,
                random.choice([C.PRI, C.ACC2, C.TEAL, C.PURPLE]),
            ])
        self._particles = [
            [p[0]+p[2], p[1]+p[3], p[2]*0.96, p[3]*0.96, p[4]-0.025, p[5]]
            for p in self._particles if p[4] > 0
        ]

        # Glitch ocasional
        if random.random() < 0.004:
            self._glitch = random.uniform(0.3, 1.0)
        elif self._glitch > 0:
            self._glitch = max(0.0, self._glitch - 0.08)

        # Parpadeo
        self._blink_tick += 1
        if self._blink_tick >= 36:
            self._blink = not self._blink; self._blink_tick = 0

        self.update()

    # ── Eventos de mouse ──────────────────────────────────────────────────────

    def mouseDoubleClickEvent(self, e):
        parent = self.parent()
        while parent and not isinstance(parent, QMainWindow):
            parent = parent.parent() if hasattr(parent, 'parent') else None
        if parent and hasattr(parent, '_toggle_mini_mode') and getattr(parent, '_mini_mode', False):
            parent._toggle_mini_mode()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            parent = self.parent()
            while parent and not isinstance(parent, QMainWindow):
                parent = parent.parent() if hasattr(parent, 'parent') else None
            if parent and getattr(parent, '_mini_mode', False):
                self._drag_start = e.globalPosition().toPoint()
                self._win_start  = parent.pos()

    def mouseMoveEvent(self, e):
        if e.buttons() == Qt.MouseButton.LeftButton and hasattr(self, '_drag_start'):
            parent = self.parent()
            while parent and not isinstance(parent, QMainWindow):
                parent = parent.parent() if hasattr(parent, 'parent') else None
            if parent and getattr(parent, '_mini_mode', False):
                delta = e.globalPosition().toPoint() - self._drag_start
                parent.move(self._win_start + delta)

    # ── Helpers de dibujo ────────────────────────────────────────────────────

    def _draw_hexagon(self, p: QPainter, cx: float, cy: float,
                      r: float, angle_deg: float, color: QColor, width: float = 1.0):
        """Dibuja un hexágono centrado en (cx,cy) con radio r y rotación angle_deg."""
        pts = []
        for i in range(6):
            a = math.radians(angle_deg + i * 60)
            pts.append(QPointF(cx + r * math.cos(a), cy + r * math.sin(a)))
        p.setPen(QPen(color, width))
        p.setBrush(Qt.BrushStyle.NoBrush)
        for i in range(6):
            p.drawLine(pts[i], pts[(i+1) % 6])

    def _draw_arc_glow(self, p: QPainter, cx: float, cy: float,
                       r: float, start: float, span: float,
                       color_hex: str, alpha: int, width: float):
        """Dibuja un arco con doble capa (glow + línea) para efecto neon."""
        rect = QRectF(cx - r, cy - r, r * 2, r * 2)
        # Glow exterior
        glow_col = qcol(color_hex, max(0, alpha // 3))
        p.setPen(QPen(glow_col, width * 2.8))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawArc(rect, int(start * 16), int(span * 16))
        # Línea principal
        p.setPen(QPen(qcol(color_hex, alpha), width))
        p.drawArc(rect, int(start * 16), int(span * 16))

    # ── Paint principal ───────────────────────────────────────────────────────

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        cx, cy = W / 2, H / 2
        fw = min(W, H)
        spk = self.speaking
        halo = self._halo
        pri_col = C.MUTED_C if self.muted else C.PRI

        # ── Fondo con gradiente radial ────────────────────────────────────────
        p.fillRect(self.rect(), qcol(C.BG))
        grad = QRadialGradient(QPointF(cx, cy), fw * 0.55)
        a_grd = max(0, min(40, int(halo * 0.22)))
        grad.setColorAt(0.0, qcol(pri_col, a_grd))
        grad.setColorAt(1.0, qcol(C.BG, 0))
        p.fillRect(self.rect(), QBrush(grad))

        # ── Grid de puntos ────────────────────────────────────────────────────
        p.setPen(QPen(qcol(C.PRI_GHO), 1))
        for x in range(0, W, 52):
            for y in range(0, H, 52):
                p.drawPoint(x, y)

        # ── Líneas de esquina (brackets Iron Man) ─────────────────────────────
        bl = 30
        hl, hr = cx - fw * 0.50, cx + fw * 0.50
        ht, hb = cy - fw * 0.50, cy + fw * 0.50
        bc = qcol(C.PRI, 200)
        p.setPen(QPen(bc, 2))
        for bx, by, dx, dy in [(hl,ht,1,1),(hr,ht,-1,1),(hl,hb,1,-1),(hr,hb,-1,-1)]:
            p.drawLine(QPointF(bx, by), QPointF(bx + dx*bl, by))
            p.drawLine(QPointF(bx, by), QPointF(bx, by + dy*bl))
        # Pequeños cuadrados en las esquinas
        sq = 4
        p.setBrush(QBrush(qcol(C.PRI, 160)))
        p.setPen(Qt.PenStyle.NoPen)
        for bx, by in [(hl,ht),(hr,ht),(hl,hb),(hr,hb)]:
            p.drawRect(QRectF(bx-sq/2, by-sq/2, sq, sq))

        # ── Líneas de cruceta ─────────────────────────────────────────────────
        ch_r = fw * 0.52; gap_h = fw * 0.17
        p.setPen(QPen(qcol(pri_col, int(halo * 0.45)), 1))
        p.drawLine(QPointF(cx-ch_r, cy), QPointF(cx-gap_h, cy))
        p.drawLine(QPointF(cx+gap_h, cy), QPointF(cx+ch_r, cy))
        p.drawLine(QPointF(cx, cy-ch_r), QPointF(cx, cy-gap_h))
        p.drawLine(QPointF(cx, cy+gap_h), QPointF(cx, cy+ch_r))
        # Puntos en los extremos de la cruceta
        dot_r = 3
        p.setBrush(QBrush(qcol(pri_col, 180)))
        p.setPen(Qt.PenStyle.NoPen)
        for px2, py2 in [(cx-ch_r, cy),(cx+ch_r, cy),(cx, cy-ch_r),(cx, cy+ch_r)]:
            p.drawEllipse(QPointF(px2, py2), dot_r, dot_r)

        # ── Hexágonos giratorios ──────────────────────────────────────────────
        hex_a = max(0, int(halo * 0.35))
        self._draw_hexagon(p, cx, cy, fw*0.52, self._hex_ang,
                           qcol(C.BORDER_A, hex_a), 1.0)
        self._draw_hexagon(p, cx, cy, fw*0.52, self._hex_ang + 30,
                           qcol(C.PRI, hex_a // 2), 0.6)

        # ── Pulsos expansivos ─────────────────────────────────────────────────
        for pr in self._pulses:
            a = max(0, int(200 * (1.0 - pr / (fw * 0.76))))
            p.setPen(QPen(qcol(pri_col, a), 1.2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QRectF(cx-pr, cy-pr, pr*2, pr*2))

        # ── Halo de glow suave alrededor del centro ───────────────────────────
        r_face = fw * 0.31
        for i in range(8):
            r = r_face * (1.75 - i * 0.09)
            frc = 1.0 - i / 8
            a = max(0, min(255, int(halo * 0.09 * frc)))
            p.setPen(QPen(qcol(pri_col, a), 1.2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QRectF(cx-r, cy-r, r*2, r*2))

        # ── Anillos giratorios segmentados (5 capas) ──────────────────────────
        for rg in self._rings:
            ring_r = fw * rg["r"]
            base   = rg["ang"]
            a_val  = max(0, min(255, int(halo * 0.95)))
            rect   = QRectF(cx-ring_r, cy-ring_r, ring_r*2, ring_r*2)
            arc_l  = rg["arc"] + (rg["arc"] * 0.3 if spk else 0)
            gap    = rg["gap"]
            angle  = base
            while angle < base + 360:
                self._draw_arc_glow(p, cx, cy, ring_r,
                                    angle, arc_l, rg["col"], a_val, rg["w"])
                angle += arc_l + gap

        # ── Escáneres neon ────────────────────────────────────────────────────
        sa   = min(255, int(halo * 1.6))
        ex1  = 80 if spk else 50
        ex2  = 45 if spk else 28
        sr1, sr2 = fw * 0.505, fw * 0.425
        self._draw_arc_glow(p, cx, cy, sr1, self._scan,  ex1, pri_col, sa,   2.5)
        self._draw_arc_glow(p, cx, cy, sr1, self._scan2, ex2, C.ACC,   sa//2, 1.5)
        self._draw_arc_glow(p, cx, cy, sr2, self._scan3, ex2, C.ACC2,  sa//3, 1.2)
        self._draw_arc_glow(p, cx, cy, sr2, self._scan4, ex1//2, C.PURPLE, sa//4, 1.0)

        # ── Escala graduada (ticks) ───────────────────────────────────────────
        t_out, t_in = fw * 0.500, fw * 0.478
        p.setPen(QPen(qcol(C.PRI, 130), 1))
        for deg in range(0, 360, 10):
            rad = math.radians(deg)
            inn = t_in if deg % 30 == 0 else (t_in + 5 if deg % 10 == 0 else t_in + 8)
            p.drawLine(
                QPointF(cx + t_out * math.cos(rad), cy - t_out * math.sin(rad)),
                QPointF(cx + inn  * math.cos(rad), cy - inn  * math.sin(rad))
            )

        # ── Datos del sistema en el borde del HUD ────────────────────────────
        p.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        cpu_a = max(0, min(255, int(halo * 1.2)))
        m = self._hud_metrics
        data_items = [
            (cx - fw*0.46, cy - 10, f"CPU\n{m['cpu']}%",  C.PRI),
            (cx + fw*0.36, cy - 10, f"MEM\n{m['mem']}%",  C.ACC2),
            (cx - fw*0.46, cy + 4,  f"NET\n{m['net']}",   C.GREEN),
        ]
        for dx, dy, txt, col in data_items:
            p.setPen(QPen(qcol(col, cpu_a), 1))
            p.drawText(QRectF(dx, dy, 50, 26), Qt.AlignmentFlag.AlignLeft, txt)

        # ── Cara / Orbe central ───────────────────────────────────────────────
        if self._face_px:
            fsz = int(fw * 0.60 * self._scale)
            scaled = self._face_px.scaled(
                fsz, fsz,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            p.drawPixmap(int(cx - fsz/2), int(cy - fsz/2), scaled)
        else:
            # Orbe de energía con capas
            orb_r = int(fw * 0.26 * self._scale)
            oc = (180, 0, 40) if self.muted else (0, 55, 105)
            for i in range(10, 0, -1):
                r2 = int(orb_r * i / 10)
                frc = i / 10
                a = max(0, min(255, int(halo * 1.15 * frc)))
                p.setBrush(QBrush(QColor(int(oc[0]*frc), int(oc[1]*frc), int(oc[2]*frc), a)))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(QRectF(cx-r2, cy-r2, r2*2, r2*2))
            # Reactor arc interno (hexágono pequeño)
            self._draw_hexagon(p, cx, cy, fw*0.08, self._hex_ang * 2,
                               qcol(C.PRI, min(255, int(halo * 2.5))), 1.5)
            p.setPen(QPen(qcol(C.PRI, min(255, int(halo * 2.2))), 1))
            p.setFont(QFont("Courier New", 12, QFont.Weight.Bold))
            p.drawText(QRectF(cx-80, cy-14, 160, 28),
                       Qt.AlignmentFlag.AlignCenter, "J.A.R.V.I.S")

        # ── Efecto de glitch ──────────────────────────────────────────────────
        if self._glitch > 0.1:
            ga = int(self._glitch * 60)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(qcol(C.PRI, ga)))
            gw = random.randint(60, 200)
            gh = random.randint(1, 3)
            gx = random.randint(0, max(1, W - gw))
            gy = random.randint(int(cy - fw*0.4), int(cy + fw*0.4))
            p.drawRect(QRectF(gx, gy, gw, gh))

        # ── Partículas de energía ─────────────────────────────────────────────
        for pt in self._particles:
            a = max(0, min(255, int(pt[4] * 255)))
            p.setPen(Qt.PenStyle.NoPen)
            sz = 2.0 + pt[4] * 1.5
            p.setBrush(QBrush(qcol(pt[5], a)))
            p.drawEllipse(QPointF(pt[0], pt[1]), sz, sz)

        # ── Estado y ecualizador ──────────────────────────────────────────────
        sy = cy + fw * 0.41
        if self.muted:
            txt, col = "⊘  SILENCIADO",   qcol(C.MUTED_C)
        elif spk:
            txt, col = "●  HABLANDO",     qcol(C.ACC)
        elif self.state in ("THINKING", "PROCESSING"):
            sym = "◈" if self._blink else "◇"
            txt, col = f"{sym}  PROCESANDO", qcol(C.ACC2)
        elif self.state == "LISTENING":
            sym = "●" if self._blink else "○"
            txt, col = f"{sym}  ESCUCHANDO", qcol(C.GREEN)
        elif self.state == "MUTED":
            txt, col = "⊘  SILENCIADO",   qcol(C.MUTED_C)
        else:
            sym = "◆" if self._blink else "◇"
            txt, col = f"{sym}  EN ESPERA",  qcol(C.PRI)

        # Fondo semitransparente detrás del texto de estado
        tw = 180; th = 22
        p.setBrush(QBrush(qcol(C.BG, 140)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(QRectF(cx-tw/2, sy-2, tw, th), 4, 4)

        p.setPen(QPen(col, 1))
        p.setFont(QFont("Courier New", 10, QFont.Weight.Bold))
        p.drawText(QRectF(0, sy, W, 22), Qt.AlignmentFlag.AlignCenter, txt)

        # Ecualizador de voz
        wy = sy + 28; N = 40; bw = 7; wx0 = (W - N*bw) / 2
        for i in range(N):
            if self.muted:
                hgt, cl = 2, qcol(C.MUTED_C, 120)
            elif spk:
                hgt = random.randint(2, 22)
                cl = (qcol(C.PRI, 230) if hgt > 14
                      else qcol(C.TEAL, 180) if hgt > 8
                      else qcol(C.PRI_DIM, 140))
            else:
                hgt = int(2 + 2.5 * abs(math.sin(self._tick * 0.08 + i * 0.55)))
                cl  = qcol(C.BORDER_B, 160)
            p.fillRect(QRectF(wx0 + i*bw, wy + 22 - hgt, bw-1, hgt), cl)


# ── MetricBar ─────────────────────────────────────────────────────────────────
class MetricBar(QWidget):
    def __init__(self, label: str, color: str = C.PRI, parent=None):
        super().__init__(parent)
        self._label = label; self._color = color; self._value = 0.0; self._text = "--"
        self.setFixedHeight(44); self.setMinimumWidth(80)

    def set_value(self, pct: float, text: str):
        self._value = max(0.0,min(100.0,pct)); self._text = text; self.update()

    def paintEvent(self,_):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W,H = self.width(),self.height()

        # Fondo con borde sutil
        p.setBrush(QBrush(qcol(C.PANEL2)))
        p.setPen(QPen(qcol(C.BORDER_A),1))
        p.drawRoundedRect(QRectF(0,0,W,H),5,5)

        # Barra de progreso — más alta y visible
        bar_h = 6; bar_y = H - bar_h - 6; bar_w = W - 14; bar_x = 7
        fill_w = int(bar_w * self._value / 100)

        # Fondo barra
        p.setBrush(QBrush(qcol(C.BAR_BG))); p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(QRectF(bar_x, bar_y, bar_w, bar_h), 3, 3)

        # Color de llenado según nivel
        bar_col = qcol(C.RED) if self._value > 85 else (qcol(C.ACC) if self._value > 65 else qcol(self._color))

        # Relleno con brillo en el borde derecho
        if fill_w > 0:
            p.setBrush(QBrush(bar_col))
            p.drawRoundedRect(QRectF(bar_x, bar_y, fill_w, bar_h), 3, 3)
            # Punto brillante al final de la barra
            if fill_w > 4:
                p.setBrush(QBrush(qcol("#ffffff", 120)))
                p.drawEllipse(QRectF(bar_x + fill_w - 4, bar_y + 1, 4, bar_h - 2))

        # Label (izquierda)
        p.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        p.setPen(QPen(qcol(C.TEXT_DIM), 1))
        p.drawText(QRectF(9, 6, 54, 14), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self._label)

        # Indicador de porcentaje con punto de color
        pct_txt = f"{self._value:.0f}%"
        p.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        col_val = bar_col if self._text != "--" else qcol(C.TEXT_DIM)
        p.setPen(QPen(col_val, 1))
        p.drawText(QRectF(0, 5, W - 8, 16), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, self._text)


# ── LogWidget ─────────────────────────────────────────────────────────────────
class LogWidget(QTextEdit):
    _sig = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True); self.setFont(QFont("Courier New", 9))
        self.setStyleSheet(f"""
            QTextEdit {{
                background:{C.PANEL};color:{C.TEXT};
                border:1px solid {C.BORDER};border-radius:5px;
                padding:8px;
                selection-background-color:{C.PRI_GHO};
            }}
            QScrollBar:vertical {{
                background:{C.DARKER};width:6px;border:none;
                border-radius:3px;
            }}
            QScrollBar::handle:vertical {{
                background:{C.BORDER_B};border-radius:3px;min-height:20px;
            }}
            QScrollBar::handle:vertical:hover {{
                background:{C.PRI_DIM};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height:0;
            }}
        """)
        self._queue: list[str] = []; self._typing=False; self._text=""; self._pos=0; self._tag="sys"
        self._tmr=QTimer(self); self._tmr.timeout.connect(self._step)
        self._sig.connect(self._enqueue)

    def append_log(self, text: str): self._sig.emit(text)

    def _enqueue(self, text: str):
        self._queue.append(text)
        if not self._typing: self._next()

    def _next(self):
        if not self._queue: self._typing=False; return
        self._typing=True; self._text=self._queue.pop(0); self._pos=0
        tl=self._text.lower()
        if tl.startswith("you:"): self._tag="you"
        elif tl.startswith("jarvis:"): self._tag="ai"
        elif tl.startswith("file:"): self._tag="file"
        elif "err" in tl: self._tag="err"
        else: self._tag="sys"
        self._tmr.start(6)

    def _step(self):
        if self._pos<len(self._text):
            ch=self._text[self._pos]; cur=self.textCursor(); fmt=cur.charFormat()
            col={"you":qcol(C.WHITE),"ai":qcol(C.PRI),"err":qcol(C.RED),
                 "file":qcol(C.GREEN),"sys":qcol(C.ACC2)}.get(self._tag,qcol(C.TEXT))
            fmt.setForeground(QBrush(col)); cur.movePosition(cur.MoveOperation.End)
            cur.insertText(ch,fmt); self.setTextCursor(cur); self.ensureCursorVisible(); self._pos+=1
        else:
            self._tmr.stop(); cur=self.textCursor(); cur.movePosition(cur.MoveOperation.End)
            cur.insertText("\n"); self.setTextCursor(cur); self.ensureCursorVisible()
            QTimer.singleShot(20,self._next)


# ── FileDropZone ──────────────────────────────────────────────────────────────
_FILE_ICONS = {
    "image":("🖼","#00d4ff"),"video":("🎬","#ff6b00"),"audio":("🎵","#cc44ff"),
    "pdf":("📄","#ff4444"),"word":("📝","#4488ff"),"excel":("📊","#44bb44"),
    "code":("💻","#ffcc00"),"archive":("📦","#ff8844"),"pptx":("📊","#ff6622"),
    "text":("📃","#aaaaaa"),"data":("🔧","#88ddff"),"unknown":("📎","#888888"),
}
_EXT_TO_CAT = {
    **dict.fromkeys(["jpg","jpeg","png","gif","webp","bmp","tiff","svg","ico"],"image"),
    **dict.fromkeys(["mp4","avi","mov","mkv","wmv","flv","webm","m4v"],"video"),
    **dict.fromkeys(["mp3","wav","ogg","m4a","aac","flac","wma","opus"],"audio"),
    **dict.fromkeys(["pdf"],"pdf"),**dict.fromkeys(["doc","docx"],"word"),
    **dict.fromkeys(["xls","xlsx","ods"],"excel"),**dict.fromkeys(["ppt","pptx"],"pptx"),
    **dict.fromkeys(["py","js","ts","jsx","tsx","html","css","java","c","cpp","cs","go","rs","rb","php","sh","sql"],"code"),
    **dict.fromkeys(["zip","rar","tar","gz","7z","bz2","xz"],"archive"),
    **dict.fromkeys(["txt","md","rst","log"],"text"),
    **dict.fromkeys(["csv","tsv","json","xml"],"data"),
}

def _file_category(path: Path) -> str:
    return _EXT_TO_CAT.get(path.suffix.lower().lstrip("."), "unknown")

def _fmt_size(size: int) -> str:
    if size<1024: return f"{size} B"
    elif size<1024**2: return f"{size/1024:.1f} KB"
    elif size<1024**3: return f"{size/1024**2:.1f} MB"
    else: return f"{size/1024**3:.1f} GB"


class FileDropZone(QWidget):
    file_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent); self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor); self.setFixedHeight(90)
        self._current_file: str|None = None
        self._hovering=False; self._drag_over=False; self._dash_offset=0.0
        self._anim_tmr=QTimer(self); self._anim_tmr.timeout.connect(self._animate); self._anim_tmr.start(40)
        layout=QVBoxLayout(self); layout.setContentsMargins(0,0,0,0); layout.setSpacing(0)
        self._canvas=_DropCanvas(self); layout.addWidget(self._canvas)

    def _animate(self): self._dash_offset=(self._dash_offset+0.8)%20; self._canvas.update()
    def dragEnterEvent(self,e:QDragEnterEvent):
        if e.mimeData().hasUrls(): e.acceptProposedAction(); self._drag_over=True; self._canvas.update()
    def dragLeaveEvent(self,e): self._drag_over=False; self._canvas.update()
    def dropEvent(self,e:QDropEvent):
        self._drag_over=False; urls=e.mimeData().urls()
        if urls:
            path=urls[0].toLocalFile()
            if Path(path).is_file(): self._set_file(path)
        self._canvas.update()
    def mousePressEvent(self,e):
        if e.button()==Qt.MouseButton.LeftButton: self._browse()
    def enterEvent(self,e): self._hovering=True; self._canvas.update()
    def leaveEvent(self,e): self._hovering=False; self._canvas.update()
    def current_file(self) -> str|None: return self._current_file
    def clear_file(self): self._current_file=None; self._canvas.update()
    def _browse(self):
        path,_=QFileDialog.getOpenFileName(self,"Seleccionar archivo",str(Path.home()),"All Files (*.*)")
        if path: self._set_file(path)
    def _set_file(self, path: str):
        self._current_file=path; self._canvas.update(); self.file_selected.emit(path)


class _DropCanvas(QWidget):
    def __init__(self, zone: FileDropZone):
        super().__init__(zone); self._z=zone

    def paintEvent(self,_):
        p=QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        z=self._z; W,H=self.width(),self.height(); pad=6
        rect=QRectF(pad,pad,W-pad*2,H-pad*2)
        bg_col=qcol("#001a24" if z._drag_over else ("#001218" if z._hovering else C.PANEL))
        p.setBrush(QBrush(bg_col)); p.setPen(Qt.PenStyle.NoPen); p.drawRoundedRect(rect,6,6)
        if z._current_file: border_col=qcol(C.GREEN,200)
        elif z._drag_over:  border_col=qcol(C.PRI,230)
        elif z._hovering:   border_col=qcol(C.BORDER_B,200)
        else:               border_col=qcol(C.BORDER,160)
        pen=QPen(border_col,1.5,Qt.PenStyle.DashLine); pen.setDashOffset(z._dash_offset)
        p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush); p.drawRoundedRect(rect,6,6)
        if z._current_file: self._paint_file(p,W,H)
        elif z._drag_over:  self._paint_drag(p,W,H)
        else:               self._paint_idle(p,W,H,z._hovering)

    def _paint_idle(self,p,W,H,hover):
        cx,cy=W/2,H/2; col=qcol(C.PRI_DIM if not hover else C.PRI)
        p.setPen(QPen(col,2)); p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawLine(QPointF(cx,cy-12),QPointF(cx,cy+4))
        p.drawLine(QPointF(cx-7,cy-5),QPointF(cx,cy-12))
        p.drawLine(QPointF(cx+7,cy-5),QPointF(cx,cy-12))
        p.drawLine(QPointF(cx-12,cy+4),QPointF(cx+12,cy+4))
        p.setFont(QFont("Courier New",8)); p.setPen(QPen(qcol(C.PRI_DIM if not hover else C.TEXT),1))
        p.drawText(QRectF(0,cy+7,W,15),Qt.AlignmentFlag.AlignCenter,"Soltar archivo  o  Click para buscar")
        p.setFont(QFont("Courier New",7)); p.setPen(QPen(qcol("#1a4a5a"),1))
        p.drawText(QRectF(0,cy+22,W,12),Qt.AlignmentFlag.AlignCenter,"IMG · VIDEO · AUDIO · PDF · DOCS · CODE")

    def _paint_drag(self,p,W,H):
        cx,cy=W/2,H/2; p.setFont(QFont("Courier New",18)); p.setPen(QPen(qcol(C.PRI),1))
        p.drawText(QRectF(0,cy-22,W,30),Qt.AlignmentFlag.AlignCenter,"⬇")
        p.setFont(QFont("Courier New",8,QFont.Weight.Bold)); p.setPen(QPen(qcol(C.PRI),1))
        p.drawText(QRectF(0,cy+12,W,15),Qt.AlignmentFlag.AlignCenter,"Soltar aquí")

    def _paint_file(self,p,W,H):
        path=Path(self._z._current_file); cat=_file_category(path)
        icon,icon_col=_FILE_ICONS.get(cat,_FILE_ICONS["unknown"])
        size_str=_fmt_size(path.stat().st_size)
        p.setFont(QFont("Segoe UI Emoji",20) if _OS=="Windows" else QFont("Arial",20))
        p.setPen(QPen(qcol(icon_col),1))
        p.drawText(QRectF(8,0,50,H),Qt.AlignmentFlag.AlignCenter,icon)
        tx=64; tw=W-tx-36
        p.setFont(QFont("Courier New",8,QFont.Weight.Bold)); p.setPen(QPen(qcol(C.WHITE),1))
        name=path.name if len(path.name)<=34 else path.name[:31]+"..."
        p.drawText(QRectF(tx,H*0.2,tw,15),Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter,name)
        p.setFont(QFont("Courier New",7)); p.setPen(QPen(qcol(C.TEXT_DIM),1))
        p.drawText(QRectF(tx,H*0.2+17,tw,13),Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter,
                   f"{path.suffix.upper().lstrip('.')}  ·  {size_str}")
        p.setFont(QFont("Courier New",9,QFont.Weight.Bold)); p.setPen(QPen(qcol(C.RED,180),1))
        p.drawText(QRectF(W-34,0,28,H),Qt.AlignmentFlag.AlignCenter,"✕")

    def mousePressEvent(self,e):
        z=self._z
        if z._current_file and e.pos().x()>self.width()-34: z.clear_file()
        else: z.mousePressEvent(e)


# ── Panel de Ajustes ──────────────────────────────────────────────────────────
class SettingsPanel(QWidget):
    closed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SettingsPanel")
        self.setStyleSheet(
            f"QWidget#SettingsPanel {{background:{C.DARK};border:1px solid {C.BORDER_B};border-radius:10px;}}" +
            f"QLabel {{background:transparent;color:{C.TEXT};}}" +
            f"QLineEdit,QSpinBox,QComboBox {{background:{C.DARKER};color:{C.WHITE};"
            f"border:1px solid {C.BORDER};border-radius:4px;padding:5px 9px;"
            f"font-family:'Courier New';font-size:9pt;}}" +
            "QComboBox::drop-down {border:none;width:20px;}" +
            f"QComboBox QAbstractItemView {{background:{C.DARKER};color:{C.WHITE};"
            f"border:1px solid {C.BORDER_B};selection-background-color:{C.PRI_GHO};"
            f"selection-color:{C.PRI};font-family:'Courier New';font-size:9pt;outline:none;}}" +
            f"QLineEdit:focus,QComboBox:focus {{border:1px solid {C.PRI};}}" +
            f"QCheckBox {{color:{C.TEXT};font-family:'Courier New';font-size:9pt;}}" +
            f"QCheckBox::indicator {{width:15px;height:15px;border:1px solid {C.BORDER_B};"
            f"border-radius:3px;background:{C.DARKER};}}" +
            f"QCheckBox::indicator:checked {{background:{C.PRI};border:1px solid {C.PRI};}}" +
            f"QSlider::groove:horizontal {{height:5px;background:{C.BAR_BG};border-radius:2px;}}" +
            f"QSlider::handle:horizontal {{width:15px;height:15px;background:{C.PRI};"
            f"border-radius:7px;margin:-5px 0;}}" +
            f"QScrollBar:vertical {{background:{C.DARKER};width:6px;border:none;}}" +
            f"QScrollBar::handle:vertical {{background:{C.BORDER_B};border-radius:3px;min-height:20px;}}" +
            f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{height:0;}}"
        )

        main_lay = QVBoxLayout(self)
        main_lay.setContentsMargins(12,10,12,10)
        main_lay.setSpacing(8)

        # Header
        hdr = QHBoxLayout()
        title = QLabel("⚙  CONFIGURACIÓN DE JARVIS")
        title.setFont(QFont("Courier New", 12, QFont.Weight.Bold))
        title.setStyleSheet(f"color:{C.ORANGE};background:transparent;letter-spacing:2px;")
        hdr.addWidget(title)
        hdr.addStretch()
        ver_lbl = QLabel("MARK XXXIX")
        ver_lbl.setFont(QFont("Courier New", 8))
        ver_lbl.setStyleSheet(
            f"color:{C.TEXT_DIM};background:{C.PANEL2};"
            f"border:1px solid {C.BORDER};border-radius:3px;padding:2px 7px;"
        )
        hdr.addWidget(ver_lbl)
        hdr.addSpacing(8)
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(26, 26)
        close_btn.setStyleSheet(
            f"QPushButton{{background:{C.RED_GHO};color:{C.RED};"
            f"border:1px solid {C.RED};border-radius:4px;font-size:10pt;}}"
            f"QPushButton:hover{{background:#300010;}}"
        )
        close_btn.clicked.connect(self._close)
        hdr.addWidget(close_btn)
        main_lay.addLayout(hdr)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color:{C.BORDER_A};"); main_lay.addWidget(sep)

        # Body: tabs + content
        body = QHBoxLayout(); body.setSpacing(8)

        # Tabs
        self._tabs_w = QWidget(); self._tabs_w.setFixedWidth(128)
        tabs_lay = QVBoxLayout(self._tabs_w); tabs_lay.setContentsMargins(0,0,0,0); tabs_lay.setSpacing(3)

        self._tab_btns: dict[str,QPushButton] = {}
        tabs_info = [
            ("identidad","👤 Identidad"),("voz","🎤 Voz"),("reloj","🕐 Reloj"),
            ("rutinas","⏰ Rutinas"),("atajos","⚡ Atajos"),("hogar","💡 Hogar IoT"),
            ("api","🔑 API Keys"),("memoria","🧠 Memoria"),
            ("notif","🔔 Notif."),("privacidad","🔒 Privacidad"),("avanzado","🔧 Avanzado"),
            ("feedback","📬 Feedback"),
        ]
        for key,label in tabs_info:
            btn = QPushButton(label)
            btn.setFont(QFont("Courier New", 8))
            btn.setFixedHeight(28)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _,k=key: self._show_tab(k))
            tabs_lay.addWidget(btn)
            self._tab_btns[key] = btn
        tabs_lay.addStretch()
        body.addWidget(self._tabs_w)

        # Stacked content
        self._stack = QStackedWidget()
        self._pages: dict[str,QWidget] = {}
        for key,_ in tabs_info:
            page = self._build_page(key)
            self._pages[key] = page
            self._stack.addWidget(page)
        body.addWidget(self._stack,stretch=1)
        main_lay.addLayout(body,stretch=1)

        # Footer save button
        footer_row = QHBoxLayout(); footer_row.setSpacing(6)
        save_btn = QPushButton("💾  GUARDAR")
        save_btn.setFixedHeight(30)
        save_btn.setFont(QFont("Courier New",9,QFont.Weight.Bold))
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.setStyleSheet(f"""
            QPushButton{{background:{C.PRI_GHO};color:{C.PRI};border:1px solid {C.PRI_DIM};border-radius:3px;}}
            QPushButton:hover{{background:#002a3a;border:1px solid {C.PRI};}}
        """)
        save_btn.clicked.connect(self._autosave)
        footer_row.addWidget(save_btn)
        save_close_btn = QPushButton("✓  GUARDAR Y CERRAR")
        save_close_btn.setFixedHeight(30)
        save_close_btn.setFont(QFont("Courier New",9,QFont.Weight.Bold))
        save_close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_close_btn.setStyleSheet(f"""
            QPushButton{{background:transparent;color:{C.GREEN};border:1px solid {C.GREEN_D};border-radius:3px;}}
            QPushButton:hover{{background:#001a0a;border:1px solid {C.GREEN};}}
        """)
        save_close_btn.clicked.connect(self._save_all)
        footer_row.addWidget(save_close_btn)
        main_lay.addLayout(footer_row)

        self._show_tab("identidad")

    def _lbl(self, txt, color=None, size=8, bold=False):
        l = QLabel(txt)
        l.setFont(QFont("Courier New",size,QFont.Weight.Bold if bold else QFont.Weight.Normal))
        l.setStyleSheet(f"color:{color or C.TEXT_DIM};background:transparent;")
        return l

    def _section_title(self, txt):
        l = QLabel(txt)
        l.setFont(QFont("Courier New",9,QFont.Weight.Bold))
        l.setStyleSheet(f"color:{C.PRI};background:transparent;border-bottom:1px solid {C.BORDER};padding-bottom:3px;")
        return l

    def _build_page(self, key: str) -> QWidget:
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea{{background:transparent;border:none;}}")
        inner = QWidget(); inner.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(inner); lay.setSpacing(8); lay.setContentsMargins(4,4,4,4)

        if key == "identidad":
            lay.addWidget(self._section_title("◆ IDENTIDAD DEL USUARIO"))
            lay.addWidget(self._lbl("Cómo te llama JARVIS"))
            self._call_me = QLineEdit(_prefs.get("call_me","jefe"))
            self._call_me.editingFinished.connect(self._autosave)
            lay.addWidget(self._call_me)

            lay.addWidget(self._lbl("Ciudad / Ubicación"))
            self._city = QLineEdit(_prefs.get("city","México"))
            lay.addWidget(self._city)
            lay.addWidget(self._lbl("Personalidad de JARVIS"))
            self._personality = DarkCombo()
            self._personality.addItems(["Iron Man — sarcástico y leal","Formal — profesional","Amigable — casual","Militar — instructor de élite 🎖","🇲🇽 Barrio — albureño y chilango"])
            lay.addWidget(self._personality)

        elif key == "voz":
            lay.addWidget(self._section_title("◆ CONFIGURACIÓN DE VOZ"))
            lay.addWidget(self._lbl("Velocidad de respuesta"))
            self._voice_speed = QSlider(Qt.Orientation.Horizontal)
            self._voice_speed.setRange(5,20); self._voice_speed.setValue(10)
            lay.addWidget(self._voice_speed)
            spd_row = QHBoxLayout()
            spd_row.addWidget(self._lbl("Lento")); spd_row.addStretch()
            spd_row.addWidget(self._lbl("Normal")); spd_row.addStretch()
            spd_row.addWidget(self._lbl("Rápido"))
            lay.addLayout(spd_row)
            lay.addSpacing(6)
            lay.addWidget(self._lbl("Nota: la voz de JARVIS se configura en el archivo config/api_keys.json (campo voice_name)", C.TEXT_DIM, 7))
            lay.addSpacing(6)
            lay.addWidget(self._lbl("Tiempo de silencio antes de responder (seg)"))
            self._vad_timeout = QSlider(Qt.Orientation.Horizontal)
            self._vad_timeout.setRange(10,50); self._vad_timeout.setValue(25)
            lay.addWidget(self._vad_timeout)

        elif key == "reloj":
            lay.addWidget(self._section_title("◆ FORMATO DEL RELOJ"))
            self._clock_24h = QCheckBox("Usar formato 24 horas  (ej. 18:30)")
            self._clock_24h.setChecked(_prefs.get("clock_24h",True))
            lay.addWidget(self._clock_24h)
            self._clock_12h_lbl = self._lbl("Desactivado = formato 12h  (ej. 6:30 PM)",C.TEXT_DIM,7)
            lay.addWidget(self._clock_12h_lbl)
            lay.addSpacing(8)
            lay.addWidget(self._lbl("Ejemplo con 24h:", C.TEXT_MED))
            self._clock_preview = QLabel("18:30:45")
            self._clock_preview.setFont(QFont("Courier New",18,QFont.Weight.Bold))
            self._clock_preview.setStyleSheet(f"color:{C.PRI};background:transparent;")
            lay.addWidget(self._clock_preview)
            self._clock_24h.stateChanged.connect(self._update_clock_preview)
            self._clock_update_tmr = QTimer(self)
            self._clock_update_tmr.timeout.connect(self._update_clock_preview)
            self._clock_update_tmr.start(1000)

        elif key == "rutinas":
            lay.addWidget(self._section_title("◆ RUTINAS PROGRAMADAS"))
            lay.addWidget(self._lbl("JARVIS ejecuta estas tareas automáticamente a la hora configurada.", C.TEXT_MED, 7))
            lay.addSpacing(4)

            # Instrucciones
            info = QLabel(
                "• Hora en formato 24h  (ej: 07:00, 22:30)\n"
                "• Días: Todos | L-V | Fines | L,M,X,J,V | Lunes\n"
                "• Tareas: escribe lo que quieres que JARVIS diga o haga"
            )
            info.setFont(QFont("Courier New", 7))
            info.setStyleSheet(f"color:{C.TEXT_FADE};background:{C.PANEL2};"
                               f"border:1px solid {C.BORDER};border-radius:3px;padding:6px 8px;")
            info.setWordWrap(True)
            lay.addWidget(info)
            lay.addSpacing(6)

            self._rutinas_container = QWidget()
            self._rutinas_container.setStyleSheet("background:transparent;")
            self._rutinas_lay = QVBoxLayout(self._rutinas_container)
            self._rutinas_lay.setContentsMargins(0,0,0,0); self._rutinas_lay.setSpacing(6)
            self._rutinas_data = list(_prefs.get("routines",[]))
            self._rutinas_widgets = []
            for r in self._rutinas_data:
                self._add_rutina_widget(r)
            lay.addWidget(self._rutinas_container)
            lay.addSpacing(4)

            add_r_btn = QPushButton("＋  Nueva rutina")
            add_r_btn.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
            add_r_btn.setFixedHeight(30)
            add_r_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            add_r_btn.setStyleSheet(
                f"QPushButton{{background:{C.GREEN_GHO};color:{C.GREEN};"
                f"border:1px solid {C.GREEN_D};border-radius:4px;}}"
                f"QPushButton:hover{{background:#002214;}}"
            )
            add_r_btn.clicked.connect(lambda: self._add_rutina_widget({
                "time": "08:00", "days": "Todos",
                "tasks": ["saluda con tu personalidad y dime el clima de hoy"]
            }))
            lay.addWidget(add_r_btn)

        elif key == "atajos":
            lay.addWidget(self._section_title("◆ ACCESOS RÁPIDOS"))
            lay.addWidget(self._lbl("Los 3 botones fijos del panel lateral",C.TEXT_MED,7))
            lay.addSpacing(8)
            self._shortcut_fields = []
            defaults = [
                ("💡 Luces",          "Jarvis enciende todas las luces"),
                ("🎵 Música",         "Jarvis pon música"),
                ("🗓 Reservaciones",  "Jarvis quiero hacer una reservación"),
            ]
            for i, (label, cmd) in enumerate(defaults):
                lay.addWidget(self._lbl(f"Botón {i+1}: {label}", C.TEXT_MED, 8, True))
                field = QLineEdit(cmd); field.setFixedHeight(28)
                lay.addWidget(field); self._shortcut_fields.append(field)
                lay.addSpacing(4)
            lay.addWidget(self._lbl("Edita el comando que se envía a JARVIS al presionar cada botón.", C.TEXT_DIM, 7))

        elif key == "hogar":
            lay.addWidget(self._section_title("◆ DISPOSITIVOS IOT — TUYA"))
            lay.addWidget(self._lbl("Agrega o elimina dispositivos Tuya",C.TEXT_MED,7))
            lay.addSpacing(4)
            self._devs_container = QWidget(); self._devs_container.setStyleSheet("background:transparent;")
            self._devs_lay = QVBoxLayout(self._devs_container)
            self._devs_lay.setContentsMargins(0,0,0,0); self._devs_lay.setSpacing(4)
            # Cargar dispositivos guardados por el usuario (no hardcodeados)
            self._devs_data = _prefs.get("devices", [])
            self._devs_widgets = []
            for d in self._devs_data:
                self._add_dev_widget(d)
            lay.addWidget(self._devs_container)
            add_d_btn = QPushButton("+ Agregar dispositivo")
            add_d_btn.setFont(QFont("Courier New",8)); add_d_btn.setFixedHeight(26)
            add_d_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            add_d_btn.setStyleSheet(f"QPushButton{{background:transparent;color:{C.PRI};border:1px solid {C.BORDER_B};border-radius:3px;}}"
                                    f"QPushButton:hover{{background:{C.PRI_GHO};}}")
            add_d_btn.clicked.connect(lambda: self._add_dev_widget({"nombre":"nuevo","id":"","tipo":"Bombilla"}))
            lay.addWidget(add_d_btn)



            lay.addWidget(self._section_title("◆ ESTADO DEL SISTEMA"))
            lay.addSpacing(6)
            # Verificar estado de conexion
            try:
                d = json.loads(API_FILE.read_text(encoding="utf-8"))
                has_key = bool(d.get("gemini_api_key",""))
            except Exception:
                has_key = False
            status_col = C.GREEN if has_key else C.RED
            status_txt = "● Conectado y listo" if has_key else "● Sin conexión"
            status_lbl = QLabel(status_txt)
            status_lbl.setFont(QFont("Courier New",11,QFont.Weight.Bold))
            status_lbl.setStyleSheet(f"color:{status_col};background:transparent;")
            lay.addWidget(status_lbl)
            lay.addSpacing(8)
            lay.addWidget(self._lbl("JARVIS usa conexión a internet para:",C.TEXT_MED,8,True))
            for item in [
                "Procesar tu voz y responder",
                "Buscar información en internet",
                "Generar documentos inteligentes",
                "Crear alarmas y recordatorios",
            ]:
                lay.addWidget(self._lbl(f"  ✓ {item}", C.GREEN, 8))
            lay.addSpacing(8)
            lay.addWidget(self._lbl("Sin internet JARVIS puede:",C.TEXT_MED,8,True))
            for item in [
                "Controlar luces y dispositivos IoT",
                "Usar IA local (Ollama) para respuestas básicas",
            ]:
                lay.addWidget(self._lbl(f"  ✓ {item}", C.ORANGE, 8))
            lay.addSpacing(8)
            self._api_key_field = QLineEdit()  # mantener referencia para autosave

        elif key == "memoria":
            lay.addWidget(self._section_title("◆ SISTEMA DE MEMORIA"))
            self._mem_enabled = QCheckBox("Activar memoria persistente entre sesiones")
            self._mem_enabled.setChecked(_prefs.get("memory_enabled",True))
            lay.addWidget(self._mem_enabled)
            lay.addSpacing(6)
            lay.addWidget(self._lbl("JARVIS recuerda:",C.TEXT_MED))
            for item in ["Tu nombre y cómo llamarte","Tu ciudad y ubicación","Preferencias de música",
                         "Proyectos en los que trabajas","Contactos importantes"]:
                lay.addWidget(self._lbl(f"  · {item}",C.TEXT_DIM,7))
            lay.addSpacing(8)
            mem_path = Path(os.environ.get("APPDATA","~")).expanduser() / "JARVIS_Mark39" / "memory.json"
            size_str = _fmt_size(mem_path.stat().st_size) if mem_path.exists() else "Vacía"
            lay.addWidget(self._lbl(f"Archivo de memoria: {size_str}",C.TEXT_DIM,7))
            clear_btn = QPushButton("🗑  Borrar toda la memoria")
            clear_btn.setFont(QFont("Courier New",8)); clear_btn.setFixedHeight(28)
            clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            clear_btn.setStyleSheet(f"QPushButton{{background:#140006;color:{C.RED};border:1px solid {C.RED};border-radius:3px;}}"
                                    f"QPushButton:hover{{background:#280010;}}")
            lay.addWidget(clear_btn)

        elif key == "notif":
            lay.addWidget(self._section_title("◆ NOTIFICACIONES"))
            self._notif_sound    = QCheckBox("Sonido al activarse (wake word)")
            self._notif_error    = QCheckBox("Sonido en errores")
            self._notif_complete = QCheckBox("Sonido al completar tareas")
            self._notif_mic      = QCheckBox("Indicador visual cuando el micrófono está activo")
            for cb in [self._notif_sound,self._notif_error,self._notif_complete,self._notif_mic]:
                cb.setChecked(True); lay.addWidget(cb)
            lay.addSpacing(8)
            lay.addWidget(self._lbl("Volumen de notificaciones"))
            self._notif_vol = QSlider(Qt.Orientation.Horizontal)
            self._notif_vol.setRange(0,100); self._notif_vol.setValue(70)
            lay.addWidget(self._notif_vol)

        elif key == "privacidad":
            lay.addWidget(self._section_title("◆ PRIVACIDAD"))
            lay.addSpacing(6)
            lay.addWidget(self._lbl("JARVIS no comparte ni envía tus datos a nadie.", C.GREEN, 9, True))
            lay.addSpacing(4)
            for item in [
                "Tu voz se procesa por Google Gemini (su política de privacidad aplica)",
                "Tus preferencias se guardan solo en tu computadora",
                "Ningún dato se envía a servidores externos de JARVIS",
                "La memoria de JARVIS se guarda localmente en tu PC",
            ]:
                lay.addWidget(self._lbl(f"  ✓ {item}", C.TEXT_DIM, 8))
            lay.addSpacing(12)
            lay.addWidget(self._lbl("Borrar memoria de JARVIS:", C.TEXT_MED, 8, True))
            clr_mem = QPushButton("🗑  Borrar toda la memoria de JARVIS")
            clr_mem.setFont(QFont("Courier New",8)); clr_mem.setFixedHeight(28)
            clr_mem.setCursor(Qt.CursorShape.PointingHandCursor)
            clr_mem.setStyleSheet(f"QPushButton{{background:#140006;color:{C.RED};border:1px solid {C.RED};border-radius:3px;}}"
                                  f"QPushButton:hover{{background:#280010;}}")
            def _clear_memory():
                try:
                    import os
                    mem_path = Path(os.environ.get("APPDATA","")) / "JARVIS_Mark39" / "memory.json"
                    if mem_path.exists(): mem_path.unlink()
                    last_seen = BASE_DIR / "config" / "last_seen.txt"
                    if last_seen.exists(): last_seen.unlink()
                except Exception as e:
                    print(f"[Memory] Error: {e}")
            clr_mem.clicked.connect(_clear_memory)
            lay.addWidget(clr_mem)

        elif key == "avanzado":
            lay.addWidget(self._section_title("◆ CONFIGURACIÓN AVANZADA"))
            lay.addSpacing(4)
            lay.addWidget(self._lbl("Tiempo de espera antes de dormir (segundos)"))
            lay.addWidget(self._lbl("Cuánto tiempo espera JARVIS sin actividad antes de silenciarse",C.TEXT_DIM,7))
            self._active_timeout = QSpinBox()
            self._active_timeout.setRange(5,120); self._active_timeout.setValue(_prefs.get("active_timeout",20))
            self._active_timeout.setFixedHeight(28)
            lay.addWidget(self._active_timeout)
            lay.addSpacing(8)
            self._ollama_cb = QCheckBox("Usar IA local (Ollama) cuando no hay internet")
            self._ollama_cb.setChecked(_prefs.get("ollama_fallback",True))
            lay.addWidget(self._ollama_cb)
            lay.addWidget(self._lbl("Ollama permite respuestas básicas sin conexión a internet",C.TEXT_DIM,7))
            self._debug_cb = QCheckBox("")  # mantener referencia pero oculto
            lay.addSpacing(12)
            lay.addWidget(self._lbl("── INFORMACIÓN ──",C.BORDER_B,8))
            lay.addWidget(self._lbl("Versión: MARK XXXIX — Build 2026",C.TEXT_DIM,7))
            lay.addWidget(self._lbl("Desarrollado por: Jose Antonio Carbajal Quintanar",C.TEXT_DIM,7))

        elif key == "feedback":
            _DEST = "programatec108@gmail.com"

            lay.addWidget(self._section_title("◆ CONTACTO CON EL DESARROLLADOR"))
            lay.addSpacing(4)

            # Descripción
            desc = QLabel(
                "¿Tienes una sugerencia, encontraste un bug o quieres pedir una nueva función?\n"
                "Escríbeme directamente — leo todos los mensajes."
            )
            desc.setFont(QFont("Courier New", 8))
            desc.setStyleSheet(f"color:{C.TEXT_MED};background:transparent;")
            desc.setWordWrap(True)
            lay.addWidget(desc)
            lay.addSpacing(10)

            # Tipo de mensaje
            lay.addWidget(self._lbl("Tipo de mensaje", C.TEXT_DIM, 8))
            self._fb_tipo = DarkCombo()
            self._fb_tipo.addItems([
                "🐛  Reporte de bug / error",
                "💡  Sugerencia de mejora",
                "✨  Nueva función que quiero",
                "🙋  Pregunta general",
                "❤️  Agradecimiento / feedback positivo",
            ])
            self._fb_tipo.setFixedHeight(30)
            lay.addWidget(self._fb_tipo)
            lay.addSpacing(8)

            # Asunto
            lay.addWidget(self._lbl("Asunto", C.TEXT_DIM, 8))
            self._fb_asunto = QLineEdit()
            self._fb_asunto.setPlaceholderText("Ej: JARVIS no reconoce mi voz cuando...")
            self._fb_asunto.setFixedHeight(30)
            self._fb_asunto.setFont(QFont("Courier New", 9))
            lay.addWidget(self._fb_asunto)
            lay.addSpacing(8)

            # Mensaje
            lay.addWidget(self._lbl("Mensaje", C.TEXT_DIM, 8))
            self._fb_msg = QTextEdit()
            self._fb_msg.setPlaceholderText(
                "Describe tu sugerencia o el problema con el mayor detalle posible...\n\n"
                "Si es un bug: ¿qué hiciste? ¿qué esperabas que pasara? ¿qué pasó?"
            )
            self._fb_msg.setFont(QFont("Courier New", 9))
            self._fb_msg.setFixedHeight(120)
            self._fb_msg.setStyleSheet(
                f"QTextEdit{{background:{C.DARKER};color:{C.WHITE};"
                f"border:1px solid {C.BORDER};border-radius:4px;padding:6px;}}"
                f"QTextEdit:focus{{border:1px solid {C.PRI};}}"
                f"QScrollBar:vertical{{background:{C.DARKER};width:5px;border:none;}}"
                f"QScrollBar::handle:vertical{{background:{C.BORDER_B};border-radius:2px;}}"
            )
            lay.addWidget(self._fb_msg)
            lay.addSpacing(10)

            # Label de estado (oculto hasta enviar)
            self._fb_status = QLabel("")
            self._fb_status.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
            self._fb_status.setStyleSheet(f"color:{C.GREEN};background:transparent;")
            self._fb_status.setWordWrap(True)
            lay.addWidget(self._fb_status)

            # Botón enviar
            send_btn = QPushButton("📬  ENVIAR MENSAJE")
            send_btn.setFixedHeight(36)
            send_btn.setFont(QFont("Courier New", 10, QFont.Weight.Bold))
            send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            send_btn.setStyleSheet(
                f"QPushButton{{background:{C.PRI_GHO};color:{C.PRI};"
                f"border:2px solid {C.PRI_DIM};border-radius:5px;letter-spacing:1px;}}"
                f"QPushButton:hover{{background:#002a40;border:2px solid {C.PRI};}}"
                f"QPushButton:pressed{{background:{C.DARKER};}}"
            )
            send_btn.clicked.connect(lambda: self._send_feedback(_DEST))
            lay.addWidget(send_btn)
            lay.addSpacing(8)

            # Info de destino
            dest_lbl = QLabel(f"Se enviará a: {_DEST}")
            dest_lbl.setFont(QFont("Courier New", 7))
            dest_lbl.setStyleSheet(f"color:{C.TEXT_FADE};background:transparent;")
            lay.addWidget(dest_lbl)

            lay.addSpacing(10)
            sep_fb = QFrame(); sep_fb.setFrameShape(QFrame.Shape.HLine)
            sep_fb.setStyleSheet(f"color:{C.BORDER};"); lay.addWidget(sep_fb)
            lay.addSpacing(6)

            nota = QLabel(
                "El mensaje se envía directo desde JARVIS — no necesitas tener\n"
                "ningún cliente de correo configurado."
            )
            nota.setFont(QFont("Courier New", 7))
            nota.setStyleSheet(f"color:{C.TEXT_FADE};background:transparent;")
            nota.setWordWrap(True)
            lay.addWidget(nota)

        lay.addStretch()
        scroll.setWidget(inner)
        return scroll

    def _update_clock_preview(self):
        try:
            fmt = "%H:%M:%S" if self._clock_24h.isChecked() else "%I:%M:%S %p"
            self._clock_preview.setText(time.strftime(fmt))
        except Exception:
            pass



    def _show_tab(self, key: str):
        if key in self._pages:
            self._stack.setCurrentWidget(self._pages[key])
        for k,btn in self._tab_btns.items():
            if k==key:
                btn.setStyleSheet(
                    f"QPushButton{{background:{C.PRI_GHO};color:{C.PRI};"
                    f"border:1px solid {C.PRI_DIM};border-radius:4px;"
                    f"text-align:left;padding:0 8px;}}"
                    f"QPushButton:hover{{background:{C.PRI_GHO};}}"
                )
            else:
                btn.setStyleSheet(
                    f"QPushButton{{background:transparent;color:{C.TEXT_DIM};"
                    f"border:1px solid {C.BORDER};border-radius:4px;"
                    f"text-align:left;padding:0 8px;}}"
                    f"QPushButton:hover{{color:{C.TEXT};border:1px solid {C.BORDER_B};}}"
                )

    def _get_device_names(self):
        """Retorna lista de dispositivos del usuario."""
        base = ["Apagar todas las luces","Encender todas las luces"]
        for d_w,name_f,id_f,tipo_f in getattr(self,"_devs_widgets",[]):
            if not d_w.isHidden() and name_f.text().strip():
                nombre = name_f.text().strip()
                base.append(f"Encender {nombre}")
                base.append(f"Apagar {nombre}")
        return base

    def _add_task_row(self, tasks_lay, task_fields, texto=""):
        """Agrega una fila de tarea con campo de texto Y selector de dispositivo."""
        row_w = QWidget(); row_w.setStyleSheet("background:transparent;")
        row = QHBoxLayout(row_w); row.setContentsMargins(0,0,0,0); row.setSpacing(3)

        tf = QLineEdit(texto); tf.setFixedHeight(22)
        tf.setStyleSheet(
            f"background:#000d14;color:{C.TEXT_DIM};border:1px solid {C.BORDER};"
            f"border-radius:2px;padding:1px 4px;font-family:'Courier New';font-size:7pt;"
        )
        tf.setPlaceholderText("Escribe o elige dispositivo →")
        row.addWidget(tf)

        dev_btn = QPushButton("💡")
        dev_btn.setFixedSize(22,22)
        dev_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        dev_btn.setToolTip("Elegir dispositivo IoT")
        dev_btn.setStyleSheet(
            f"QPushButton{{background:#001a0a;color:{C.GREEN};border:1px solid {C.GREEN_D};"
            f"border-radius:2px;font-size:11pt;}}"
            f"QPushButton:hover{{background:#002a14;}}"
        )

        def _show_device_menu(tf=tf):
            menu_w = QWidget(self)
            menu_w.setStyleSheet(
                f"QWidget{{background:#000d14;border:1px solid {C.BORDER_B};border-radius:4px;}}"
            )
            menu_lay = QVBoxLayout(menu_w); menu_lay.setContentsMargins(3,3,3,3); menu_lay.setSpacing(2)

            devices = self._get_device_names()
            for dev in devices:
                d_btn = QPushButton(dev)
                d_btn.setFixedHeight(22)
                d_btn.setFont(QFont("Courier New",7))
                d_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                d_btn.setStyleSheet(
                    f"QPushButton{{background:transparent;color:{C.TEXT};border:none;"
                    f"text-align:left;padding:0 6px;}}"
                    f"QPushButton:hover{{background:{C.PRI_GHO};color:{C.PRI};}}"
                )
                d_btn.clicked.connect(lambda _,t=tf,d=dev: (t.setText(d), menu_w.hide(), menu_w.deleteLater()))
                menu_lay.addWidget(d_btn)

            menu_w.setFixedWidth(220)
            menu_w.setFixedHeight(min(len(devices)*24+6, 200))
            # Posicionar cerca del boton
            pos = dev_btn.mapTo(self, dev_btn.rect().bottomLeft())
            menu_w.move(max(0, pos.x()-180), pos.y())
            menu_w.show(); menu_w.raise_()

        dev_btn.clicked.connect(_show_device_menu)
        row.addWidget(dev_btn)

        del_t = QPushButton("✕")
        del_t.setFixedSize(18,22)
        del_t.setCursor(Qt.CursorShape.PointingHandCursor)
        del_t.setStyleSheet(
            f"QPushButton{{background:transparent;color:{C.RED};border:none;font-size:9pt;}}"
            f"QPushButton:hover{{color:#ff6666;}}"
        )
        del_t.clicked.connect(lambda: (row_w.hide(), row_w.deleteLater(), task_fields.remove(tf) if tf in task_fields else None))
        row.addWidget(del_t)

        tasks_lay.addWidget(row_w)
        task_fields.append(tf)

    def _add_rutina_widget(self, r: dict):
        """Agrega un widget de rutina editable con selector de dispositivos."""
        r_w = QWidget()
        r_w.setStyleSheet(f"background:{C.PANEL2};border:1px solid {C.BORDER_A};border-radius:4px;")
        r_main = QVBoxLayout(r_w); r_main.setContentsMargins(6,4,6,4); r_main.setSpacing(3)

        # Fila horario + dias
        h_row = QHBoxLayout()
        time_field = QLineEdit(r.get("time","08:00"))
        time_field.setFixedWidth(55); time_field.setFixedHeight(22)
        time_field.setStyleSheet(
            f"background:#000d14;color:{C.ORANGE};border:1px solid {C.BORDER};"
            f"border-radius:2px;padding:2px 4px;font-family:'Courier New';font-size:8pt;"
        )
        h_row.addWidget(time_field)

        days_field = QLineEdit(r.get("days","Todos"))
        days_field.setFixedHeight(22); days_field.setPlaceholderText("L-V / Todos / L,M,X,J,V")
        days_field.setStyleSheet(
            f"background:#000d14;color:{C.TEXT};border:1px solid {C.BORDER};"
            f"border-radius:2px;padding:2px 4px;font-family:'Courier New';font-size:8pt;"
        )
        h_row.addWidget(days_field)
        h_row.addStretch()

        del_btn = QPushButton("✕")
        del_btn.setFixedSize(22,22); del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.setStyleSheet(
            f"QPushButton{{background:#140006;color:{C.RED};border:1px solid {C.RED};border-radius:2px;}}"
            f"QPushButton:hover{{background:#280010;}}"
        )
        del_btn.clicked.connect(lambda: self._remove_widget(r_w, self._rutinas_lay))
        h_row.addWidget(del_btn)
        r_main.addLayout(h_row)

        # Separador
        sep = QLabel("Tareas:"); sep.setFont(QFont("Courier New",7))
        sep.setStyleSheet(f"color:{C.TEXT_DIM};background:transparent;")
        r_main.addWidget(sep)

        # Tareas con selector de dispositivo
        task_fields = []
        tasks_w = QWidget(); tasks_w.setStyleSheet("background:transparent;")
        tasks_lay = QVBoxLayout(tasks_w); tasks_lay.setContentsMargins(0,0,0,0); tasks_lay.setSpacing(2)

        for task in r.get("tasks",["Nueva tarea"]):
            self._add_task_row(tasks_lay, task_fields, task)

        r_main.addWidget(tasks_w)

        add_task_btn = QPushButton("+ agregar tarea")
        add_task_btn.setFixedHeight(20); add_task_btn.setFont(QFont("Courier New",7))
        add_task_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_task_btn.setStyleSheet(
            f"QPushButton{{background:transparent;color:{C.GREEN_D};border:none;}}"
            f"QPushButton:hover{{color:{C.GREEN};}}"
        )
        add_task_btn.clicked.connect(lambda: self._add_task_row(tasks_lay, task_fields))
        r_main.addWidget(add_task_btn)

        self._rutinas_lay.addWidget(r_w)
        self._rutinas_widgets.append((r_w, time_field, days_field, task_fields))

    def _add_dev_widget(self, d: dict):
        """Agrega un widget de dispositivo editable."""
        d_w = QWidget()
        d_w.setStyleSheet(f"background:{C.PANEL2};border:1px solid {C.BORDER_A};border-radius:4px;")
        d_lay = QHBoxLayout(d_w); d_lay.setContentsMargins(6,4,6,4); d_lay.setSpacing(4)
        name_f = QLineEdit(d.get("nombre",""))
        name_f.setFixedWidth(80); name_f.setFixedHeight(22); name_f.setPlaceholderText("Nombre")
        name_f.setStyleSheet(f"background:#000d14;color:{C.GREEN};border:1px solid {C.BORDER};border-radius:2px;padding:2px 4px;font-family:'Courier New';font-size:8pt;")
        d_lay.addWidget(name_f)
        id_f = QLineEdit(d.get("id",""))
        id_f.setFixedHeight(22); id_f.setPlaceholderText("Device ID de Tuya")
        id_f.setStyleSheet(f"background:#000d14;color:{C.TEXT_DIM};border:1px solid {C.BORDER};border-radius:2px;padding:2px 4px;font-family:'Courier New';font-size:7pt;")
        d_lay.addWidget(id_f)
        tipo_f = QLineEdit(d.get("tipo","Bombilla"))
        tipo_f.setFixedWidth(65); tipo_f.setFixedHeight(22); tipo_f.setPlaceholderText("Tipo")
        tipo_f.setStyleSheet(f"background:#000d14;color:{C.TEXT_MED};border:1px solid {C.BORDER};border-radius:2px;padding:2px 4px;font-family:'Courier New';font-size:8pt;")
        d_lay.addWidget(tipo_f)
        del_btn = QPushButton("✕")
        del_btn.setFixedSize(22,22); del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.setStyleSheet(f"QPushButton{{background:#140006;color:{C.RED};border:1px solid {C.RED};border-radius:2px;}}"
                              f"QPushButton:hover{{background:#280010;}}")
        del_btn.clicked.connect(lambda: self._remove_widget(d_w, self._devs_lay))
        d_lay.addWidget(del_btn)
        self._devs_lay.addWidget(d_w)
        self._devs_widgets.append((d_w, name_f, id_f, tipo_f))

    def _remove_widget(self, widget: QWidget, layout: QVBoxLayout):
        """Elimina un widget de un layout."""
        layout.removeWidget(widget)
        widget.hide()
        widget.deleteLater()

    def _preview_personality(self, idx: int):
        """Muestra preview de cómo suena la personalidad seleccionada."""
        previews = [
            "Aquí estoy, jefe. ¿Qué necesita? A sus órdenes.",
            "Buenos días. ¿En qué puedo asistirle el día de hoy?",
            "¡Hey! ¿Qué onda? Cuéntame qué necesitas.",
            "¡Soldado! ¡Firme! ¿Cuál es la misión? ¡Reporte de inmediato!",
            "¡Órale wey! ¿Qué pedo? ¿En qué te aviento la mano, carnal? 🇲🇽",
            "Soldado JARVIS reportándose. ¿Cuál es la misión, señor?",
            "¡Ey, aquí estoy! Dime qué necesitas, no te me rajes.",
        ]
        if 0 <= idx < len(previews):
            self._personality_preview.setText(f'Preview: "{previews[idx]}"')

    def _autosave(self):
        """Guarda configuracion sin cerrar el panel."""
        global _prefs
        try:
            _prefs["call_me"]        = self._call_me.text().strip() or "jefe"
            _prefs["city"]           = self._city.text().strip()
            _prefs["personality_idx"]= self._personality.currentIndex()
            _prefs["clock_24h"]      = self._clock_24h.isChecked()
            try: _prefs["active_timeout"] = self._active_timeout.value()
            except Exception: pass
            try: _prefs["ollama_fallback"]= self._ollama_cb.isChecked()
            except Exception: pass
            try: _prefs["debug_mode"]     = self._debug_cb.isChecked()
            except Exception: pass
            try: _prefs["memory_enabled"] = self._mem_enabled.isChecked()
            except Exception: pass
            try: _prefs["shortcuts"]      = [f.text() for f in self._shortcut_fields]
            except Exception: pass
            # Guardar rutinas
            rutinas = []
            for r_w,time_f,days_f,task_fields in getattr(self,"_rutinas_widgets",[]):
                if not r_w.isHidden():
                    tasks = [tf.text().strip() for tf in task_fields if tf.text().strip()]
                    rutinas.append({"time":time_f.text().strip(),"days":days_f.text().strip(),"tasks":tasks})
            if rutinas: _prefs["routines"] = rutinas
            # Guardar dispositivos
            devs = []
            for d_w,name_f,id_f,tipo_f in getattr(self,"_devs_widgets",[]):
                if not d_w.isHidden() and name_f.text().strip():
                    devs.append({"nombre":name_f.text().strip(),"id":id_f.text().strip(),"tipo":tipo_f.text().strip()})
            if devs: _prefs["devices"] = devs
            # API key
# API key is managed by developer, not user
            save_prefs(_prefs)
            self._update_prompt_call_me(_prefs["call_me"], _prefs.get("personality_idx",0))
            # Reconectar JARVIS en vivo si cambió la personalidad o el apelativo
            self._trigger_reconnect()
            # Mostrar confirmacion breve
            self._show_saved_msg()
        except Exception as e:
            print(f"[Settings] Autosave error: {e}")

    def _show_saved_msg(self):
        """Muestra mensaje de guardado brevemente."""
        try:
            if not hasattr(self, '_saved_lbl'):
                self._saved_lbl = QLabel("✓ Guardado", self)
                self._saved_lbl.setFont(QFont("Courier New",8,QFont.Weight.Bold))
                self._saved_lbl.setStyleSheet(
                    f"color:{C.GREEN};background:{C.PANEL2};border:1px solid {C.GREEN_D};"
                    f"border-radius:3px;padding:3px 8px;"
                )
            self._saved_lbl.adjustSize()
            self._saved_lbl.move(self.width()-self._saved_lbl.width()-10, 10)
            self._saved_lbl.show(); self._saved_lbl.raise_()
            QTimer.singleShot(2000, self._saved_lbl.hide)
        except Exception: pass

    def _save_all(self):
        global _prefs
        try:
            _prefs["call_me"]        = self._call_me.text().strip() or "jefe"
            _prefs["city"]           = self._city.text().strip()
            _prefs["personality_idx"]= self._personality.currentIndex()
            _prefs["clock_24h"]      = self._clock_24h.isChecked()
            _prefs["active_timeout"] = self._active_timeout.value()
            _prefs["ollama_fallback"]= self._ollama_cb.isChecked()
            _prefs["debug_mode"]     = self._debug_cb.isChecked()
            _prefs["memory_enabled"] = self._mem_enabled.isChecked()
            _prefs["shortcuts"]      = [f.text() for f in self._shortcut_fields]

            # Guardar rutinas
            rutinas = []
            for r_w,time_f,days_f,task_fields in getattr(self,"_rutinas_widgets",[]):
                if not r_w.isHidden():
                    tasks = [tf.text().strip() for tf in task_fields if tf.text().strip()]
                    rutinas.append({"time":time_f.text().strip(),"days":days_f.text().strip(),"tasks":tasks})
            if rutinas: _prefs["routines"] = rutinas

            # Guardar dispositivos
            devs = []
            for d_w,name_f,id_f,tipo_f in getattr(self,"_devs_widgets",[]):
                if not d_w.isHidden() and name_f.text().strip():
                    devs.append({"nombre":name_f.text().strip(),"id":id_f.text().strip(),"tipo":tipo_f.text().strip()})
            if devs: _prefs["devices"] = devs

            save_prefs(_prefs)

            # Actualizar API key
            new_key = self._api_key_field.text().strip()
            if new_key:
                try:
                    d = json.loads(API_FILE.read_text(encoding="utf-8")) if API_FILE.exists() else {}
                    d["gemini_api_key"] = new_key
                    API_FILE.write_text(json.dumps(d,indent=4),encoding="utf-8")
                except Exception: pass

            # Aplicar call_me al prompt dinamicamente
            self._update_prompt_call_me(_prefs["call_me"], _prefs.get("personality_idx",0))
            # Reconectar JARVIS en vivo
            self._trigger_reconnect()

        except Exception as e:
            print(f"[Settings] Error guardando: {e}")
        self._close()

    def _trigger_reconnect(self):
        """Notifica a JARVIS que reconecte con la nueva configuración."""
        try:
            # Buscar MainWindow y llamar a su on_reconnect callback
            parent = self.parent()
            while parent:
                if hasattr(parent, 'on_reconnect'):
                    parent.on_reconnect()
                    break
                parent = parent.parent() if hasattr(parent, 'parent') else None
        except Exception as e:
            print(f"[Settings] Error triggering reconnect: {e}")

    def _update_prompt_call_me(self, call_me: str, personality_idx: int):
        """Actualiza como JARVIS llama al usuario en el prompt."""
        try:
            prompt_path = BASE_DIR / "core" / "prompt.txt"
            if not prompt_path.exists(): return
            txt = prompt_path.read_text(encoding="utf-8")
            personalities = ["ironman","formal","amigable","serio","barrio"]
            personality = personalities[personality_idx] if personality_idx < len(personalities) else "ironman"
            _prefs["personality"] = personality
            _prefs["call_me"] = call_me
            save_prefs(_prefs)
        except Exception as e:
            print(f"[Settings] Error actualizando prompt: {e}")

    def _send_feedback(self, dest: str):
        """Envía el mensaje directo via SMTP a Gmail — sin cliente de correo."""

        # Proteger contra crash si el tab Feedback nunca se abrió
        if not hasattr(self, '_fb_tipo') or not hasattr(self, '_fb_msg'):
            print("[Feedback] Tab Feedback no inicializado — abre Ajustes → Feedback primero")
            return

        tipo   = self._fb_tipo.currentText().strip()
        asunto = self._fb_asunto.text().strip() if hasattr(self, '_fb_asunto') else ""
        cuerpo = self._fb_msg.toPlainText().strip()

        # ── Validar ───────────────────────────────────────────────────────────
        if not cuerpo:
            self._fb_status.setStyleSheet(f"color:{C.RED};background:transparent;")
            self._fb_status.setText("⚠ Escribe un mensaje antes de enviar.")
            return

        if not asunto:
            asunto = tipo or "Feedback JARVIS Mark XXXIX"

        # ── Deshabilitar botón mientras envía ─────────────────────────────────
        self._fb_status.setStyleSheet(f"color:{C.ACC2};background:transparent;")
        self._fb_status.setText("⏳ Enviando...")

        # ── Enviar en hilo separado para no congelar la UI ───────────────────
        def _do_send():
            import smtplib, ssl
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart

            # Credenciales reales de Gmail
            SMTP_USER = "programatec108@gmail.com"
            SMTP_PASS = "vawm rscw xcsx xwdp"

            asunto_completo = f"[JARVIS MARK XXXIX] {tipo} — {asunto}"
            cuerpo_completo = (
                f"TIPO: {tipo}\n"
                f"{'='*50}\n\n"
                f"{cuerpo}\n\n"
                f"{'='*50}\n"
                f"Enviado desde : JARVIS Mark XXXIX\n"
                f"Versión       : Build 2026\n"
                f"OS del usuario: {_OS}\n"
            )

            try:
                msg = MIMEMultipart()
                msg["From"]    = SMTP_USER
                msg["To"]      = dest
                msg["Subject"] = asunto_completo
                msg.attach(MIMEText(cuerpo_completo, "plain", "utf-8"))

                ctx = ssl.create_default_context()
                with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ctx) as server:
                    server.login(SMTP_USER, SMTP_PASS)
                    server.sendmail(SMTP_USER, dest, msg.as_string())

                # ── Éxito — actualizar UI desde hilo principal ────────────────
                def _ok():
                    self._fb_status.setStyleSheet(f"color:{C.GREEN};background:transparent;")
                    self._fb_status.setText("✓ ¡Mensaje enviado! Lo revisaré pronto.")
                    self._fb_asunto.clear()
                    self._fb_msg.clear()
                    QTimer.singleShot(6000, lambda: self._fb_status.setText(""))
                QTimer.singleShot(0, _ok)
                print(f"[Feedback] ✓ Enviado a {dest}")

            except smtplib.SMTPAuthenticationError:
                def _err_auth():
                    self._fb_status.setStyleSheet(f"color:{C.RED};background:transparent;")
                    self._fb_status.setText("⚠ Error de autenticación SMTP. Contacta al desarrollador.")
                QTimer.singleShot(0, _err_auth)
                print("[Feedback] Error: autenticación SMTP falló")

            except smtplib.SMTPException as e:
                def _err_smtp(err=str(e)):
                    self._fb_status.setStyleSheet(f"color:{C.RED};background:transparent;")
                    self._fb_status.setText(f"⚠ Error SMTP: {err[:80]}")
                QTimer.singleShot(0, _err_smtp)
                print(f"[Feedback] Error SMTP: {e}")

            except OSError as e:
                def _err_net(err=str(e)):
                    self._fb_status.setStyleSheet(f"color:{C.RED};background:transparent;")
                    self._fb_status.setText("⚠ Sin conexión a internet. Verifica tu red.")
                QTimer.singleShot(0, _err_net)
                print(f"[Feedback] Error de red: {e}")

            except Exception as e:
                def _err_gen(err=str(e)):
                    self._fb_status.setStyleSheet(f"color:{C.RED};background:transparent;")
                    self._fb_status.setText(f"⚠ Error inesperado: {err[:80]}")
                QTimer.singleShot(0, _err_gen)
                print(f"[Feedback] Error: {e}")

        threading.Thread(target=_do_send, daemon=True).start()

    def _close(self):
        self.closed.emit()
        self.hide()


# ── Setup Overlay ─────────────────────────────────────────────────────────────
class SetupOverlay(QWidget):
    done = pyqtSignal(str,str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground,True)
        self.setStyleSheet(f"""
            SetupOverlay{{
                background:rgba(0,6,10,250);
                border:2px solid {C.BORDER_B};
                border-radius:10px;
            }}
        """)
        detected = {"darwin":"mac","windows":"windows"}.get(_OS.lower(),"linux")
        self._sel_os = detected
        self._step = 0  # 0=bienvenida, 1=key

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30,24,30,24)
        layout.setSpacing(10)

        def _lbl(txt,fs=9,bold=False,color=C.PRI,align=Qt.AlignmentFlag.AlignCenter):
            w=QLabel(txt); w.setAlignment(align)
            w.setFont(QFont("Courier New",fs,QFont.Weight.Bold if bold else QFont.Weight.Normal))
            w.setStyleSheet(f"color:{color};background:transparent;")
            w.setWordWrap(True)
            return w

        # ── TITULO ──
        layout.addWidget(_lbl("⚡  J.A.R.V.I.S",18,True,C.PRI))
        layout.addWidget(_lbl("Bienvenido. Antes de comenzar necesitas",9,color=C.TEXT_DIM))
        layout.addWidget(_lbl("una clave gratuita de Google (tarda 2 min)",9,color=C.TEXT_DIM))
        layout.addSpacing(6)

        sep=QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color:{C.BORDER};"); layout.addWidget(sep)
        layout.addSpacing(4)

        # ── PASOS ──
        pasos_w = QWidget(); pasos_w.setStyleSheet("background:transparent;")
        pasos_lay = QVBoxLayout(pasos_w); pasos_lay.setSpacing(6); pasos_lay.setContentsMargins(0,0,0,0)

        pasos = [
            ("1", "Ve a aistudio.google.com", C.ACC2),
            ("2", "Inicia sesión con tu cuenta de Gmail", C.ACC2),
            ("3", "Haz clic en el botón  ⊕ Crear clave de API", C.ACC2),
            ("4", "Escribe un nombre (ej: JARVIS) y elige 'Default Gemini Project'", C.ACC2),
            ("5", "Haz clic en el botón  Crear clave", C.ACC2),
            ("6", "Copia la clave generada y pégala abajo", C.GREEN),
        ]
        for num,txt,col in pasos:
            row = QHBoxLayout()
            n = QLabel(num)
            n.setFixedSize(22,22)
            n.setAlignment(Qt.AlignmentFlag.AlignCenter)
            n.setFont(QFont("Courier New",9,QFont.Weight.Bold))
            n.setStyleSheet(f"color:#000;background:{col};border-radius:11px;")
            row.addWidget(n)
            t = QLabel(txt)
            t.setFont(QFont("Courier New",9))
            t.setStyleSheet(f"color:{C.TEXT};background:transparent;")
            row.addWidget(t); row.addStretch()
            pasos_lay.addLayout(row)

        layout.addWidget(pasos_w)

        # Boton abrir Google
        open_btn = QPushButton("🌐  Abrir aistudio.google.com")
        open_btn.setFixedHeight(32)
        open_btn.setFont(QFont("Courier New",9,QFont.Weight.Bold))
        open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        open_btn.setStyleSheet(f"""
            QPushButton{{background:#001a2e;color:{C.PRI};border:1px solid {C.PRI_DIM};border-radius:4px;}}
            QPushButton:hover{{background:#002a40;border:1px solid {C.PRI};}}
        """)
        open_btn.clicked.connect(lambda: __import__('webbrowser').open("https://aistudio.google.com/apikey"))
        layout.addWidget(open_btn)

        sep2=QFrame(); sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet(f"color:{C.BORDER};"); layout.addWidget(sep2)

        layout.addWidget(_lbl("PEGA TU CLAVE AQUÍ:",8,True,C.TEXT_DIM,Qt.AlignmentFlag.AlignLeft))
        self._key_input=QLineEdit()
        self._key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._key_input.setPlaceholderText("AIzaSy... (pega tu clave de Google aquí)")
        self._key_input.setFont(QFont("Courier New",10))
        self._key_input.setFixedHeight(36)
        self._key_input.setStyleSheet(f"""
            QLineEdit{{
                background:#000d12;color:{C.WHITE};
                border:1px solid {C.BORDER};border-radius:4px;padding:4px 10px;
            }}
            QLineEdit:focus{{border:1px solid {C.PRI};}}
        """)
        layout.addWidget(self._key_input)

        # Error label
        self._err_lbl = QLabel("⚠ Por favor pega tu clave antes de continuar")
        self._err_lbl.setFont(QFont("Courier New",8))
        self._err_lbl.setStyleSheet(f"color:{C.RED};background:transparent;")
        self._err_lbl.hide()
        layout.addWidget(self._err_lbl)

        # Boton iniciar
        init_btn=QPushButton("▸  INICIAR JARVIS")
        init_btn.setFixedHeight(40)
        init_btn.setFont(QFont("Courier New",11,QFont.Weight.Bold))
        init_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        init_btn.setStyleSheet(f"""
            QPushButton{{
                background:{C.PRI_GHO};color:{C.PRI};
                border:2px solid {C.PRI};border-radius:5px;
                letter-spacing:2px;
            }}
            QPushButton:hover{{background:#002a40;}}
        """)
        init_btn.clicked.connect(self._submit)
        layout.addWidget(init_btn)

        layout.addWidget(_lbl("La clave es gratuita · No compartimos tus datos",7,color=C.TEXT_DIM))

    def _submit(self):
        key=self._key_input.text().strip()
        if not key or not key.startswith("AIza"):
            self._err_lbl.show()
            self._key_input.setStyleSheet(
                self._key_input.styleSheet()+f"border:1px solid {C.RED};"
            )
            return
        self._err_lbl.hide()
        self.done.emit(key, self._sel_os)

    # Mantener _sel para compatibilidad
    def _sel(self, key):
        self._sel_os = key


# ── MainWindow ────────────────────────────────────────────────────────────────


class _MiniHudCanvas(QWidget):
    """Canvas mini que dibuja el reloj, estado y anillos del HUD."""

    def __init__(self, hud: HudCanvas, parent=None):
        super().__init__(parent)
        self._hud = hud
        self.setStyleSheet("background:transparent;")
        self._tmr = QTimer(self)
        self._tmr.timeout.connect(self.update)
        self._tmr.start(100)

    def paintEvent(self, _):
        from time import strftime
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        cx, cy = W / 2, H / 2
        fw = min(W, H) * 0.9

        # Fondo transparente
        p.fillRect(self.rect(), QColor(0, 0, 0, 0))

        hud = self._hud
        col_main = qcol(C.MUTED_C if hud.muted else C.PRI)

        # Anillos externos
        for i, (r_frac, alpha) in enumerate([(0.48,60),(0.38,40),(0.28,30)]):
            r = fw * r_frac
            a = max(0, min(255, int(hud._halo * 0.06 * (3-i))))
            p.setPen(QPen(qcol(C.MUTED_C if hud.muted else C.PRI, a), 1))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QRectF(cx-r, cy-r, r*2, r*2))

        # Arcos giratorios mini
        for idx, (r_frac, arc_l, gap) in enumerate([(0.44,90,60),(0.34,60,45)]):
            ring_r = fw * r_frac
            base = hud._rings[idx]
            a = max(0, min(255, int(hud._halo * (0.9 - idx*0.2))))
            p.setPen(QPen(qcol(C.MUTED_C if hud.muted else C.PRI, a), 1.5))
            p.setBrush(Qt.BrushStyle.NoBrush)
            angle = base
            rect = QRectF(cx-ring_r, cy-ring_r, ring_r*2, ring_r*2)
            while angle < base + 360:
                p.drawArc(rect, int(angle*16), int(arc_l*16))
                angle += arc_l + gap

        # Circulo central
        r_inner = fw * 0.22
        p.setPen(QPen(col_main, 1.5))
        p.setBrush(QBrush(qcol("#020c1a")))
        p.drawEllipse(QRectF(cx-r_inner, cy-r_inner, r_inner*2, r_inner*2))

        # Reloj grande en el centro
        from time import strftime
        clock_fmt = "%H:%M:%S"
        clock_str = strftime(clock_fmt)
        p.setFont(QFont("Courier New", 11, QFont.Weight.Bold))
        p.setPen(QPen(col_main, 1))
        p.drawText(QRectF(0, cy-18, W, 22), Qt.AlignmentFlag.AlignCenter, clock_str)

        # Fecha pequeña bajo el reloj
        date_str = strftime("%a %d %b")
        p.setFont(QFont("Courier New", 7))
        p.setPen(QPen(qcol(C.TEXT_DIM), 1))
        p.drawText(QRectF(0, cy+6, W, 14), Qt.AlignmentFlag.AlignCenter, date_str)

        # Estado bajo la fecha
        if hud.muted:          estado = "⊘ SILENCIADO"
        elif hud.speaking:     estado = "● HABLANDO"
        elif hud.state in ("THINKING","PROCESSING"): estado = "◈ PENSANDO"
        elif hud.state == "LISTENING": estado = "● ESCUCHANDO"
        else:                  estado = "◇ EN ESPERA"

        col_estado = (qcol(C.MUTED_C) if hud.muted else
                      qcol(C.ACC) if hud.speaking else
                      qcol(C.ACC2) if hud.state in ("THINKING","PROCESSING") else
                      qcol(C.GREEN) if hud.state=="LISTENING" else qcol(C.PRI))

        p.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        p.setPen(QPen(col_estado, 1))
        p.drawText(QRectF(0, cy+20, W, 16), Qt.AlignmentFlag.AlignCenter, estado)

        # Ondas de voz mini en la parte inferior
        if hud.speaking or hud.state=="LISTENING":
            import math, random
            wy = H - 14
            N, bw = 20, 5
            wx0 = (W - N*bw) / 2
            for i in range(N):
                if hud.speaking:
                    hgt = random.randint(2,10)
                    cl = qcol(C.PRI, 180)
                else:
                    hgt = int(2 + 2*math.sin(hud._tick*0.1 + i*0.5))
                    cl = qcol(C.BORDER_B, 150)
                p.fillRect(QRectF(wx0+i*bw, wy-hgt, bw-1, hgt), cl)

class _MiniWidget(QWidget):
    """Widget flotante mini 250x250 con HUD, estado y log."""

    def __init__(self, main_win, parent=None):
        super().__init__(parent)
        self._main = main_win
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(250,270)
        self._drag_pos = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(8,8,8,8)
        lay.setSpacing(4)

        # Fondo
        bg = QWidget(self)
        bg.setObjectName("miniBg")
        bg.setStyleSheet(f"""
            QWidget#miniBg{{
                background:rgba(0,6,10,230);
                border:1px solid {C.BORDER_B};
                border-radius:12px;
            }}
        """)
        bg_lay = QVBoxLayout(bg)
        bg_lay.setContentsMargins(6,6,6,6)
        bg_lay.setSpacing(4)

        # Header mini
        hdr = QHBoxLayout()
        title = QLabel("J.A.R.V.I.S")
        title.setFont(QFont("Courier New",8,QFont.Weight.Bold))
        title.setStyleSheet(f"color:{C.PRI};background:transparent;")
        hdr.addWidget(title)
        hdr.addStretch()
        self._clock_lbl = QLabel("00:00")
        self._clock_lbl.setFont(QFont("Courier New",8))
        self._clock_lbl.setStyleSheet(f"color:{C.PRI};background:transparent;")
        hdr.addWidget(self._clock_lbl)
        # Boton restaurar
        rest_btn = QPushButton("⊡")
        rest_btn.setFixedSize(18,18)
        rest_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        rest_btn.setStyleSheet(f"QPushButton{{background:transparent;color:{C.TEXT_DIM};border:none;font-size:10pt;}}"
                               f"QPushButton:hover{{color:{C.PRI};}}")
        rest_btn.clicked.connect(main_win._toggle_mini_mode)
        hdr.addWidget(rest_btn)
        bg_lay.addLayout(hdr)

        # Mini HUD canvas propio
        self._mini_hud = _MiniHudCanvas(main_win.hud)
        self._mini_hud.setFixedHeight(155)
        bg_lay.addWidget(self._mini_hud, stretch=1)

        # Log mini
        self._log_mini = QTextEdit()
        self._log_mini.setReadOnly(True)
        self._log_mini.setFixedHeight(52)
        self._log_mini.setFont(QFont("Courier New",7))
        self._log_mini.setStyleSheet(f"""
            QTextEdit{{
                background:rgba(0,13,20,180);color:{C.TEXT_DIM};
                border:1px solid {C.BORDER};border-radius:4px;padding:3px;
            }}
            QScrollBar:vertical{{width:4px;background:transparent;}}
            QScrollBar::handle:vertical{{background:{C.BORDER};border-radius:2px;}}
        """)
        bg_lay.addWidget(self._log_mini)

        # Mute button mini
        self._mute_mini = QPushButton("🎙 ACTIVO")
        self._mute_mini.setFixedHeight(22)
        self._mute_mini.setFont(QFont("Courier New",7,QFont.Weight.Bold))
        self._mute_mini.setCursor(Qt.CursorShape.PointingHandCursor)
        self._mute_mini.setStyleSheet(f"QPushButton{{background:#00140a;color:{C.GREEN};border:1px solid {C.GREEN_D};border-radius:3px;}}"
                                      f"QPushButton:hover{{background:#001f10;}}")
        self._mute_mini.clicked.connect(main_win._toggle_mute)
        bg_lay.addWidget(self._mute_mini)

        lay.addWidget(bg)

        # Timer para actualizar
        self._tmr = QTimer(self)
        self._tmr.timeout.connect(self._update)
        self._tmr.start(500)

        # Redirigir logs al mini log
        self._orig_write_log = main_win.on_text_command

    def _update(self):
        """Actualiza reloj y estado."""
        from time import strftime
        self._clock_lbl.setText(strftime("%H:%M"))
        # Sync mute button
        if self._main._muted:
            self._mute_mini.setText("🔇 SILENCIADO")
            self._mute_mini.setStyleSheet(f"QPushButton{{background:#140006;color:{C.MUTED_C};border:1px solid {C.MUTED_C};border-radius:3px;}}")
        else:
            self._mute_mini.setText("🎙 ACTIVO")
            self._mute_mini.setStyleSheet(f"QPushButton{{background:#00140a;color:{C.GREEN};border:1px solid {C.GREEN_D};border-radius:3px;}}")

    def add_log(self, text):
        """Agrega texto al log mini."""
        self._log_mini.append(text[-60:] if len(text)>60 else text)
        self._log_mini.verticalScrollBar().setValue(self._log_mini.verticalScrollBar().maximum())

    def paintEvent(self, event):
        """Dibuja el HUD en el contenedor mini."""
        super().paintEvent(event)

    def mousePressEvent(self, e):
        if e.button()==Qt.MouseButton.LeftButton:
            self._drag_pos=e.globalPosition().toPoint()-self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if e.buttons()==Qt.MouseButton.LeftButton and self._drag_pos:
            self.move(e.globalPosition().toPoint()-self._drag_pos)

    def mouseDoubleClickEvent(self, e):
        self._main._toggle_mini_mode()

    def closeEvent(self, e):
        self._main._toggle_mini_mode()


class MainWindow(QMainWindow):
    _log_sig   = pyqtSignal(str)
    _state_sig = pyqtSignal(str)

    def __init__(self, face_path: str):
        super().__init__()
        self.setWindowTitle("J.A.R.V.I.S — MARK XXXIX")
        self.setMinimumSize(_MIN_W,_MIN_H); self.resize(_DEFAULT_W,_DEFAULT_H)
        screen=QApplication.primaryScreen().availableGeometry()
        self.move((screen.width()-_DEFAULT_W)//2,(screen.height()-_DEFAULT_H)//2)
        self.on_text_command=None; self._muted=False; self._current_file: str|None=None
        self._clock_24h = _prefs.get("clock_24h",True)

        central=QWidget(); central.setStyleSheet(f"background:{C.BG};"); self.setCentralWidget(central)
        root=QVBoxLayout(central); root.setContentsMargins(0,0,0,0); root.setSpacing(0)
        root.addWidget(self._build_header())

        body=QHBoxLayout(); body.setContentsMargins(0,0,0,0); body.setSpacing(0)
        self._left_panel=self._build_left_panel(); body.addWidget(self._left_panel,stretch=0)
        self.hud=HudCanvas(face_path)
        self.hud.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Expanding)
        body.addWidget(self.hud,stretch=5)
        self._right_panel=self._build_right_panel(); body.addWidget(self._right_panel,stretch=0)
        root.addLayout(body,stretch=1)
        root.addWidget(self._build_footer())

        # Settings panel (hidden initially)
        self._settings=SettingsPanel(central)
        self._settings.closed.connect(self._on_settings_closed)
        self._settings.hide()

        self._clock_tmr=QTimer(self); self._clock_tmr.timeout.connect(self._tick_clock); self._clock_tmr.start(1000); self._tick_clock()
        self._metric_tmr=QTimer(self); self._metric_tmr.timeout.connect(self._update_metrics); self._metric_tmr.start(2000); self._update_metrics()
        self._log_sig.connect(self._log.append_log)
        self._state_sig.connect(self._apply_state)
        self._overlay: SetupOverlay|None=None
        self._ready=self._check_config()
        if not self._ready: self._show_setup()
        QShortcut(QKeySequence("F4"),self).activated.connect(self._toggle_mute)
        QShortcut(QKeySequence("F11"),self).activated.connect(self._toggle_fullscreen)
        QShortcut(QKeySequence("F2"),self).activated.connect(self._toggle_mini_mode)

        # Animacion de boot al iniciar
        QTimer.singleShot(100, self._animate_boot)

    def _animate_boot(self):
        """Animacion de entrada estilo HUD futurista — elementos uno por uno."""

        def _fade_widget(widget, duration=400, delay=0, slide_from=None):
            """Fade in + slide opcional para un widget."""
            effect = QGraphicsOpacityEffect(widget)
            widget.setGraphicsEffect(effect)
            effect.setOpacity(0)

            anim = QPropertyAnimation(effect, b"opacity")
            anim.setDuration(duration)
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)

            QTimer.singleShot(delay, anim.start)
            # Guardar referencia para evitar garbage collection
            if not hasattr(self, '_boot_anims'):
                self._boot_anims = []
            self._boot_anims.append((anim, effect))

        def _glitch_widget(widget, delay=0):
            """Efecto parpadeo rapido antes del fade."""
            def _do_glitch():
                effect = QGraphicsOpacityEffect(widget)
                widget.setGraphicsEffect(effect)
                blinks = [0, 1, 0, 0, 1, 0, 1, 1]
                for i, val in enumerate(blinks):
                    QTimer.singleShot(i * 60, lambda v=val, e=effect: e.setOpacity(v))
                QTimer.singleShot(len(blinks) * 60, lambda: _fade_widget(widget, 300, 0))
            QTimer.singleShot(delay, _do_glitch)

        def _fill_bar(bar, delay=0):
            """Anima el llenado de una barra de progreso."""
            target = bar._value
            bar.set_value(0, bar._text)
            def _animate():
                steps = 20
                for i in range(steps + 1):
                    QTimer.singleShot(i * 20, lambda v=target*i//steps, t=bar._text:
                        bar.set_value(v, t))
            QTimer.singleShot(delay, _animate)

        def _type_log(text, delay=0):
            """Simula escritura de texto en el log."""
            QTimer.singleShot(delay, lambda: self._log_sig.emit(text))

        # ── SECUENCIA DE ANIMACION ────────────────────────────────────────
        # Ocultar todo al inicio
        for w in [self._left_panel, self.hud, self._right_panel]:
            eff = QGraphicsOpacityEffect(w)
            w.setGraphicsEffect(eff)
            eff.setOpacity(0)

        # 1. HUD central — primero, con glitch
        _glitch_widget(self.hud, delay=200)

        # 2. Panel izquierdo (SYS MONITOR) — desliza desde la izquierda
        QTimer.singleShot(900, lambda: _fade_widget(self._left_panel, 500))

        # 3. Barras del monitor se llenan secuencialmente
        bars = [self._bar_cpu, self._bar_mem, self._bar_net, self._bar_gpu, self._bar_tmp]
        for i, bar in enumerate(bars):
            _fill_bar(bar, delay=1100 + i * 180)

        # 4. Panel derecho (LOG) — fade in
        QTimer.singleShot(1400, lambda: _fade_widget(self._right_panel, 500))

        # 5. Log escribe linea por linea efecto typing
        boot_logs = [
            (1600, "SYS: ▸ Iniciando protocolo Mark XXXIX..."),
            (2000, "SYS: ▸ Motor de IA Gemini 2.5... OK"),
            (2300, "SYS: ▸ Micrófono calibrado... OK"),
            (2600, "SYS: ▸ Dispositivos IoT sincronizados... OK"),
            (2900, "SYS: ▸ Memoria del usuario cargada... OK"),
            (3200, "SYS: ▸ Detector de voz activo... OK"),
            (3500, "SYS: ━━━━ TODOS LOS SISTEMAS OPERATIVOS ━━━━"),
            (3800, "SYS: JARVIS en espera. Di 'Jarvis' para activar."),
        ]
        for delay, msg in boot_logs:
            _type_log(msg, delay)

        # 6. Estado: encender indicadores uno por uno (strobe)
        QTimer.singleShot(3000, self._animate_status_lights)

    def _animate_status_lights(self):
        """Enciende los indicadores de estado uno por uno con destello."""
        status_labels = []
        # Buscar labels de estado en el panel izquierdo
        for child in self._left_panel.findChildren(QLabel):
            txt = child.text()
            if any(x in txt for x in ["AI CORE", "MIC", "IOT", "GEMINI", "OLLAMA"]):
                status_labels.append(child)

        for i, lbl in enumerate(status_labels):
            delay = i * 150
            orig_style = lbl.styleSheet()
            def _strobe(l=lbl, s=orig_style):
                # Flash blanco rapido luego vuelve al color
                l.setStyleSheet(f"color:#ffffff;background:transparent;")
                QTimer.singleShot(80,  lambda: l.setStyleSheet(f"color:#000000;background:transparent;"))
                QTimer.singleShot(140, lambda: l.setStyleSheet(f"color:#ffffff;background:transparent;"))
                QTimer.singleShot(200, lambda: l.setStyleSheet(s))
            QTimer.singleShot(delay, _strobe)

    def _toggle_fullscreen(self):
        if self.isFullScreen(): self.showNormal()
        else: self.showFullScreen()

    def resizeEvent(self,event):
        super().resizeEvent(event)
        cw=self.centralWidget()
        if self._overlay and self._overlay.isVisible():
            ow,oh=460,390
            self._overlay.setGeometry((cw.width()-ow)//2,(cw.height()-oh)//2,ow,oh)
        if hasattr(self,'_settings') and self._settings.isVisible():
            sw,sh=720,560
            self._settings.setGeometry((cw.width()-sw)//2,(cw.height()-sh)//2,sw,sh)

    def _show_settings(self):
        cw=self.centralWidget(); sw,sh=720,560
        self._settings.setGeometry((cw.width()-sw)//2,(cw.height()-sh)//2,sw,sh)
        self._settings.show(); self._settings.raise_()

    def _on_settings_closed(self):
        global _prefs; _prefs=load_prefs()
        self._clock_24h=_prefs.get("clock_24h",True)

    def _update_metrics(self):
        snap=_metrics.snapshot()
        self._bar_cpu.set_value(snap["cpu"],f"{snap['cpu']:.0f}%")
        self._bar_mem.set_value(snap["mem"],f"{snap['mem']:.0f}%")
        net=snap["net"]
        net_str=f"{net*1024:.0f}KB/s" if net<1.0 else f"{net:.1f}MB/s"
        self._bar_net.set_value(min(100,net*10),net_str)
        gpu=snap["gpu"]
        self._bar_gpu.set_value(gpu if gpu>=0 else 0,"N/A" if gpu<0 else f"{gpu:.0f}%")
        tmp=snap["tmp"]
        self._bar_tmp.set_value(min(100,(tmp/100)*100) if tmp>=0 else 0,"N/A" if tmp<0 else f"{tmp:.0f}°C")
        try:
            elapsed=time.time()-psutil.boot_time()
            h,m=int(elapsed//3600),int((elapsed%3600)//60)
            self._uptime_lbl.setText(f"UP  {h:02d}:{m:02d}")
        except Exception: self._uptime_lbl.setText("UP  --:--")
        try: self._proc_lbl.setText(f"PROC  {len(psutil.pids())}")
        except Exception: self._proc_lbl.setText("PROC  --")
        # Pasar métricas al HUD central para mostrarlas en el canvas
        try:
            cpu_i = int(snap["cpu"]); mem_i = int(snap["mem"])
            if hasattr(self, '_hud'):
                self._hud.update_metrics(cpu_i, mem_i, net_str)
        except Exception:
            pass

    def _build_header(self) -> QWidget:
        w = QWidget(); w.setFixedHeight(64)
        w.setStyleSheet(
            f"background:qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            f"stop:0 {C.DARKER},stop:1 {C.DARK});"
            f"border-bottom:1px solid {C.BORDER_B};"
        )
        lay = QHBoxLayout(w); lay.setContentsMargins(18, 0, 18, 0); lay.setSpacing(0)

        # ── Columna izquierda: versión + modelo ──────────────────────────────
        left_col = QVBoxLayout(); left_col.setSpacing(2)
        ver_lbl = QLabel("◈  MARK XXXIX")
        ver_lbl.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        ver_lbl.setStyleSheet(f"color:{C.PRI};background:transparent;letter-spacing:2px;")
        left_col.addWidget(ver_lbl)
        model_lbl = QLabel("GEMINI 2.5 FLASH  ·  LIVE API")
        model_lbl.setFont(QFont("Courier New", 7))
        model_lbl.setStyleSheet(f"color:{C.TEXT_DIM};background:transparent;")
        left_col.addWidget(model_lbl)
        lay.addLayout(left_col)

        lay.addStretch()

        # ── Centro: título principal ─────────────────────────────────────────
        mid = QVBoxLayout(); mid.setSpacing(0)
        title = QLabel("J.A.R.V.I.S")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Courier New", 20, QFont.Weight.Bold))
        title.setStyleSheet(
            f"color:{C.PRI};background:transparent;"
            f"letter-spacing:6px;"
        )
        mid.addWidget(title)
        sub = QLabel("Just A Rather Very Intelligent System  ·  Jose Antonio Carbajal Quintanar")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setFont(QFont("Courier New", 6))
        sub.setStyleSheet(f"color:{C.TEXT_FADE};background:transparent;letter-spacing:1px;")
        mid.addWidget(sub)
        lay.addLayout(mid)

        lay.addStretch()

        # ── Columna derecha: reloj + fecha ───────────────────────────────────
        right_col = QVBoxLayout(); right_col.setSpacing(1); right_col.setContentsMargins(0, 0, 0, 0)
        self._clock_lbl = QLabel("00:00:00")
        self._clock_lbl.setFont(QFont("Courier New", 16, QFont.Weight.Bold))
        self._clock_lbl.setStyleSheet(f"color:{C.PRI};background:transparent;")
        self._clock_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        right_col.addWidget(self._clock_lbl)
        self._date_lbl = QLabel("")
        self._date_lbl.setFont(QFont("Courier New", 7))
        self._date_lbl.setStyleSheet(f"color:{C.TEXT_DIM};background:transparent;")
        self._date_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        right_col.addWidget(self._date_lbl)
        lay.addLayout(right_col)

        # ── Botón ajustes compacto en header ────────────────────────────────
        lay.addSpacing(14)
        hdr_settings = QPushButton("⚙")
        hdr_settings.setFixedSize(32, 32)
        hdr_settings.setCursor(Qt.CursorShape.PointingHandCursor)
        hdr_settings.setToolTip("Ajustes")
        hdr_settings.setFont(QFont("Courier New", 12))
        hdr_settings.setStyleSheet(
            f"QPushButton{{background:transparent;color:{C.ORANGE_D};border:1px solid {C.BORDER};border-radius:4px;}}"
            f"QPushButton:hover{{color:{C.ORANGE};border:1px solid {C.ORANGE_D};background:#0d0800;}}"
        )
        hdr_settings.clicked.connect(self._show_settings)
        lay.addWidget(hdr_settings)
        return w

    def _tick_clock(self):
        fmt = "%H:%M:%S" if _prefs.get("clock_24h",True) else "%I:%M:%S %p"
        self._clock_lbl.setText(time.strftime(fmt))
        self._date_lbl.setText(time.strftime("%a %d %b %Y"))

    def _build_left_panel(self) -> QWidget:
        w = QWidget(); w.setFixedWidth(_LEFT_W)
        w.setStyleSheet(
            f"background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            f"stop:0 {C.DARKER},stop:1 {C.DARK});"
            f"border-right:1px solid {C.BORDER};"
        )
        lay = QVBoxLayout(w); lay.setContentsMargins(10, 12, 10, 12); lay.setSpacing(5)

        # ── Sección SYS MONITOR ──────────────────────────────────────────────
        def _sec_hdr(txt: str) -> QLabel:
            l = QLabel(txt)
            l.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
            l.setStyleSheet(
                f"color:{C.PRI};background:transparent;"
                f"border-bottom:1px solid {C.BORDER};"
                f"padding-bottom:4px;padding-top:2px;letter-spacing:2px;"
            )
            return l

        lay.addWidget(_sec_hdr("SYS MONITOR"))
        lay.addSpacing(2)

        self._bar_cpu = MetricBar("CPU", C.PRI)
        self._bar_mem = MetricBar("MEM", C.ACC2)
        self._bar_net = MetricBar("NET", C.GREEN)
        self._bar_gpu = MetricBar("GPU", C.ACC)
        self._bar_tmp = MetricBar("TMP", "#ff6688")
        for bar in [self._bar_cpu, self._bar_mem, self._bar_net, self._bar_gpu, self._bar_tmp]:
            lay.addWidget(bar)

        lay.addSpacing(6)

        # ── Panel info compacto (uptime, procesos, OS) ───────────────────────
        info_panel = QWidget()
        info_panel.setStyleSheet(
            f"background:{C.PANEL2};border:1px solid {C.BORDER_A};"
            f"border-radius:5px;"
        )
        ip_lay = QVBoxLayout(info_panel); ip_lay.setContentsMargins(8, 6, 8, 6); ip_lay.setSpacing(4)

        def _info_row(ico: str, lbl_attr: str, col: str, default_txt: str) -> QLabel:
            row = QHBoxLayout(); row.setSpacing(4)
            ic = QLabel(ico); ic.setFont(QFont("Courier New", 7))
            ic.setStyleSheet(f"color:{C.BORDER_B};background:transparent;border:none;")
            row.addWidget(ic)
            val = QLabel(default_txt)
            val.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
            val.setStyleSheet(f"color:{col};background:transparent;border:none;")
            row.addWidget(val); row.addStretch()
            setattr(self, lbl_attr, val)
            container = QWidget(); container.setStyleSheet("background:transparent;")
            container.setLayout(row)
            ip_lay.addWidget(container)
            return val

        _info_row("⏱", "_uptime_lbl", C.GREEN, "UP  --:--")
        _info_row("⚙", "_proc_lbl",   C.TEXT_MED, "PROC  --")
        os_name = {"Windows": "WIN 11", "Darwin": "macOS", "Linux": "LINUX"}.get(_OS, _OS.upper())
        os_lbl = QLabel(f"OS   {os_name}"); os_lbl.setFont(QFont("Courier New", 8))
        os_lbl.setStyleSheet(f"color:{C.ACC2};background:transparent;border:none;")
        ip_lay.addWidget(os_lbl)
        lay.addWidget(info_panel)

        lay.addSpacing(6)

        # ── Estado JARVIS ────────────────────────────────────────────────────
        lay.addWidget(_sec_hdr("ESTADO"))
        lay.addSpacing(2)

        estado_panel = QWidget()
        estado_panel.setStyleSheet(
            f"background:{C.PANEL2};border:1px solid {C.BORDER_A};border-radius:5px;"
        )
        ep_lay = QVBoxLayout(estado_panel); ep_lay.setContentsMargins(8, 6, 8, 6); ep_lay.setSpacing(3)

        for txt, col in [
            ("AI CORE",   C.GREEN),
            ("MIC",       C.GREEN),
            ("IOT",       C.GREEN),
            ("GEMINI 2.5", C.ORANGE),
            ("OLLAMA",    C.PRI_DIM),
        ]:
            row = QHBoxLayout(); row.setSpacing(5)
            dot = QLabel("●"); dot.setFont(QFont("Courier New", 8))
            dot.setStyleSheet(f"color:{col};background:transparent;border:none;")
            lbl = QLabel(txt); lbl.setFont(QFont("Courier New", 7))
            lbl.setStyleSheet(f"color:{C.TEXT_DIM};background:transparent;border:none;")
            row.addWidget(dot); row.addWidget(lbl); row.addStretch()
            # badge "OK"
            ok = QLabel("OK"); ok.setFont(QFont("Courier New", 6, QFont.Weight.Bold))
            ok.setStyleSheet(
                f"color:{col};background:transparent;border:1px solid {col};"
                f"border-radius:2px;padding:0 3px;border:none;"
            )
            row.addWidget(ok)
            rw = QWidget(); rw.setStyleSheet("background:transparent;"); rw.setLayout(row)
            ep_lay.addWidget(rw)
        lay.addWidget(estado_panel)

        lay.addStretch()
        return w

    def _build_right_panel(self) -> QWidget:
        w = QWidget(); w.setFixedWidth(_RIGHT_W)
        w.setStyleSheet(
            f"background:qlineargradient(x1:1,y1:0,x2:0,y2:0,"
            f"stop:0 {C.DARKER},stop:1 {C.DARK});"
            f"border-left:1px solid {C.BORDER};"
        )
        lay = QVBoxLayout(w); lay.setContentsMargins(10, 12, 10, 10); lay.setSpacing(6)

        def _sec_hdr(txt: str) -> QLabel:
            l = QLabel(txt)
            l.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
            l.setStyleSheet(
                f"color:{C.PRI};background:transparent;"
                f"border-bottom:1px solid {C.BORDER};"
                f"padding-bottom:4px;letter-spacing:2px;"
            )
            return l

        # ── Activity Log ─────────────────────────────────────────────────────
        lay.addWidget(_sec_hdr("ACTIVITY LOG"))
        self._log = LogWidget()
        self._log.setMinimumHeight(200)
        lay.addWidget(self._log, stretch=1)

        # ── Separador ────────────────────────────────────────────────────────
        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color:{C.BORDER};margin:0;"); lay.addWidget(sep)

        # ── Accesos rápidos ──────────────────────────────────────────────────
        lay.addWidget(_sec_hdr("ACCESOS RÁPIDOS"))

        _QUICK_BTNS = [
            ("💡", "Luces",
             C.ACC2, "#1a1400",
             "lista mis dispositivos de luz conectados y pregúntame cuál encender"),
            ("🎵", "Música",
             C.PURPLE, "#0e0014",
             "pon música"),
            ("🗓", "Reservaciones",
             C.GREEN, C.GREEN_GHO,
             "quiero hacer una reservación, puede ser vuelo, restaurante u hotel, ayúdame"),
        ]

        sc_vlay = QVBoxLayout(); sc_vlay.setSpacing(6); sc_vlay.setContentsMargins(0, 2, 0, 2)
        for ico, label, col, bg, cmd in _QUICK_BTNS:
            btn = QPushButton(f"  {ico}   {label}")
            btn.setFixedHeight(38)
            btn.setFont(QFont("Courier New", 10, QFont.Weight.Bold))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                f"QPushButton{{background:{bg};color:{col};"
                f"border:1px solid {col}33;border-radius:5px;"
                f"text-align:left;padding:0 10px;}}"
                f"QPushButton:hover{{border:1px solid {col};background:{bg}cc;}}"
                f"QPushButton:pressed{{background:{C.DARKER};}}"
            )
            btn.clicked.connect(lambda _, c=cmd: self._quick_cmd(c))
            sc_vlay.addWidget(btn)
        lay.addLayout(sc_vlay)

        sep3 = QFrame(); sep3.setFrameShape(QFrame.Shape.HLine)
        sep3.setStyleSheet(f"color:{C.BORDER};margin:0;"); lay.addWidget(sep3)

        # ── Input de comando ─────────────────────────────────────────────────
        lay.addWidget(_sec_hdr("COMANDO"))
        lay.addLayout(self._build_input_row())

        # ── Fila mic + interrupción ──────────────────────────────────────────
        self._mute_btn = QPushButton("🎙  MICRÓFONO ACTIVO")
        self._mute_btn.setFixedHeight(32)
        self._mute_btn.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        self._mute_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._mute_btn.clicked.connect(self._toggle_mute)
        self._style_mute_btn()
        lay.addWidget(self._mute_btn)

        # ── Mini mode + fullscreen ────────────────────────────────────────────
        ctrl_row = QHBoxLayout(); ctrl_row.setSpacing(5)
        fs_btn = QPushButton("⛶  PANTALLA COMPLETA  [F11]")
        fs_btn.setFixedHeight(22); fs_btn.setFont(QFont("Courier New", 7))
        fs_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        fs_btn.setStyleSheet(
            f"QPushButton{{background:transparent;color:{C.TEXT_FADE};"
            f"border:1px solid {C.BORDER};border-radius:3px;}}"
            f"QPushButton:hover{{color:{C.PRI};border:1px solid {C.BORDER_B};}}"
        )
        fs_btn.clicked.connect(self._toggle_fullscreen)
        ctrl_row.addWidget(fs_btn)
        float_btn = QPushButton("⧉ Mini [F2]")
        float_btn.setFixedHeight(22); float_btn.setFont(QFont("Courier New", 7))
        float_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        float_btn.setStyleSheet(
            f"QPushButton{{background:transparent;color:{C.TEXT_FADE};"
            f"border:1px solid {C.BORDER};border-radius:3px;padding:0 5px;}}"
            f"QPushButton:hover{{color:{C.PRI};border:1px solid {C.BORDER_B};}}"
        )
        float_btn.clicked.connect(self._toggle_mini_mode)
        ctrl_row.addWidget(float_btn)
        lay.addLayout(ctrl_row)
        return w

    def _build_input_row(self) -> QHBoxLayout:
        row = QHBoxLayout(); row.setSpacing(6)
        self._input = QLineEdit()
        self._input.setPlaceholderText("  Escribe un comando para JARVIS...")
        self._input.setFont(QFont("Courier New", 9))
        self._input.setFixedHeight(34)
        self._input.setStyleSheet(
            f"QLineEdit{{background:{C.DARKER};color:{C.WHITE};"
            f"border:1px solid {C.BORDER};border-radius:4px;padding:3px 10px;}}"
            f"QLineEdit:focus{{border:1px solid {C.PRI};"
            f"background:#000f1a;}}"
        )
        self._input.returnPressed.connect(self._send)
        row.addWidget(self._input)

        send = QPushButton("▶")
        send.setFixedSize(34, 34)
        send.setFont(QFont("Courier New", 10, QFont.Weight.Bold))
        send.setCursor(Qt.CursorShape.PointingHandCursor)
        send.setToolTip("Enviar [Enter]")
        send.setStyleSheet(
            f"QPushButton{{background:{C.PRI_GHO};color:{C.PRI};"
            f"border:1px solid {C.PRI_DIM};border-radius:4px;}}"
            f"QPushButton:hover{{background:#002a40;border:1px solid {C.PRI};}}"
            f"QPushButton:pressed{{background:{C.DARKER};}}"
        )
        send.clicked.connect(self._send)
        row.addWidget(send)
        return row

    def _build_footer(self) -> QWidget:
        w = QWidget(); w.setFixedHeight(26)
        w.setStyleSheet(
            f"background:{C.DARKER};"
            f"border-top:1px solid {C.BORDER};"
        )
        lay = QHBoxLayout(w); lay.setContentsMargins(16, 0, 16, 0); lay.setSpacing(0)

        def _fl(txt, color=C.TEXT_FADE, bold=False):
            l = QLabel(txt)
            l.setFont(QFont("Courier New", 7, QFont.Weight.Bold if bold else QFont.Weight.Normal))
            l.setStyleSheet(f"color:{color};background:transparent;")
            return l

        def _sep():
            l = QLabel("·"); l.setFont(QFont("Courier New", 7))
            l.setStyleSheet(f"color:{C.BORDER};background:transparent;padding:0 6px;")
            return l

        lay.addWidget(_fl("[F4] Mute"))
        lay.addWidget(_sep())
        lay.addWidget(_fl("[F11] Pantalla Completa"))
        lay.addWidget(_sep())
        lay.addWidget(_fl("[F2] Mini Mode"))
        lay.addStretch()
        lay.addWidget(_fl("◈ J.A.R.V.I.S", C.PRI_DIM, True))
        lay.addWidget(_sep())
        lay.addWidget(_fl("Jose Antonio Carbajal  ·  MARK XXXIX  ·  2026"))
        return w

    def _toggle_mini_mode(self):
        """Alterna entre modo normal y modo flotante mini 250x250."""
        if not hasattr(self,'_mini_mode'): self._mini_mode=False
        if self._mini_mode:
            # Restaurar modo normal
            self._mini_mode=False
            if hasattr(self,'_mini_overlay') and self._mini_overlay:
                self._mini_overlay.hide()
                self._mini_overlay.deleteLater()
                self._mini_overlay=None
            self.setWindowFlags(Qt.WindowType.Window)
            self.resize(_DEFAULT_W,_DEFAULT_H)
            screen=QApplication.primaryScreen().availableGeometry()
            self.move((screen.width()-_DEFAULT_W)//2,(screen.height()-_DEFAULT_H)//2)
            self.show()
        else:
            # Activar modo mini
            self._mini_mode=True
            self.hide()
            self._mini_overlay = _MiniWidget(self)
            screen=QApplication.primaryScreen().availableGeometry()
            self._mini_overlay.move(screen.width()-270, screen.height()-290)
            self._mini_overlay.show()

    def _quick_cmd(self, cmd: str):
        self._log.append_log(f"You: {cmd}")
        if self.on_text_command:
            threading.Thread(target=self.on_text_command,args=(cmd,),daemon=True).start()

    def _on_file_selected(self, path: str):
        pass  # File upload removed

    def on_interrupt(self):
        """Callback externo para interrumpir — se asigna desde main.py"""
        pass

    def on_reconnect(self):
        """Callback externo para reconectar JARVIS — se asigna desde main.py"""
        pass

    def _on_interrupt_click(self):
        """Boton de interrupcion presionado."""
        if callable(self.on_interrupt):
            self.on_interrupt()

    def _toggle_mute(self):
        self._muted=not self._muted; self.hud.muted=self._muted; self._style_mute_btn()
        if self._muted: self._apply_state("MUTED"); self._log.append_log("SYS: Micrófono silenciado.")
        else:           self._apply_state("LISTENING"); self._log.append_log("SYS: Micrófono activo.")

    def _style_mute_btn(self):
        if self._muted:
            self._mute_btn.setText("🔇  MICRÓFONO SILENCIADO")
            self._mute_btn.setStyleSheet(
                f"QPushButton{{background:{C.RED_GHO};color:{C.MUTED_C};"
                f"border:1px solid {C.MUTED_C};border-radius:4px;}}"
                f"QPushButton:hover{{background:#220010;}}"
            )
        else:
            self._mute_btn.setText("🎙  MICRÓFONO ACTIVO")
            self._mute_btn.setStyleSheet(
                f"QPushButton{{background:{C.GREEN_GHO};color:{C.GREEN};"
                f"border:1px solid {C.GREEN_D};border-radius:4px;}}"
                f"QPushButton:hover{{background:#002214;}}"
            )

    def _send(self):
        txt=self._input.text().strip()
        if not txt: return
        self._input.clear(); self._log.append_log(f"You: {txt}")
        if self.on_text_command:
            threading.Thread(target=self.on_text_command,args=(txt,),daemon=True).start()

    def _apply_state(self, state: str):
        self.hud.state=state; self.hud.speaking=(state=="SPEAKING")

    def _check_config(self) -> bool:
        if not API_FILE.exists(): return False
        try:
            d=json.loads(API_FILE.read_text(encoding="utf-8"))
            return bool(d.get("gemini_api_key")) and bool(d.get("os_system"))
        except Exception: return False

    def _show_setup(self):
        ov=SetupOverlay(self.centralWidget()); cw=self.centralWidget(); ow,oh=460,390
        ov.setGeometry((cw.width()-ow)//2,(cw.height()-oh)//2,ow,oh)
        ov.done.connect(self._on_setup_done); ov.show(); self._overlay=ov

    def _on_setup_done(self, key: str, os_name: str):
        os.makedirs(CONFIG_DIR,exist_ok=True)
        API_FILE.write_text(json.dumps({"gemini_api_key":key,"os_system":os_name},indent=4),encoding="utf-8")
        self._ready=True
        if self._overlay: self._overlay.hide(); self._overlay=None
        self._apply_state("LISTENING")
        self._log.append_log(f"SYS: Inicializado. OS={os_name.upper()}. JARVIS online.")


# ── JarvisUI público ──────────────────────────────────────────────────────────
class _RootShim:
    def __init__(self, app): self._app=app
    def mainloop(self): self._app.exec()
    def protocol(self,*_): pass


class JarvisUI:
    def __init__(self, face_path: str, size=None):
        self._app=QApplication.instance() or QApplication(sys.argv)
        self._app.setStyle("Fusion")
        self._win=MainWindow(face_path)
        self._win.show()
        self.root=_RootShim(self._app)

    @property
    def muted(self) -> bool: return self._win._muted

    @muted.setter
    def muted(self, v: bool):
        if v!=self._win._muted: self._win._toggle_mute()

    @property
    def current_file(self) -> str|None: return None

    @property
    def on_text_command(self): return self._win.on_text_command

    @on_text_command.setter
    def on_text_command(self, cb): self._win.on_text_command=cb

    @property
    def on_reconnect(self): return self._win.on_reconnect

    @on_reconnect.setter
    def on_reconnect(self, cb): self._win.on_reconnect=cb

    def set_state(self, state: str): self._win._state_sig.emit(state)
    def write_log(self, text: str):
        self._win._log_sig.emit(text)
        # También enviar al mini widget si está activo
        mini = getattr(self._win, '_mini_overlay', None)
        if mini and mini.isVisible():
            try: mini.add_log(text)
            except Exception: pass
    def wait_for_api_key(self):
        while not self._win._ready: time.sleep(0.1)
    def start_speaking(self): self.set_state("SPEAKING")
    def stop_speaking(self):
        if not self.muted: self.set_state("LISTENING")
