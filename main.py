import sys
import os
import atexit
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PySide6.QtGui import QIcon, QAction, QPixmap, QPainter
from PySide6.QtCore import QLockFile, QDir, Qt, QPoint
import pyperclip # Needed here for copy-only action

class DirectSearchApplication:
    """Main application controller with system tray"""
    
    def __init__(self, app: QApplication, start_minimized=False):
        self.app = app
        print("[DEBUG] Initializing Direct Search Application...")
        
        # Set up system tray
        self.setup_system_tray()
        
        # Initialize core components as None (lazy loading)
        self.search_engine = None
        self.overlay = None
        self.hotkey_manager = None
        
        # Start minimal hotkey listener (lightweight)
        self.setup_minimal_hotkey_manager()
        
        if not start_minimized:
            self.show_notification("Direct Search", "Application started! Press Ctrl+Shift+Space to capture.")
        
        print("[DEBUG] Direct Search Application initialized in low-memory mode!")

    def setup_minimal_hotkey_manager(self):
        """Setup minimal hotkey manager without loading heavy dependencies"""
        try:
            from utils.hotkey_manager import HotkeyManager
            self.hotkey_manager = HotkeyManager()
            self.hotkey_manager.hotkey_pressed.connect(self.handle_show_overlay)
            self.hotkey_manager.start_listening()
            print("[INFO] Minimal hotkey manager started")
        except Exception as e:
            print(f"[WARNING] Failed to setup hotkey manager: {e}")

    def lazy_load_components(self):
        """Lazy load heavy components only when needed"""
        if self.search_engine is None:
            print("[DEBUG] 🚀 Lazy loading core components...")
            try:
                from core.direct_search_engine import DirectSearchEngine
                from overlay import OverlayWindow
                
                self.search_engine = DirectSearchEngine()
                self.overlay = OverlayWindow()
                
                # Connect signals
                # 1. Region selection (Image Search Mode)
                self.overlay.region_selected.connect(self.on_region_selected)
                
                # 2. Text Selection Actions (New)
                self.overlay.text_copied_and_searched.connect(self.on_text_search_copy)
                self.overlay.text_copied.connect(self.on_text_copy) 

                # 3. OCR results from Engine back to Overlay
                self.search_engine.ocr_results_available.connect(self.overlay.load_ocr_results)
                
                print("[DEBUG] Core components loaded successfully")
            except Exception as e:
                print(f"[ERROR] Failed to load core components: {e}")
                return False
        return True



    def create_default_icon(self):
        """Create a default icon programmatically if no icon file exists"""
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw a simple search icon (magnifying glass)
        painter.setBrush(Qt.blue)
        painter.setPen(Qt.darkBlue)
        painter.drawEllipse(8, 8, 48, 48)  # Outer circle
        
        painter.setBrush(Qt.white)
        painter.drawEllipse(16, 16, 32, 32)  # Inner circle
        
        # Draw handle (simplified - just a rectangle)
        painter.setBrush(Qt.blue)
        painter.drawRect(40, 40, 20, 8)  # Simple handle
        
        painter.end()
        return QIcon(pixmap)

    def setup_system_tray(self):
        """Setup system tray icon and menu"""
        # Create tray icon
        self.tray_icon = QSystemTrayIcon()
        
        # Try to load custom icon, fallback to default
        icon_path = self.get_icon_path()
        if os.path.exists(icon_path):
            self.tray_icon.setIcon(QIcon(icon_path))
            print(f"[INFO] Loaded icon from: {icon_path}")
        else:
            # Create a default icon programmatically
            print("[INFO] No icon file found, creating default icon")
            default_icon = self.create_default_icon()
            self.tray_icon.setIcon(default_icon)
        
        # Create context menu
        tray_menu = QMenu()
        
        # Show overlay action
        show_action = QAction("📷 Capture Screen", self.app)
        show_action.triggered.connect(self.handle_show_overlay)
        tray_menu.addAction(show_action)
        
        # Separator
        tray_menu.addSeparator()
        
        # Exit action
        exit_action = QAction("❌ Exit", self.app)
        exit_action.triggered.connect(self.cleanup_and_exit)
        tray_menu.addAction(exit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.setToolTip("Direct Search\nPress Ctrl+Shift+Space to capture")
        self.tray_icon.activated.connect(self.on_tray_activated)
        self.tray_icon.show()

    def get_icon_path(self):
        """Get path to application icon"""
        # Check multiple possible locations
        possible_paths = [
            # Development paths
            os.path.join(os.path.dirname(__file__), 'assets', 'tray_icon.ico'),
            os.path.join(os.path.dirname(__file__), 'assets', 'icon.ico'),
            os.path.join(os.path.dirname(__file__), 'tray_icon.ico'),
            os.path.join(os.path.dirname(__file__), 'icon.ico'),
            # For PyInstaller - look in the same directory as executable
            os.path.join(os.path.dirname(sys.executable), 'tray_icon.ico'),
            os.path.join(os.path.dirname(sys.executable), 'icon.ico'),
        ]
        
        # For PyInstaller bundled app
        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS
            possible_paths.extend([
                os.path.join(base_path, 'assets', 'tray_icon.ico'),
                os.path.join(base_path, 'assets', 'icon.ico'),
                os.path.join(base_path, 'tray_icon.ico'),
                os.path.join(base_path, 'icon.ico'),
            ])
        
        for path in possible_paths:
            if os.path.exists(path):
                return path
        
        return ""

    def on_tray_activated(self, reason):
        """Handle tray icon clicks"""
        if reason == QSystemTrayIcon.DoubleClick:
            self.handle_show_overlay()

    def show_notification(self, title, message):
        """Show system tray notification"""
        self.tray_icon.showMessage(title, message, QSystemTrayIcon.Information, 3000)

    def handle_show_overlay(self):
        """Show the capture overlay with lazy loading and immediate OCR trigger"""
        print("[DEBUG] 🎯 Activating overlay with lazy loading and OCR prep...")
        try:
            # 1. Lazy load components first
            if not self.lazy_load_components():
                self.show_notification("Error", "Failed to load application components")
                return
            
            # 2. Capture full screen image immediately (blocking but necessary for background)
            full_image = self.search_engine.capture_full_screen()
            if not full_image:
                self.show_notification("Error", "Failed to capture screen.")
                return
            
            # 3. Load captured image and geometry into overlay
            self.overlay.load_full_screen_capture(full_image)
            
            # 4. Show the overlay (User sees the screen and wait cursor/loading state)
            self.overlay.show_overlay()
            
            # 5. Start background OCR process on the full image
            self.search_engine.start_full_screen_ocr(full_image) 
            
            print("[DEBUG] Overlay activated and OCR worker started.")
            
        except Exception as e:
            print(f"[ERROR] Failed to show overlay: {e}")
            self.show_notification("Error", "Failed to show overlay")


    def on_region_selected(self, rect):
        """Handle region selection for Image Search"""
        print(f"[DEBUG] Region selected (Image Search Mode): {rect}")
        if self.search_engine:
            self.search_engine.process_selection(rect)
        else:
            print("[ERROR] Search engine not initialized")
            
    def on_text_search_copy(self, text):
        """Handle text search and copy request from the overlay menu"""
        print(f"[DEBUG] Text selected: Copy & Search: {text[:40]}...")
        if self.search_engine:
            # Engine handles both copy and search execution
            self.search_engine.search_text_and_copy(text)
        else:
            self.show_notification("Error", "Search engine not ready.")
            
    def on_text_copy(self, text):
        """Handle text copy only request from the overlay menu"""
        print(f"[DEBUG] Text selected: Copy Only: {text[:40]}...")
        try:
            pyperclip.copy(text.strip())
            self.show_notification("Copied", f"'{text.strip()[:50]}...' copied to clipboard.")
        except Exception as e:
            print(f"[WARNING] Could not copy text: {e}")
            self.show_notification("Error", "Failed to copy text.")


    def cleanup_and_exit(self):
        """Cleanup and exit application"""
        self.cleanup()
        self.app.quit()

    def cleanup(self):
        """Cleanup resources"""
        if self.search_engine:
            self.search_engine.cleanup()
        if self.hotkey_manager:
            self.hotkey_manager.stop_listening()


# Follwing code is for develoment phase - inevitablegs

        
def main():
    print("🚀 Starting Direct Search Application (Lazy Load Mode)")
    
    # Single instance lock
    lock_file = QLockFile(os.path.join(QDir.tempPath(), "direct-search-app.lock"))
    if not lock_file.tryLock(100):
        print("[ERROR] Another instance is already running.")
        sys.exit(0)
    
    # Check for minimized start
    start_minimized = "--minimized" in sys.argv or "/minimized" in sys.argv
    
    # Create application
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("Direct Search")
    app.setApplicationDisplayName("Direct Search")

    # Create main controller with lazy loading
    main_controller = DirectSearchApplication(app, start_minimized=start_minimized)

    print("✨ Direct Search Application is ready!")
    print("📖 Running in background with minimal memory...")
    print("   🎯 Press Ctrl+Shift+Space to capture")
    print("   📌 Double-click tray icon to capture") 
    print("   ❌ Right-click tray icon to exit")
    print("   💾 Memory: Lightweight mode (heavy components load on demand)")
    
    # Ensure cleanup on exit
    atexit.register(main_controller.cleanup)

    # Start the application
    sys.exit(app.exec())

if __name__ == "__main__":
    main()