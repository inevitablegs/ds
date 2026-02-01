from PySide6.QtWidgets import QWidget, QToolButton, QHBoxLayout, QFrame
from PySide6.QtCore import Qt, QRect, QPoint, Signal, QSize
from PySide6.QtGui import QPainter, QColor, QPen, QGuiApplication, QPixmap
import enum
from PIL.ImageQt import ImageQt


class OverlayMode(enum.Enum):
    LOADING = 0
    TEXT_SELECTION = 1
    REGION_SELECTION = 2


class TextActionWidget(QFrame):
    search_triggered = Signal(str)
    copy_triggered = Signal(str)

    def __init__(self, selected_text: str):
        super().__init__()
        self.selected_text = selected_text
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool | Qt.Popup)
        self.setStyleSheet(
            "QFrame { background-color: #333; border: 1px solid #00F; border-radius: 5px; padding: 5px; }"
        )

        layout = QHBoxLayout(self)

        search_btn = QToolButton(self)
        search_btn.setText("🔍 Copy & Search")
        search_btn.clicked.connect(lambda: self.search_triggered.emit(self.selected_text))

        copy_btn = QToolButton(self)
        copy_btn.setText("📋 Copy Text")
        copy_btn.clicked.connect(lambda: self.copy_triggered.emit(self.selected_text))

        layout.addWidget(search_btn)
        layout.addWidget(copy_btn)
        self.adjustSize()


