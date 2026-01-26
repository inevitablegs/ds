from PySide6.QtWidgets import QWidget, QToolButton, QHBoxLayout, QFrame
from PySide6.QtCore import Qt, QRect, QPoint, Signal, QSize, QMargins
from PySide6.QtGui import QPainter, QColor, QPen, QGuiApplication, QPixmap, QCursor, QFont
import enum
from PIL.ImageQt import ImageQt

class OverlayMode(enum.Enum):
    LOADING = 0
    TEXT_SELECTION = 1
    REGION_SELECTION = 2

class TextActionWidget(QFrame):
    """Small widget for showing text actions"""
    search_triggered = Signal(str)
    copy_triggered = Signal(str)

    def __init__(self, selected_text: str):
        super().__init__()
        self.selected_text = selected_text
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool | Qt.Popup)
        self.setStyleSheet("QFrame { background-color: #333; border: 1px solid #00F; border-radius: 5px; padding: 5px; }")
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(10)

        # Search Button (Copy & Search)
        search_btn = QToolButton(self)
        search_btn.setText("🔍 Copy & Search")
        search_btn.setStyleSheet("QToolButton { background-color: #0078D4; color: white; border-radius: 3px; padding: 5px 10px; } QToolButton:hover { background-color: #005A9E; }")
        search_btn.clicked.connect(lambda: self.search_triggered.emit(self.selected_text))

        # Copy Button
        copy_btn = QToolButton(self)
        copy_btn.setText("📋 Copy Text")
        copy_btn.setStyleSheet("QToolButton { background-color: #555; color: white; border-radius: 3px; padding: 5px 10px; } QToolButton:hover { background-color: #777; }")
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
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool |
            Qt.Popup 
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_DeleteOnClose)

        self.mode = OverlayMode.LOADING
        
        self.full_screen_pixmap = None
        self.ocr_results = [] 
        
        # Region selection state
        self.begin_pos = QPoint()
        self.end_pos = QPoint()
        self.is_selecting_region = False

        # Text selection state
        self.hovered_ocr_index = -1
        self.selected_ocr_index = -1
        self.is_selecting_text = False
        self.selected_text_content = ""
        
        self.mode_button = self._setup_mode_button()
        self.action_widget = None

    def _setup_mode_button(self):
        """Setup the button to switch modes"""
        btn = QToolButton(self)
        btn.setStyleSheet("""
            QToolButton { 
                background-color: #4CAF50; color: white; border-radius: 5px; 
                padding: 8px 15px; font-weight: bold; 
                border: 2px solid #388E3C;
            }
            QToolButton:hover { 
                background-color: #66BB6A; 
            }
        """)
        btn.setVisible(False)
        btn.clicked.connect(self.toggle_mode)
        return btn
    
    def set_mode(self, new_mode: OverlayMode):
        """Switch the overlay mode"""
        self.mode = new_mode
        self.is_selecting_region = False
        self.selected_ocr_index = -1
        self.cleanup_action_widget() # Ensure floating widget is closed

        if new_mode == OverlayMode.TEXT_SELECTION:
            print("[DEBUG] Switched to TEXT SELECTION Mode.")
            self.mode_button.setText("📷 Switch to Image Search Area")
            self.mode_button.setVisible(True)
            self.setCursor(Qt.IBeamCursor)
        elif new_mode == OverlayMode.REGION_SELECTION:
            print("[DEBUG] Switched to REGION SELECTION Mode.")
            self.mode_button.setText("📝 Switch to Text Selection Mode")
            self.mode_button.setVisible(True)
            self.setCursor(Qt.CrossCursor)
        elif new_mode == OverlayMode.LOADING:
            self.mode_button.setVisible(False)
            self.setCursor(Qt.WaitCursor)
            
        self.update_mode_button_position()
        self.update()

    def toggle_mode(self):
        """Handler for switching modes"""
        if self.mode == OverlayMode.REGION_SELECTION:
            self.set_mode(OverlayMode.TEXT_SELECTION)
        elif self.mode == OverlayMode.TEXT_SELECTION:
            self.set_mode(OverlayMode.REGION_SELECTION)

    def update_mode_button_position(self):
        """Center the mode button at the top"""
        if self.mode_button.isVisible():
            button_size = self.mode_button.sizeHint()
            x = (self.width() - button_size.width()) // 2
            y = 10 
            self.mode_button.move(x, y)

    def load_full_screen_capture(self, pil_image):
        """Load the background image and set geometry."""
        from PIL.ImageQt import ImageQt
        
        # 1. Get the screen geometry (logical pixels)
        desktop_geometry = self.get_desktop_geometry()
        self.setGeometry(desktop_geometry)
        
        # 2. Convert PIL image to QPixmap
        qimage = ImageQt(pil_image)
        native_pixmap = QPixmap.fromImage(qimage)
        
        # 3. Get primary screen's DPI ratio to understand the scale
        primary_screen = QGuiApplication.primaryScreen()
        pixel_ratio = primary_screen.devicePixelRatio()
        
        print(f"[DEBUG] Screen geometry: {desktop_geometry}, Image size: {pil_image.size}, DPI: {pixel_ratio}")
        
        # 4. Scale the pixmap to match logical screen size
        # The captured image is in physical pixels, we need to scale down to logical pixels
        logical_width = desktop_geometry.width()
        logical_height = desktop_geometry.height()
        
        self.full_screen_pixmap = native_pixmap.scaled(
            logical_width, 
            logical_height, 
            Qt.KeepAspectRatio,  # Changed from KeepAspectRatioByExpanding
            Qt.SmoothTransformation
        )
        
        # Start in loading state, wait for OCR results
        self.set_mode(OverlayMode.LOADING)     
        
    def load_ocr_results(self, results: list):
        """Load OCR results and switch mode based on success"""
        self.ocr_results = results
        if results:
            self.set_mode(OverlayMode.TEXT_SELECTION)
        else:
            # Fallback if OCR found nothing
            self.set_mode(OverlayMode.REGION_SELECTION)
        self.update()

    def show_overlay(self):
        """Shows the overlay across all screens."""
        if not self.full_screen_pixmap: return
        self.showFullScreen()
        self.activateWindow()
        self.update_mode_button_position()

    def get_desktop_geometry(self) -> QRect:
        """Calculates the bounding box of all connected screens."""
        total_geometry = QRect()
        for screen in QGuiApplication.screens():
            total_geometry = total_geometry.united(screen.geometry())
        return total_geometry

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 1. Draw the captured full screen image as the background
        if self.full_screen_pixmap:
            # Calculate centered position
            x = (self.width() - self.full_screen_pixmap.width()) // 2
            y = (self.height() - self.full_screen_pixmap.height()) // 2
            painter.drawPixmap(x, y, self.full_screen_pixmap)
            
        if self.mode == OverlayMode.LOADING:
            # Draw a heavy dark overlay while waiting for OCR
            overlay_color = QColor(0, 0, 0, 150)
            painter.fillRect(self.rect(), overlay_color)
            return

        if self.mode == OverlayMode.TEXT_SELECTION:
            # 2a. Draw slight dark overlay to make highlights pop
            overlay_color = QColor(0, 0, 0, 80)
            painter.fillRect(self.rect(), overlay_color)

            # Draw OCR bounding boxes and selection/hover feedback
            for i, item in enumerate(self.ocr_results):
                x, y, w, h = item['rect']
                rect = QRect(x, y, w, h)
                
                # Draw hover feedback
                if i == self.hovered_ocr_index:
                    painter.setBrush(QColor(255, 255, 255, 60))
                    painter.setPen(Qt.NoPen)
                    painter.drawRect(rect)
                
                # Draw selection feedback
                if i == self.selected_ocr_index:
                    painter.setBrush(QColor(0, 120, 215, 120)) # Blue highlight
                    painter.setPen(Qt.NoPen)
                    painter.drawRect(rect)

        elif self.mode == OverlayMode.REGION_SELECTION:
            # 2b. Draw semi-transparent overlay AND the selection rectangle (old logic)
            overlay_color = QColor(0, 0, 0, 80)
            painter.fillRect(self.rect(), overlay_color)

            if self.is_selecting_region:
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

    # --- Mouse Handlers ---
    def mousePressEvent(self, event):
        self.cleanup_action_widget()
        
        if self.mode == OverlayMode.REGION_SELECTION:
            self.is_selecting_region = True
            self.begin_pos = event.position().toPoint()
            self.end_pos = self.begin_pos
            self.update()
        elif self.mode == OverlayMode.TEXT_SELECTION:
            # Start text selection
            self.is_selecting_text = True
            self.selected_ocr_index = self.hovered_ocr_index
            self.update()

    def mouseMoveEvent(self, event):
        mouse_pos = event.position().toPoint()
        
        if self.mode == OverlayMode.REGION_SELECTION and self.is_selecting_region:
            self.end_pos = mouse_pos
            self.update()
            
        elif self.mode == OverlayMode.TEXT_SELECTION:
            # Handle hover feedback
            new_hover_index = self._get_ocr_index_at_point(mouse_pos)
            if new_hover_index != self.hovered_ocr_index:
                self.hovered_ocr_index = new_hover_index
                self.update()

    def _get_ocr_index_at_point(self, point: QPoint):
        """Find the index of the OCR result bounding box containing the point"""
        for i, item in enumerate(self.ocr_results):
            x, y, w, h = item['rect']
            rect = QRect(x, y, w, h)
            if rect.contains(point):
                return i
        return -1

    def mouseReleaseEvent(self, event):
        if self.mode == OverlayMode.REGION_SELECTION and self.is_selecting_region:
            self.is_selecting_region = False
            selection_rect = QRect(self.begin_pos, self.end_pos).normalized()
            self.cleanup_and_hide()
            
            if selection_rect.width() > 5 and selection_rect.height() > 5:
                self.region_selected.emit(selection_rect) # Trigger Image Search
            
        elif self.mode == OverlayMode.TEXT_SELECTION and self.is_selecting_text:
            self.is_selecting_text = False
            
            if self.selected_ocr_index != -1:
                item = self.ocr_results[self.selected_ocr_index]
                self.selected_text_content = item['text']
                
                # Show action widget near the selection
                x, y, w, h = item['rect']
                selected_rect = QRect(x, y, w, h)
                self._show_text_action_widget(selected_rect)
            else:
                 # If user clicked empty space, deselect
                 self.update()


    def _show_text_action_widget(self, selection_rect: QRect):
        """Show the floating widget with Search/Copy options"""
        self.cleanup_action_widget()
            
        self.action_widget = TextActionWidget(self.selected_text_content)
        self.action_widget.search_triggered.connect(self._handle_text_search_copy)
        self.action_widget.copy_triggered.connect(self._handle_text_copy)
        
        # Position widget just below the selected text
        widget_x = selection_rect.left()
        widget_y = selection_rect.bottom() + 5
        
        # Adjust position if too close to the screen edge
        if widget_x + self.action_widget.width() > self.width():
            widget_x = self.width() - self.action_widget.width() - 10
        if widget_y + self.action_widget.height() > self.height():
             # If too low, put it above the text
            widget_y = selection_rect.top() - self.action_widget.height() - 5
            
        self.action_widget.move(widget_x, widget_y)
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
        """Hides overlay and cleans temporary state"""
        self.cleanup_action_widget()
        self.hide()
        self.selected_ocr_index = -1
        self.hovered_ocr_index = -1
        self.is_selecting_text = False
        self.is_selecting_region = False
        self.setCursor(Qt.ArrowCursor) 

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.cleanup_and_hide()
        
        # Toggle modes with M key
        elif event.key() == Qt.Key_M and self.mode != OverlayMode.LOADING:
            self.toggle_mode()