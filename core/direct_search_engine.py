import os
import tempfile
import pyperclip
import webbrowser
import mss
from urllib.parse import quote_plus
from PIL import Image
from PySide6.QtCore import QRect, QThread, Signal, QObject 
from PySide6.QtGui import QGuiApplication, QScreen

from core.ocr_processor import OCRProcessor
from core.image_search import DirectImageSearchHandler

class SearchWorker(QThread):
    """Worker thread for processing search operations, including initial OCR"""
    finished = Signal(bool, str)
    ocr_results_ready = Signal(list) 
    
    def __init__(self, search_engine, rect=None, image=None, text=None, full_ocr_task=False):
        super().__init__()
        self.search_engine = search_engine
        self.rect = rect
        self.image = image
        self.text = text
        self.full_ocr_task = full_ocr_task

    def run(self):
        """Run search operation in thread"""
        try:
            if self.full_ocr_task:
                self.search_engine._initialize_ocr()
                results = self.search_engine.ocr_processor.extract_text(self.image)
                
                # Get the primary screen's DPI ratio for coordinate scaling
                primary_screen = QGuiApplication.primaryScreen()
                pixel_ratio = primary_screen.devicePixelRatio()
                
                # Calculate the scale factor between OCR image and overlay
                # OCR runs on native resolution, overlay uses logical resolution
                ocr_image_width = self.image.width
                overlay_width = primary_screen.geometry().width()
                
                # Scale factor is the ratio between overlay (logical) and image (native) width
                scale_factor = overlay_width / ocr_image_width
                
                scaled_results = []
                for item in results:
                    x, y, w, h = item['rect']
                    # Scale coordinates from OCR image space to overlay (logical) space
                    item['rect'] = (
                        int(x * scale_factor), 
                        int(y * scale_factor),
                        int(w * scale_factor), 
                        int(h * scale_factor)
                    )
                    scaled_results.append(item)
                        
                self.ocr_results_ready.emit(scaled_results)
                self.finished.emit(True, "Full screen OCR completed.")
                
            elif self.text:
                success = self.search_engine.search_text(self.text)
                self.finished.emit(success, f"Text search: {self.text[:30]}...")
            elif self.image:
                success = self.search_engine.search_image(self.image)
                self.finished.emit(success, "Direct image search")
            else:
                self.finished.emit(False, "No content to search")
        except Exception as e:
            print(f"[ERROR] Search worker error: {e}")
            self.finished.emit(False, f"Error: {str(e)}")