class OverlayWindow(QWidget):
    region_selected = Signal(QRect)
    text_copied_and_searched = Signal(str)
    text_copied = Signal(str)

    def __init__(self):
        super().__init__()

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool | Qt.Popup)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.mode = OverlayMode.LOADING
        self.full_screen_pixmap = None
        self.ocr_results = []

        # REGION selection
        self.begin_pos = QPoint()
        self.end_pos = QPoint()
        self.is_selecting_region = False

        # TEXT selection
        self.is_selecting_text = False
        self.selection_start_pos = None
        self.selection_rect = QRect()
        self.selected_ocr_indices = set()
        self.selected_text_content = ""

        self.action_widget = None

    # -------------------- SETUP --------------------

    def load_full_screen_capture(self, pil_image):
        desktop_geometry = self.get_desktop_geometry()
        self.setGeometry(desktop_geometry)

        qimage = ImageQt(pil_image)
        pixmap = QPixmap.fromImage(qimage)

        self.full_screen_pixmap = pixmap.scaled(
            desktop_geometry.size(),
            Qt.IgnoreAspectRatio,
            Qt.SmoothTransformation,
        )

        self.mode = OverlayMode.LOADING
        self.update()

    def load_ocr_results(self, results):
        self.ocr_results = results
        self.mode = OverlayMode.TEXT_SELECTION if results else OverlayMode.REGION_SELECTION
        self.update()

    def show_overlay(self):
        self.showFullScreen()
        self.activateWindow()

    def get_desktop_geometry(self):
        geo = QRect()
        for screen in QGuiApplication.screens():
            geo = geo.united(screen.geometry())
        return geo

    # -------------------- PAINT --------------------

    def paintEvent(self, event):
        painter = QPainter(self)

        if self.full_screen_pixmap:
            painter.drawPixmap(self.rect(), self.full_screen_pixmap)

        if self.mode == OverlayMode.LOADING:
            painter.fillRect(self.rect(), QColor(0, 0, 0, 150))
            return

        painter.fillRect(self.rect(), QColor(0, 0, 0, 80))

        if self.mode == OverlayMode.TEXT_SELECTION:
            # Draw OCR boxes
            for i, item in enumerate(self.ocr_results):
                rect = QRect(*item["rect"])
                if i in self.selected_ocr_indices:
                    painter.fillRect(rect, QColor(0, 120, 215, 120))

            # Draw selection rectangle
            if self.is_selecting_text and not self.selection_rect.isNull():
                painter.setPen(QPen(QColor(0, 120, 215), 2))
                painter.setBrush(QColor(0, 120, 215, 40))
                painter.drawRect(self.selection_rect)

        elif self.mode == OverlayMode.REGION_SELECTION and self.is_selecting_region:
            rect = QRect(self.begin_pos, self.end_pos).normalized()
            painter.setCompositionMode(QPainter.CompositionMode_Clear)
            painter.fillRect(rect, Qt.transparent)
            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
            painter.setPen(QPen(Qt.white, 2))
            painter.drawRect(rect)

    # -------------------- MOUSE --------------------

    def mousePressEvent(self, event):
        self.cleanup_action_widget()

        if self.mode == OverlayMode.REGION_SELECTION:
            self.is_selecting_region = True
            self.begin_pos = event.position().toPoint()
            self.end_pos = self.begin_pos

        elif self.mode == OverlayMode.TEXT_SELECTION:
            self.is_selecting_text = True
            self.selection_start_pos = event.position().toPoint()
            self.selection_rect = QRect(self.selection_start_pos, self.selection_start_pos)
            self.selected_ocr_indices.clear()

        self.update()

    def mouseMoveEvent(self, event):
        pos = event.position().toPoint()

        if self.mode == OverlayMode.REGION_SELECTION and self.is_selecting_region:
            self.end_pos = pos

        elif self.mode == OverlayMode.TEXT_SELECTION and self.is_selecting_text:
            self.selection_rect = QRect(self.selection_start_pos, pos).normalized()
            self.selected_ocr_indices.clear()

            for i, item in enumerate(self.ocr_results):
                rect = QRect(*item["rect"])
                if rect.intersects(self.selection_rect):
                    self.selected_ocr_indices.add(i)

        self.update()

    def mouseReleaseEvent(self, event):
        if self.mode == OverlayMode.REGION_SELECTION:
            self.is_selecting_region = False
            rect = QRect(self.begin_pos, self.end_pos).normalized()
            self.cleanup_and_hide()
            if rect.width() > 5 and rect.height() > 5:
                self.region_selected.emit(rect)

        elif self.mode == OverlayMode.TEXT_SELECTION:
            self.is_selecting_text = False

            # Fallback: single click
            if not self.selected_ocr_indices:
                idx = self.get_ocr_index_at(event.position().toPoint())
                if idx != -1:
                    self.selected_ocr_indices = {idx}

            if not self.selected_ocr_indices:
                return

            items = [self.ocr_results[i] for i in self.selected_ocr_indices]

            # Sort top-to-bottom first
            items.sort(key=lambda i: i["rect"][1])

            lines = []
            current_line = []
            current_y = None
            Y_THRESHOLD = 10  # tweak if needed

            for item in items:
                x, y, w, h = item["rect"]
                center_y = y + h // 2

                if current_y is None or abs(center_y - current_y) <= Y_THRESHOLD:
                    current_line.append(item)
                    current_y = center_y if current_y is None else current_y
                else:
                    # New line
                    current_line.sort(key=lambda i: i["rect"][0])  # left to right
                    lines.append(" ".join(i["text"] for i in current_line))
                    current_line = [item]
                    current_y = center_y

            # Last line
            if current_line:
                current_line.sort(key=lambda i: i["rect"][0])
                lines.append(" ".join(i["text"] for i in current_line))

            self.selected_text_content = "\n".join(lines)

            self._show_text_action_widget(self.selection_rect)

    # -------------------- HELPERS --------------------

    def get_ocr_index_at(self, point):
        for i, item in enumerate(self.ocr_results):
            if QRect(*item["rect"]).contains(point):
                return i
        return -1

    def _show_text_action_widget(self, rect):
        self.cleanup_action_widget()
        self.action_widget = TextActionWidget(self.selected_text_content)
        self.action_widget.search_triggered.connect(self._handle_text_search_copy)
        self.action_widget.copy_triggered.connect(self._handle_text_copy)
        self.action_widget.move(rect.left(), rect.bottom() + 5)
        self.action_widget.show()

    def cleanup_action_widget(self):
        if self.action_widget:
            self.action_widget.close()
            self.action_widget = None

    def _handle_text_search_copy(self, text):
        self.text_copied_and_searched.emit(text)
        self.cleanup_and_hide()

    def _handle_text_copy(self, text):
        self.text_copied.emit(text)
        self.cleanup_and_hide()

    def cleanup_and_hide(self):
        self.cleanup_action_widget()
        self.hide()
        self.selected_ocr_indices.clear()
        self.selection_rect = QRect()
        self.is_selecting_text = False
        self.is_selecting_region = False
