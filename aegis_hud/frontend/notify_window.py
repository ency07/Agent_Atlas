#!/usr/bin/env python3
"""
notify_window.py — Ventana PyQt6 minimalista para notificaciones y doble palmada.

Funciones:
  1. Muestra notificaciones toast del OS (polling al backend cada 5s).
  2. Detecta doble palmada (clap) como wake word para activar el microfono.
  3. Ventana frameless, siempre visible, minimalista.

Requisitos: PyQt6, requests, sounddevice, numpy
Uso: python notify_window.py [--backend http://127.0.0.1:8765]
"""

import sys
import os
import time
import json
import threading
from pathlib import Path

# --- Config ---
BACKEND_URL = "http://127.0.0.1:8765"
CLAP_THRESHOLD = 0.6
CLAP_COOLDOWN_S = 2.0
POLL_INTERVAL_S = 5.0
NOTIFICATION_DURATION_MS = 5000

# Parse args
for i, arg in enumerate(sys.argv):
    if arg == "--backend" and i + 1 < len(sys.argv):
        BACKEND_URL = sys.argv[i + 1]

try:
    from PyQt6.QtWidgets import (
        QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
        QGraphicsDropShadowEffect, QPushButton
    )
    from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtSignal, QObject
    from PyQt6.QtGui import QFont, QColor, QPainter, QPen, QRadialGradient
except ImportError:
    print("[notify_window] PyQt6 no instalado. Ejecuta: pip install PyQt6")
    sys.exit(1)

try:
    import requests
except ImportError:
    print("[notify_window] requests no instalado. Ejecuta: pip install requests")
    sys.exit(1)


# ============================================================
#  CLAP DETECTOR (sounddevice + numpy)
# ============================================================

class ClapDetector(QObject):
    """Detecta doble palmada usando picos de audio."""
    clap_detected = pyqtSignal()

    def __init__(self, threshold=CLAP_THRESHOLD, cooldown=CLAP_COOLDOWN_S):
        super().__init__()
        self.threshold = threshold
        self.cooldown = cooldown
        self._last_clap_time = 0
        self._first_clap_time = 0
        self._listening = False
        self._stream = None
        self._enabled = False

    def start(self):
        """Inicia la escucha de audio."""
        try:
            import sounddevice as sd
            self._sd = sd
            self._enabled = True
            self._listening = True
            self._stream = sd.InputStream(
                channels=1, samplerate=16000, blocksize=1600,
                callback=self._audio_callback
            )
            self._stream.start()
            print("[clap] Detector de palmadas activado (threshold={:.2f})".format(self.threshold))
        except Exception as e:
            print("[clap] No se pudo activar detector: {}".format(e))
            self._enabled = False

    def stop(self):
        """Detiene la escucha."""
        self._listening = False
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

    def _audio_callback(self, indata, frames, time_info, status):
        """Callback de audio: detecta picos de energia."""
        if not self._listening or not self._enabled:
            return
        try:
            import numpy as np
            energy = np.sqrt(np.mean(indata.astype(float) ** 2))
            now = time.time()

            if energy > self.threshold:
                if now - self._last_clap_time > self.cooldown:
                    if now - self._first_clap_time < 0.8 and self._first_clap_time > 0:
                        # Doble palmada detectada
                        self._first_clap_time = 0
                        self._last_clap_time = now
                        print("[clap] DOBLE PALMADA DETECTADA")
                        self.clap_detected.emit()
                    else:
                        self._first_clap_time = now
        except Exception:
            pass


# ============================================================
#  NOTIFICATION WIDGET
# ============================================================

class NotificationToast(QWidget):
    """Widget de notificacion toast."""

    def __init__(self, title, message, level="info", duration_ms=NOTIFICATION_DURATION_MS, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(300)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        self.title_label = QLabel(title)
        self.title_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.title_label.setStyleSheet("color: #59c8ff;")

        self.msg_label = QLabel(message)
        self.msg_label.setFont(QFont("Segoe UI", 9))
        self.msg_label.setStyleSheet("color: #eaf6ff;")
        self.msg_label.setWordWrap(True)

        layout.addWidget(self.title_label)
        layout.addWidget(self.msg_label)

        # Color por nivel
        border_color = {"info": "#59c8ff", "success": "#5cf0c8", "warning": "#ffc857", "error": "#ff5d5d"}.get(level, "#59c8ff")
        self.setStyleSheet(
            "background-color: rgba(18,18,18,0.92); "
            "border: 1px solid rgba(140,200,255,0.22); "
            "border-left: 3px solid {}; "
            "border-radius: 10px;".format(border_color)
        )

        # Shadow
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 120))
        shadow.setOffset(0, 4)
        self.setGraphicsEffect(shadow)

        # Auto-hide
        QTimer.singleShot(duration_ms, self.close)


