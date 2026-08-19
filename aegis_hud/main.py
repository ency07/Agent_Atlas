import sys
import requests
from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
                             QWidget, QLabel, QTextEdit, QLineEdit, QPushButton,
                             QGraphicsDropShadowEffect, QFrame)
from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QRect, pyqtProperty
from PyQt5.QtGui import QFont, QColor, QPainter, QPen, QRadialGradient

class ReactorArc(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(120, 120)
        self.angle = 0
        self.is_processing = False
        self.color = QColor(0, 255, 255)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_angle)
        self.timer.start(50)

    def set_processing(self, state: bool):
        self.is_processing = state
        self.color = QColor(255, 165, 0) if state else QColor(0, 255, 255)
        self.timer.setInterval(20 if state else 50)

    def update_angle(self):
        self.angle = (self.angle + 2) % 360
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        center = self.rect().center()
        radius = 50

        painter.save()
        painter.translate(center)
        painter.rotate(self.angle)
        painter.setPen(QPen(self.color, 4, Qt.SolidLine))
        painter.drawArc(-radius, -radius, radius*2, radius*2, 0, 200 * 16)
        painter.drawArc(-radius+10, -radius+10, (radius-10)*2, (radius-10)*2, 180 * 16, 200 * 16)
        painter.restore()

        gradient = QRadialGradient(center.x(), center.y(), radius * 0.4)
        gradient.setColorAt(0, QColor(255, 255, 255, 200))
        gradient.setColorAt(0.5, self.color)
        gradient.setColorAt(1, QColor(0, 0, 0, 0))
        painter.setBrush(gradient)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(center, int(radius * 0.4), int(radius * 0.4))


