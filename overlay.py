from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QRect, QPoint, Signal
from PySide6.QtGui import QPainter, QColor, QPen, QGuiApplication

class OverlayWindow(QWidget):
    region_selected = Signal(QRect)

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_DeleteOnClose)

        self.begin_pos = QPoint()
        self.end_pos = QPoint()
        self.is_selecting = False

    def show_overlay(self):
        """Shows the simplified overlay across all screens."""
        desktop_geometry = self.get_desktop_geometry()
        self.setGeometry(desktop_geometry)
        self.showFullScreen()
        self.activateWindow()

    def get_desktop_geometry(self) -> QRect:
        """Calculates the bounding box of all connected screens."""
        total_geometry = QRect()
        for screen in QGuiApplication.screens():
            total_geometry = total_geometry.united(screen.geometry())
        return total_geometry

    def paintEvent(self, event):
        """A much simpler paint event for debugging."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 1. Draw a semi-transparent black overlay over the entire screen area.
        overlay_color = QColor(0, 0, 0, 80)
        painter.fillRect(self.rect(), overlay_color)

        # 2. If selecting, draw a border for the selection rectangle.
        if self.is_selecting:
            selection_rect = QRect(self.begin_pos, self.end_pos).normalized()
            
            # Draw a clear rectangle inside the selection
            painter.setCompositionMode(QPainter.CompositionMode_Clear)
            painter.fillRect(selection_rect, Qt.transparent)
            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)

            # Draw a white border around it
            pen = QPen(QColor("#FFFFFF"), 2, Qt.SolidLine)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(selection_rect)

    def mousePressEvent(self, event):
        self.is_selecting = True
        self.begin_pos = event.position().toPoint()
        self.end_pos = self.begin_pos
        self.update()

    def mouseMoveEvent(self, event):
        if self.is_selecting:
            self.end_pos = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event):
        if self.is_selecting:
            self.is_selecting = False
            selection_rect = QRect(self.begin_pos, self.end_pos).normalized()
            self.hide()
            
            if selection_rect.width() > 5 and selection_rect.height() > 5:
                self.region_selected.emit(selection_rect)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.is_selecting = False
            self.hide()