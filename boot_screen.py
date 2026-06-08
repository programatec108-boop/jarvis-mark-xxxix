# boot_screen.py - Pantalla de carga estilo Iron Man para JARVIS Mark XXXIX
# Archivo: C:\Users\jose1\Mark-XXXIX\boot_screen.py

import sys
import math
import random
import time
from PyQt6.QtCore import Qt, QTimer, QRectF, QPointF, pyqtSignal
from PyQt6.QtGui import (QPainter, QColor, QPen, QBrush, QFont,
                          QLinearGradient, QRadialGradient)
from PyQt6.QtWidgets import QApplication, QWidget


class BootScreen(QWidget):
    """
    Pantalla de carga estilo Iron Man.
    Muestra secuencia animada y emite 'finished' cuando termina.
    """
    finished = pyqtSignal()

    # Secuencia de mensajes con delay en ms
    BOOT_SEQUENCE = [
        (0,    "#00d4ff", "J.A.R.V.I.S — MARK XXXIX"),
        (100,  "#007a99", "Just A Rather Very Intelligent System"),
        (400,  "#0d3347", "─" * 48),
        (700,  "#00d4ff", "▸ Iniciando protocolo de arranque..."),
        (1100, "#00ff88", "  [OK] Núcleo de inteligencia artificial"),
        (1400, "#00d4ff", "▸ Calibrando sistema de audio..."),
        (1800, "#00ff88", "  [OK] Motor de voz Gemini 2.5 Flash"),
        (2000, "#00d4ff", "▸ Verificando conexión de red..."),
        (2400, "#00ff88", "  [OK] Conexión establecida — 12ms latencia"),
        (2600, "#00d4ff", "▸ Cargando dispositivos IoT..."),
        (2900, "#00ff88", "  [OK] Dispositivos Tuya sincronizados"),
        (3100, "#00d4ff", "▸ Restaurando memoria del usuario..."),
        (3500, "#00ff88", "  [OK] Memoria cargada"),
        (3700, "#00d4ff", "▸ Activando detector de voz local..."),
        (4000, "#00ff88", "  [OK] Detector activo — Di 'Jarvis' para activar"),
        (4200, "#ffcc00", "▸ Cargando módulos de sistema..."),
        (4400, "#00ff88", "  [OK] 23 módulos cargados"),
        (4600, "#0d3347", "─" * 48),
        (4900, "#ffcc00", "  TODOS LOS SISTEMAS OPERATIVOS"),
        (5200, "#00ff88", "  BIENVENIDO — PROTOCOLO MARK XXXIX ACTIVO"),
    ]

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Pantalla completa
        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(screen)

        # Estado
        self._tick       = 0
        self._lines      = []       # lineas mostradas
        self._progress   = 0.0     # 0-100
        self._counter    = 0       # numero animado
        self._rings      = [0.0, 120.0, 240.0]
        self._particles  = []
        self._alpha      = 255     # fade out al final
        self._done       = False
        self._glitch     = 0       # efecto glitch

        # Timers
        self._anim_tmr = QTimer(self)
        self._anim_tmr.timeout.connect(self._step)
        self._anim_tmr.start(16)  # 60fps

        # Programar mensajes
        for delay, color, text in self.BOOT_SEQUENCE:
            QTimer.singleShot(delay, lambda c=color, t=text: self._add_line(c, t))

        # Programar fin
        QTimer.singleShot(5800, self._start_fadeout)

    def _add_line(self, color, text):
        self._lines.append((color, text))
        # Actualizar progreso
        total = len(self.BOOT_SEQUENCE)
        self._progress = min(100, len(self._lines) / total * 100)
        self.update()

    def _step(self):
        self._tick += 1
        # Anillos giratorios
        for i in range(3):
            speeds = [0.8, -0.5, 1.2]
            self._rings[i] = (self._rings[i] + speeds[i]) % 360
        # Contador de numeros
        if self._progress < 100:
            self._counter = int(self._progress * 10.24) + random.randint(0, 9)
        # Particulas
        if random.random() < 0.15:
            self._particles.append([
                random.randint(0, self.width()),
                random.randint(0, self.height()),
                random.uniform(-0.5, 0.5),
                random.uniform(-1.5, -0.5),
                random.uniform(0.3, 0.8)
            ])
        self._particles = [
            [p[0]+p[2], p[1]+p[3], p[2], p[3], p[4]-0.015]
            for p in self._particles if p[4] > 0
        ]
        # Glitch ocasional
        if random.random() < 0.02:
            self._glitch = random.randint(3, 8)
        if self._glitch > 0:
            self._glitch -= 1
        self.update()

    def _start_fadeout(self):
        self._fade_tmr = QTimer(self)
        self._fade_tmr.timeout.connect(self._fadeout_step)
        self._fade_tmr.start(16)

    def _fadeout_step(self):
        self._alpha -= 8
        if self._alpha <= 0:
            self._alpha = 0
            self._fade_tmr.stop()
            self._anim_tmr.stop()
            self.hide()
            self.finished.emit()
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        cx, cy = W / 2, H / 2

        # Fondo negro semitransparente
        p.fillRect(self.rect(), QColor(0, 4, 8, self._alpha))

        # Grid de puntos
        p.setPen(QPen(QColor(0, 50, 70, int(self._alpha * 0.3)), 1))
        for x in range(0, W, 60):
            for y in range(0, H, 60):
                p.drawPoint(x, y)

        # ── Anillos HUD en el centro-izquierda ──
        hx, hy = W * 0.22, H * 0.45
        for idx, (r, w, al) in enumerate([
            (160, 2, 0.7), (130, 1.5, 0.5), (100, 1, 0.35)
        ]):
            base = self._rings[idx]
            a = int(self._alpha * al)
            p.setPen(QPen(QColor(0, 212, 255, a), w))
            p.setBrush(Qt.BrushStyle.NoBrush)
            arc_len, gap = 100, 70
            angle = base
            rect = QRectF(hx-r, hy-r, r*2, r*2)
            while angle < base + 360:
                p.drawArc(rect, int(angle*16), int(arc_len*16))
                angle += arc_len + gap

        # Circulo central HUD
        r_inner = 65
        p.setPen(QPen(QColor(0, 212, 255, self._alpha), 1.5))
        p.setBrush(QBrush(QColor(0, 10, 20, int(self._alpha * 0.8))))
        p.drawEllipse(QPointF(hx, hy), r_inner, r_inner)

        # Texto JARVIS en el circulo
        p.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
        p.setPen(QPen(QColor(0, 212, 255, self._alpha), 1))
        p.drawText(QRectF(hx-60, hy-8, 120, 16),
                   Qt.AlignmentFlag.AlignCenter, "J.A.R.V.I.S")

        # Porcentaje debajo del circulo
        p.setFont(QFont("Courier New", 11, QFont.Weight.Bold))
        p.setPen(QPen(QColor(0, 255, 136, self._alpha), 1))
        p.drawText(QRectF(hx-60, hy+75, 120, 20),
                   Qt.AlignmentFlag.AlignCenter,
                   f"{int(self._progress)}%")

        # Barra de progreso circular (arco)
        arc_r = 80
        p.setPen(QPen(QColor(0, 212, 255, int(self._alpha * 0.3)), 4))
        p.drawEllipse(QPointF(hx, hy), arc_r, arc_r)
        p.setPen(QPen(QColor(0, 212, 255, self._alpha), 4))
        span = int(-self._progress / 100 * 360 * 16)
        p.drawArc(QRectF(hx-arc_r, hy-arc_r, arc_r*2, arc_r*2),
                  90*16, span)

        # ── Particulas ──
        for pt in self._particles:
            a = max(0, min(255, int(pt[4] * self._alpha)))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(QColor(0, 212, 255, a)))
            p.drawEllipse(QPointF(pt[0], pt[1]), 1.5, 1.5)

        # ── Panel de texto (derecha) ──
        tx = W * 0.38
        ty_start = H * 0.12

        # Titulo grande
        p.setFont(QFont("Courier New", 22, QFont.Weight.Bold))
        p.setPen(QPen(QColor(0, 212, 255, self._alpha), 1))
        glitch_x = random.randint(-3, 3) if self._glitch > 0 else 0
        p.drawText(QRectF(tx + glitch_x, ty_start, W*0.6, 36),
                   Qt.AlignmentFlag.AlignLeft, "J.A.R.V.I.S")

        p.setFont(QFont("Courier New", 9))
        p.setPen(QPen(QColor(0, 122, 153, self._alpha), 1))
        p.drawText(QRectF(tx, ty_start+38, W*0.6, 16),
                   Qt.AlignmentFlag.AlignLeft,
                   "MARK XXXIX  ·  INICIALIZANDO SISTEMAS")

        # Linea separadora
        sep_y = ty_start + 62
        p.setPen(QPen(QColor(13, 51, 71, self._alpha), 1))
        p.drawLine(QPointF(tx, sep_y), QPointF(W*0.92, sep_y))

        # Mensajes del log
        p.setFont(QFont("Courier New", 10))
        max_visible = 14
        visible = self._lines[-max_visible:] if len(self._lines) > max_visible else self._lines
        for i, (color, text) in enumerate(visible):
            y = sep_y + 16 + i * 22
            # Ultima linea parpadea
            if i == len(visible) - 1 and self._tick % 30 < 20:
                alpha_line = self._alpha
            else:
                alpha_line = int(self._alpha * (0.5 + 0.5 * (i / max(len(visible),1))))
            r_, g_, b_ = int(color[1:3],16), int(color[3:5],16), int(color[5:7],16)
            p.setPen(QPen(QColor(r_, g_, b_, alpha_line), 1))
            # Efecto glitch en texto
            gx = random.randint(-2, 2) if self._glitch > 3 and i == len(visible)-1 else 0
            p.drawText(QRectF(tx + gx, y, W*0.6, 20),
                       Qt.AlignmentFlag.AlignLeft, text)

        # Barra de progreso lineal
        bar_y = H * 0.88
        bar_x = tx
        bar_w = W * 0.54
        bar_h = 3

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(13, 51, 71, self._alpha)))
        p.drawRoundedRect(QRectF(bar_x, bar_y, bar_w, bar_h), 1, 1)

        fill_w = bar_w * self._progress / 100
        if fill_w > 0:
            g = QLinearGradient(bar_x, 0, bar_x + fill_w, 0)
            g.setColorAt(0, QColor(0, 100, 140, self._alpha))
            g.setColorAt(1, QColor(0, 212, 255, self._alpha))
            p.setBrush(QBrush(g))
            p.drawRoundedRect(QRectF(bar_x, bar_y, fill_w, bar_h), 1, 1)

        # Texto de progreso
        p.setFont(QFont("Courier New", 8))
        p.setPen(QPen(QColor(0, 122, 153, self._alpha), 1))
        p.drawText(QRectF(bar_x, bar_y+8, bar_w, 14),
                   Qt.AlignmentFlag.AlignLeft,
                   f"CARGANDO  {int(self._progress)}%  ·  MARK XXXIX")

        # Contador binario decorativo
        p.setFont(QFont("Courier New", 7))
        p.setPen(QPen(QColor(0, 60, 80, int(self._alpha * 0.6)), 1))
        binary = format(self._counter % 65536, '016b')
        p.drawText(QRectF(bar_x, bar_y+22, bar_w, 12),
                   Qt.AlignmentFlag.AlignLeft, binary + "  " + hex(self._counter % 65536))

        # Lineas de escaneo
        scan_y = (self._tick * 3) % H
        p.setPen(QPen(QColor(0, 212, 255, int(self._alpha * 0.04)), 1))
        p.drawLine(0, scan_y, W, scan_y)
        p.drawLine(0, (scan_y + H//2) % H, W, (scan_y + H//2) % H)

        p.end()

    def mousePressEvent(self, e):
        """Click para saltar la animacion."""
        self._start_fadeout()