# ============================================================
#  MAIN WINDOW
# ============================================================

class NotifyWindow(QWidget):
    """Ventana principal minimalista: indicador + notificaciones + clap."""

    def __init__(self, backend_url=BACKEND_URL):
        super().__init__()
        self.backend_url = backend_url
        self.toast_y = 54
        self.active_toasts = []

        # Ventana frameless, siempre encima,最小化
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(200, 36)

        # UI
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)

        self.status_dot = QLabel("\U0001f7e2")
        self.status_dot.setFont(QFont("Segoe UI", 12))
        layout.addWidget(self.status_dot)

        self.status_label = QLabel("AEGIS")
        self.status_label.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.status_label.setStyleSheet("color: #59c8ff;")
        layout.addWidget(self.status_label)

        self.clap_label = QLabel("\U0001f44f")
        self.clap_label.setFont(QFont("Segoe UI", 10))
        self.clap_label.setStyleSheet("opacity: 0.4;")
        layout.addWidget(self.clap_label)

        layout.addStretch()

        # Style
        self.setStyleSheet(
            "background-color: rgba(18,18,18,0.88); "
            "border: 1px solid rgba(140,200,255,0.22); "
            "border-radius: 8px;"
        )

        # Shadow
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(12)
        shadow.setColor(QColor(0, 0, 0, 80))
        shadow.setOffset(0, 2)
        self.setGraphicsEffect(shadow)

        # Polling timer
        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self.poll_notifications)
        self.poll_timer.start(int(POLL_INTERVAL_S * 1000))

        # Clap detector
        self.clap_detector = ClapDetector()
        self.clap_detector.clap_detected.connect(self.on_clap)

        # Drag support
        self._drag_pos = None

    def start_clap(self):
        """Activa el detector de palmadas."""
        self.clap_detector.start()
        self.clap_label.setStyleSheet("opacity: 1.0;")

    def poll_notifications(self):
        """Consulta notificaciones pendientes del backend."""
        try:
            resp = requests.get(
                f"{self.backend_url}/state",
                timeout=3
            )
            if resp.status_code == 200:
                data = resp.json()
                ts = data.get("task_state", {})
                status = ts.get("status", "idle")
                if status == "completed" and ts.get("result"):
                    resp_text = ts["result"].get("response", "")
                    if resp_text:
                        self.show_toast("Atlas", resp_text[:120], "success")
                elif status == "error":
                    self.show_toast("Error", ts.get("last_error", "Unknown error"), "error")
                elif data.get("blocked"):
                    self.status_dot.setText("\U0001f534")
                    self.status_label.setText("BLOCKED")
                    return

                # Update dot
                if status in ("executing", "classifying", "routing"):
                    self.status_dot.setText("\U0001f7e1")
                    self.status_label.setText("BUSY")
                else:
                    self.status_dot.setText("\U0001f7e2")
                    self.status_label.setText("IDLE")

        except Exception:
            self.status_dot.setText("\U0001f534")
            self.status_label.setText("DOWN")

    def on_clap(self):
        """Callback cuando se detecta doble palmada."""
        self.clap_label.setStyleSheet("opacity: 1.0; color: #ffc857;")
        QTimer.singleShot(1000, lambda: self.clap_label.setStyleSheet("opacity: 0.4;"))
        self.show_toast("Wake Word", "Doble palmada detectada. Activa el microfono.", "info")
        # Emitir signal para voice_bridge (si esta corriendo)

    def show_toast(self, title, message, level="info"):
        """Muestra una notificacion toast."""
        toast = NotificationToast(title, message, level, parent=None)
        toast.move(self.x(), self.toast_y)
        toast.show()
        self.active_toasts.append(toast)
        self.toast_y += 60
        # Cleanup despues de duration
        QTimer.singleShot(NOTIFICATION_DURATION_MS + 200, lambda: self._cleanup_toast(toast))

    def _cleanup_toast(self, toast):
        if toast in self.active_toasts:
            self.active_toasts.remove(toast)
            toast.close()
        if not self.active_toasts:
            self.toast_y = 54

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None


# ============================================================
#  MAIN
# ============================================================

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = NotifyWindow()
    window.show()

    # Start clap detector after window is visible
    QTimer.singleShot(1000, window.start_clap)

    print("[notify_window] Ventana de notificaciones activa")
    print("[notify_window] Backend: {}".format(BACKEND_URL))
    print("[notify_window] Clap detector: activo (threshold={})".format(CLAP_THRESHOLD))

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
