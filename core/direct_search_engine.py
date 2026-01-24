import os
import tempfile
import pyperclip
import webbrowser
import mss
from urllib.parse import quote_plus
from PIL import Image
from PySide6.QtCore import QRect, QThread, Signal
from PySide6.QtGui import QGuiApplication

from core.ocr_processor import OCRProcessor
from core.image_search import DirectImageSearchHandler

class SearchWorker(QThread):
    """Worker thread for processing search operations"""
    finished = Signal(bool, str)
    
    def __init__(self, search_engine, rect, image=None, text=None):
        super().__init__()
        self.search_engine = search_engine
        self.rect = rect
        self.image = image
        self.text = text

    def run(self):
        """Run search operation in thread"""
        try:
            if self.text:
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

class DirectSearchEngine:
    """Main search engine handling both text and direct image search"""
    
    def __init__(self):
        self.ocr_processor = None  # Lazy initialization
        self.image_handler = None  # Lazy initialization
        self.current_worker = None

    def _initialize_ocr(self):
        """Initialize OCR processor only when needed"""
        if self.ocr_processor is None:
            self.ocr_processor = OCRProcessor()

    def _initialize_image_handler(self):
        """Initialize image handler only when needed"""
        if self.image_handler is None:
            self.image_handler = DirectImageSearchHandler()

    def capture_region(self, rect: QRect):
        """Capture screen region and return PIL Image"""
        try:
            screen = QGuiApplication.primaryScreen()
            pixel_ratio = screen.devicePixelRatio()
            
            capture_rect = {
                "top": int(rect.top() * pixel_ratio),
                "left": int(rect.left() * pixel_ratio),
                "width": int(rect.width() * pixel_ratio),
                "height": int(rect.height() * pixel_ratio),
            }
            
            with mss.mss() as sct:
                sct_img = sct.grab(capture_rect)
                pil_img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                return pil_img
                
        except Exception as e:
            print(f"[ERROR] Screen capture failed: {e}")
            return None

    def process_selection(self, rect: QRect):
        """Process selected region for search"""
        print("[INFO] Processing selected region...")
        
        # Capture image
        captured_image = self.capture_region(rect)
        if not captured_image:
            print("[ERROR] Failed to capture region")
            return

        # Initialize OCR only when needed
        self._initialize_ocr()
        
        # Perform OCR
        ocr_text = self.ocr_processor.extract_text(captured_image)
        
        # Auto-copy text to clipboard
        if ocr_text.strip():
            try:
                pyperclip.copy(ocr_text.strip())
                print("[INFO] Text copied to clipboard")
            except Exception as e:
                print(f"[WARNING] Could not copy text: {e}")

        # Determine search type and execute
        if ocr_text.strip():
            print(f"[INFO] 🔍 Performing text search: {ocr_text[:40]}...")
            self._start_search_worker(rect, text=ocr_text.strip())
        else:
            print("[INFO] 🚀 Performing direct image search...")
            # Initialize image handler only when needed
            self._initialize_image_handler()
            self._start_search_worker(rect, image=captured_image)

    def _start_search_worker(self, rect, image=None, text=None):
        """Start search in worker thread"""
        if self.current_worker and self.current_worker.isRunning():
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

    def cleanup(self):
        """Cleanup resources and free memory - ONLY on app exit"""
        if self.ocr_processor:
            self.ocr_processor.cleanup()
        # Don't cleanup image_handler here - let browser stay open
        # if self.image_handler:
        #     self.image_handler.cleanup()
        if self.current_worker and self.current_worker.isRunning():
            self.current_worker.quit()
            self.current_worker.wait()