class DirectSearchEngine(QObject):
    """Main search engine handling both text and direct image search"""
    
    ocr_results_available = Signal(list) # Signal to main app

    def __init__(self):
        super().__init__()
        self.ocr_processor = None
        self.image_handler = None
        self.current_worker = None

    def _initialize_ocr(self):
        """Initialize OCR processor only when needed"""
        if self.ocr_processor is None:
            self.ocr_processor = OCRProcessor()

    def _initialize_image_handler(self):
        """Initialize image handler only when needed"""
        if self.image_handler is None:
            self.image_handler = DirectImageSearchHandler()

    def capture_full_screen(self):
        """Capture the entire screen area at native resolution."""
        try:
            # Use mss to capture all monitors
            with mss.mss() as sct:
                # Capture all monitors as one image
                sct_img = sct.grab(sct.monitors[0])  # monitors[0] is all screens combined
                
                pil_img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                return pil_img
                
        except Exception as e:
            print(f"[ERROR] Full screen capture failed: {e}")
            return None

    def capture_region(self, rect: QRect):
        """Capture screen region based on QRect (used for Image Search)"""
        try:
            # Find which screen contains the center of the selection
            target_screen = None
            center_point = rect.center()
            
            for screen in QGuiApplication.screens():
                screen_geometry = screen.geometry()
                if screen_geometry.contains(center_point):
                    target_screen = screen
                    break
            
            if not target_screen:
                # Fallback to primary screen
                target_screen = QGuiApplication.primaryScreen()
            
            # Get the screen's DPI ratio
            pixel_ratio = target_screen.devicePixelRatio()
            
            # The input rect is in logical coordinates (same as overlay)
            # We need to convert it to screen-specific coordinates
            screen_geometry = target_screen.geometry()
            
            # Calculate screen-relative coordinates in LOGICAL pixels
            screen_relative_logical = QRect(
                rect.x() - screen_geometry.x(),
                rect.y() - screen_geometry.y(),
                rect.width(),
                rect.height()
            )
            
            # Convert logical coordinates to PHYSICAL coordinates for mss
            # mss expects physical pixels, so multiply by DPI ratio
            capture_rect = {
                "top": int(screen_relative_logical.top() * pixel_ratio),
                "left": int(screen_relative_logical.left() * pixel_ratio),
                "width": int(screen_relative_logical.width() * pixel_ratio),
                "height": int(screen_relative_logical.height() * pixel_ratio),
            }
            
            print(f"[DEBUG] Capture rect - Logical: {screen_relative_logical}, Physical: {capture_rect}, DPI: {pixel_ratio}")
            
            with mss.mss() as sct:
                # Get monitor index for this screen
                monitors = sct.monitors
                monitor_index = 1  # Default to primary monitor
                
                # Find the correct monitor based on screen position
                for i in range(1, len(monitors)):  # Skip monitor 0 (all screens)
                    monitor = monitors[i]
                    # Check if this monitor matches our target screen's position
                    if (abs(monitor["left"] - screen_geometry.x() * pixel_ratio) < 10 and 
                        abs(monitor["top"] - screen_geometry.y() * pixel_ratio) < 10):
                        monitor_index = i
                        break
                
                # Add monitor number to capture rect
                capture_rect["mon"] = monitor_index
                
                sct_img = sct.grab(capture_rect)
                pil_img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                
                print(f"[DEBUG] Captured image size: {pil_img.size}")
                return pil_img
                
        except Exception as e:
            print(f"[ERROR] Screen capture failed: {e}")
            return None

    def _get_screen_index(self, screen):
        """Get the screen index for mss"""
        screens = QGuiApplication.screens()
        for i, s in enumerate(screens):
            if s == screen:
                return i
        return 1  # Default to primary screen if not found

    def start_full_screen_ocr(self, captured_image):
        """Starts the initial OCR process on the full captured image."""
        if self.current_worker and self.current_worker.isRunning():
            self.current_worker.quit()
            self.current_worker.wait()
            
        print("[INFO] Starting full screen OCR worker...")
        self.current_worker = SearchWorker(self, image=captured_image, full_ocr_task=True)
        self.current_worker.ocr_results_ready.connect(self._on_full_ocr_complete)
        self.current_worker.finished.connect(lambda s, m: print(f"[INFO] OCR Worker Status: {m}"))
        self.current_worker.start()

    def _on_full_ocr_complete(self, results):
        """Handle full screen OCR completion"""
        print(f"[INFO] Initial OCR returned {len(results)} items.")
        self.ocr_results_available.emit(results)
        
    def process_selection(self, rect: QRect):
        """Process selected region for direct image search (Region Mode)"""
        print(f"[DEBUG] Processing selection at: {rect}")
        print(f"[DEBUG] Screen info: {self.get_screen_info()}")
        
        captured_image = self.capture_region(rect)
        if not captured_image:
            print("[ERROR] Failed to capture region")
            return

        self._initialize_image_handler()
        self._start_search_worker(rect, image=captured_image)

    def get_screen_info(self):
        """Get information about all screens for debugging"""
        screens = QGuiApplication.screens()
        info = []
        for i, screen in enumerate(screens):
            geometry = screen.geometry()
            info.append({
                'index': i,
                'name': screen.name(),
                'geometry': (geometry.x(), geometry.y(), geometry.width(), geometry.height()),
                'dpi': screen.devicePixelRatio(),
                'logical_dpi': screen.logicalDotsPerInch(),
                'physical_dpi': screen.physicalDotsPerInch()
            })
        return info

    def search_text_and_copy(self, query):
        """Copy text and perform Google search (used by Overlay menu)"""
        if not query.strip():
            return False
            
        try:
            pyperclip.copy(query.strip())
            print("[INFO] Text copied to clipboard")
        except Exception as e:
            print(f"[WARNING] Could not copy text: {e}")
            
        return self.search_text(query)

    def search_text(self, query):
        """Search text with Google"""
        if not query.strip():
            return False
        
        try:
            clean_query = query.strip()
            encoded_query = quote_plus(clean_query)
            url = f"https://www.google.com/search?q={encoded_query}"
            webbrowser.open(url)
            print(f"[INFO] 🔍 Google text search: '{clean_query[:50]}{'...' if len(clean_query) > 50 else ''}'")
            return True
        except Exception as e:
            print(f"[ERROR] Text search failed: {e}")
            return False

    def search_image(self, pil_image):
        """Perform direct reverse image search"""
        if pil_image:
            print("🚀 Starting direct image search...")
            return self.image_handler.perform_direct_image_search(pil_image)
        else:
            print("[WARNING] No image provided for reverse search")
            return False
            
    def _start_search_worker(self, rect, image=None, text=None):
        """Start search in worker thread"""
        if self.current_worker and self.current_worker.isRunning() and not self.current_worker.full_ocr_task:
            self.current_worker.quit()
            self.current_worker.wait()
            
        if self.current_worker and self.current_worker.full_ocr_task and self.current_worker.isRunning():
             # If a new search request comes in while OCR is running, we stop the OCR thread
             self.current_worker.quit()
             self.current_worker.wait()
            
        self.current_worker = SearchWorker(self, rect, image, text)
        self.current_worker.finished.connect(self._on_search_complete)
        self.current_worker.start()

    def _on_search_complete(self, success, message):
        """Handle search completion"""
        if success:
            print(f"✅ {message} completed successfully!")
        else:
            print(f"❌ {message} failed")

    def cleanup(self):
        """Cleanup resources and free memory - ONLY on app exit"""
        if self.ocr_processor:
            self.ocr_processor.cleanup()
        if self.current_worker and self.current_worker.isRunning():
            self.current_worker.quit()
            self.current_worker.wait()