class AegisHUD(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AEGIS-JARVIS HUD")
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, False)

        self.is_minimized = False
        self.normal_geometry = None

        self.setStyleSheet("""
            QMainWindow { background-color: #121212; border: 2px solid #00ffff; border-radius: 12px; }
            QLabel { color: #e0e0e0; }
            QLabel#title { color: #00ffff; font-weight: bold; font-size: 14px; }
            QLabel#metric { color: #00ffff; font-size: 12px; }
            QTextEdit { background-color: #1e1e1e; color: #00ff00; border: 1px solid #333; border-radius: 4px; font-family: Consolas; }
            QLineEdit { background-color: #1e1e1e; color: #fff; border: 1px solid #00ffff; border-radius: 4px; padding: 6px; }
            QPushButton { background-color: #00ffff; color: #000; font-weight: bold; border-radius: 4px; padding: 6px; }
            QPushButton:hover { background-color: #00cccc; }
            QPushButton#stopBtn { background-color: #ff4444; color: white; }
            QPushButton#stopBtn:hover { background-color: #cc0000; }
        """)

        self.init_ui()
        self.start_bridge_polling()

    def _make_title(self, text):
        lbl = QLabel(text)
        lbl.setObjectName("title")
        return lbl

    def _make_metric(self, text):
        lbl = QLabel(text)
        lbl.setObjectName("metric")
        return lbl

    def init_ui(self):
        screen = QApplication.primaryScreen().geometry()
        w = screen.width()
        h = screen.height()
        self.normal_geometry = QRect(0, 0, w, h)
        self.setGeometry(self.normal_geometry)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.main_layout = QVBoxLayout(central_widget)
        self.main_layout.setContentsMargins(15, 15, 15, 15)
        self.main_layout.setSpacing(15)

        self.expanded_view = QWidget()
        exp_layout = QHBoxLayout(self.expanded_view)
        exp_layout.setContentsMargins(0, 0, 0, 0)
        exp_layout.setSpacing(15)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(self._make_title("LOG DE ACCIONES"))
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.append("[INFO] Sistema iniciado. Conectando a bridge...")
        left_layout.addWidget(self.log_area)

        center_panel = QWidget()
        center_layout = QVBoxLayout(center_panel)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setAlignment(Qt.AlignCenter)

        self.reactor = ReactorArc()
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 255, 255))
        self.reactor.setGraphicsEffect(shadow)
        center_layout.addWidget(self.reactor, alignment=Qt.AlignCenter)

        self.reactor_label = self._make_title("Estado: IDLE")
        self.reactor_label.setAlignment(Qt.AlignCenter)
        center_layout.addWidget(self.reactor_label)

        self.metrics_label = self._make_metric("CPU: --% | RAM: --% | DISK: --%")
        self.metrics_label.setAlignment(Qt.AlignCenter)
        center_layout.addWidget(self.metrics_label)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(self._make_title("ATLAS STATUS"))
        self.status_label = QLabel("Bridge: Desconectado\nMCPs: Inactivos")
        right_layout.addWidget(self.status_label)

        self.stop_btn = QPushButton("STOP AGENTE")
        self.stop_btn.setObjectName("stopBtn")
        self.stop_btn.clicked.connect(lambda: self.log_area.append("[WARN] Agente detenido por usuario."))
        right_layout.addWidget(self.stop_btn)
        right_layout.addStretch()

        exp_layout.addWidget(left_panel, stretch=1)
        exp_layout.addWidget(center_panel, stretch=1)
        exp_layout.addWidget(right_panel, stretch=1)

        self.minimized_view = QWidget()
        self.minimized_view.setVisible(False)
        min_layout = QHBoxLayout(self.minimized_view)
        min_layout.setContentsMargins(15, 0, 15, 0)

        min_layout.addWidget(self._make_title("AEGIS"))
        self.min_status = self._make_metric("OK")
        min_layout.addWidget(self.min_status)
        self.min_metrics = self._make_metric("CPU: --% | RAM: --%")
        min_layout.addWidget(self.min_metrics)
        min_layout.addStretch()
        self.expand_btn = QPushButton("Expandir")
        self.expand_btn.clicked.connect(self.toggle_view)
        min_layout.addWidget(self.expand_btn)

        input_layout = QHBoxLayout()
        self.cmd_input = QLineEdit()
        self.cmd_input.setPlaceholderText("Escribe un comando...")
        self.cmd_input.returnPressed.connect(self.send_command)
        send_btn = QPushButton("ENVIAR")
        send_btn.clicked.connect(self.send_command)
        input_layout.addWidget(self.cmd_input)
        input_layout.addWidget(send_btn)

        self.main_layout.addWidget(self.expanded_view)
        self.main_layout.addWidget(self.minimized_view)
        self.main_layout.addLayout(input_layout)

    def mouseDoubleClickEvent(self, event):
        self.toggle_view()

    def toggle_view(self):
        self.is_minimized = not self.is_minimized
        if self.is_minimized:
            self.normal_geometry = self.geometry()
            self.expanded_view.setVisible(False)
            self.minimized_view.setVisible(True)
            self.setGeometry(self.geometry().x(), 0, self.geometry().width(), 40)
        else:
            self.expanded_view.setVisible(True)
            self.minimized_view.setVisible(False)
            if self.normal_geometry:
                self.setGeometry(self.normal_geometry)

    def start_bridge_polling(self):
        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self.poll_bridge)
        self.poll_timer.start(3000)

    def poll_bridge(self):
        try:
            r_health = requests.get("http://127.0.0.1:8765/health", timeout=1)
            if r_health.status_code == 200:
                data = r_health.json()
                status_text = "Bridge: OK" if data["status"] == "healthy" else "Bridge: Degraded"
                mcp_count = sum(1 for v in data["mcp_endpoints"].values() if v)
                self.status_label.setText(f"{status_text}\nMCPs Activos: {mcp_count}/7")
                self.min_status.setText("OK")

            r_metrics = requests.get("http://127.0.0.1:8765/system_metrics", timeout=1)
            if r_metrics.status_code == 200:
                m = r_metrics.json()
                self.metrics_label.setText(f"CPU: {m['cpu']}% | RAM: {m['ram']}% | DISK: {m['disk']}%")
                self.min_metrics.setText(f"CPU: {m['cpu']}% | RAM: {m['ram']}%")

        except requests.exceptions.RequestException:
            self.status_label.setText("Bridge: Desconectado\nInicia el bridge primero.")
            self.min_status.setText("OFF")

    def send_command(self):
        cmd = self.cmd_input.text().strip()
        if not cmd:
            return

        self.log_area.append(f"\n[USER] {cmd}")
        self.reactor.set_processing(True)
        self.reactor_label.setText("Estado: PROCESANDO...")

        try:
            r = requests.post("http://127.0.0.1:8765/execute_action", params={"action": cmd}, timeout=2)
            if r.status_code == 200:
                self.log_area.append("[SUCCESS] Comando enviado al bridge.")
            else:
                self.log_area.append(f"[ERROR] Fallo en bridge: {r.status_code}")
        except Exception as e:
            self.log_area.append(f"[ERROR] No se pudo conectar al bridge: {e}")
        finally:
            self.reactor.set_processing(False)
            self.reactor_label.setText("Estado: IDLE")
            self.cmd_input.clear()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    hud = AegisHUD()
    hud.showFullScreen()
    hud.raise_()
    hud.activateWindow()
    sys.exit(app.exec_())
