import os
import tempfile
import time
import webbrowser
from PIL import Image
import threading
import sys

# Selenium imports for direct image search
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service as ChromeService

class DirectImageSearchHandler:
    """Handles DIRECT image search with automatic upload to Google Images/Lens"""
    
    def __init__(self):
        self.temp_dir = tempfile.gettempdir()
        self.driver = None
        self.selenium_available = self._check_selenium()
    
    def _check_selenium(self):
        """Check if Selenium is available"""
        try:
            from selenium import webdriver
            return True
        except ImportError:
            print("[WARNING] Selenium not available - direct image search disabled")
            return False
    
    def _close_driver(self):
        """Helper to safely close the driver."""
        if self.driver:
            try:
                self.driver.quit()
                self.driver = None
            except:
                pass

    def perform_direct_image_search(self, pil_image: Image.Image):
        """
        Robust DIRECT image upload using Google Lens, automatically clicks search button
        """
        
        temp_image_path = self._save_temp_image(pil_image)
        print(f"📁 Image saved to: {temp_image_path}")
        
        if not self.selenium_available:
            print("[ERROR] Selenium not available. Falling back to manual method.")
            return self._fallback_image_search(pil_image)

        if not self._setup_driver():
            print("[ERROR] Failed to set up browser driver. Falling back.")
            return self._fallback_image_search(pil_image)

        try:
            print("🌐 Navigating to Google")
            self.driver.get("https://google.com")
            
            # Wait for page to load
            time.sleep(2)
            
            # --- Robust File Upload Logic ---
            
            # 1. Locate the file input element (it is usually hidden)
            print("🔍 Searching for file upload input...")
            file_input = WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='file']"))
            )
            
            # Ensure the input has a unique ID for JS manipulation
            input_id = "direct_search_upload_input"
            self.driver.execute_script(f"arguments[0].id = '{input_id}';", file_input)

            print("📤 Sending file path to input...")
            # 2. Send the file path
            file_input.send_keys(temp_image_path)
            
            
            
            # Wait for upload to complete and upload button to appear
            print("⏳ Waiting for upload to complete...")
            time.sleep(5)
            
           
            
            # --- Wait for Results ---
            
            # Wait for the URL to change to the results page (/lens/search/).
            print("⏳ Waiting for search results (URL change to /lens/search)...")
            
            WebDriverWait(self.driver, 30).until(
                EC.url_contains('/search')
            )
            
            # Now wait briefly for the content structure to confirm full page load
            try:
                search_results_selector = By.CSS_SELECTOR, "#rcnt, .tS4Oec, .GorPzc, .F8EnNe"
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located(search_results_selector)
                )
            except TimeoutException:
                 print("⚠️ URL changed successfully, but result container took longer to render.")

            print("✅ Search completed and results loaded successfully!")
            print("📖 Browser will stay open - close manually when done")
            return True

        except TimeoutException:
            print("❌ Timeout: Search results did not load in time. Check the browser window.")
            # Try manual fallback in the browser
            self._show_manual_instructions(temp_image_path)
            return False
        except Exception as e:
            print(f"❌ Automated search failed: {e}")
            self._close_driver()
            return self._fallback_image_search(pil_image)
    
    def _show_manual_instructions(self, image_path):
        """Show instructions for manual search if automated fails"""
        print("\n" + "="*60)
        print("🔧 MANUAL SEARCH INSTRUCTIONS:")
        print("="*60)
        print("1. Browser window is open to Google Lens")
        print(f"2. Image saved at: {image_path}")
        print("3. Drag and drop the image file into the browser")
        print("4. Click the search button manually")
        print("="*60 + "\n")
    
    def _setup_driver(self):
        """Setup Chrome driver with better compatibility"""
        try:
            from selenium.webdriver.chrome.options import Options as ChromeOptions
            
            chrome_options = ChromeOptions()
            
            # Essential arguments
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            
            # Make it look more like a real browser
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # User agent to appear as regular Chrome
            chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            
            # Disable automation flags
            prefs = {
                "credentials_enable_service": False,
                "profile.password_manager_enabled": False
            }
            chrome_options.add_experimental_option("prefs", prefs)
            
            # Try multiple driver initialization methods
            try:
                # Method 1: Use webdriver-manager
                from selenium.webdriver.chrome.service import Service
                from webdriver_manager.chrome import ChromeDriverManager
                service = Service(ChromeDriverManager().install())
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
                
            except Exception as e:
                print(f"[INFO] Webdriver-manager failed, trying system Chrome: {e}")
                # Method 2: Use system Chrome
                try:
                    self.driver = webdriver.Chrome(options=chrome_options)
                except Exception as e2:
                    print(f"[INFO] System Chrome failed: {e2}")
                    # Method 3: Try Firefox as fallback
                    try:
                        from selenium import webdriver as firefox_driver
                        from selenium.webdriver.firefox.options import Options as FirefoxOptions
                        firefox_options = FirefoxOptions()
                        self.driver = firefox_driver.Firefox(options=firefox_options)
                    except:
                        return False
            
            # Hide automation indicators
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            # Set reasonable timeouts
            self.driver.set_page_load_timeout(20)
            self.driver.implicitly_wait(5)
            
            print("[INFO] Browser driver initialized successfully")
            return True
            
        except Exception as e:
            print(f"[ERROR] Driver setup failed completely: {e}")
            return False
            
    def _get_safe_temp_dir(self):
        """Get a safe temp directory that works in .exe"""
        if getattr(sys, 'frozen', False):
            # Running as .exe - use user's temp directory
            return os.path.join(os.path.expanduser("~"), "AppData", "Local", "Temp")
        else:
            # Running as script
            return tempfile.gettempdir()
        
    def _save_temp_image(self, pil_image: Image.Image):
        """Save image to temporary file"""
        temp_dir = self._get_safe_temp_dir()
        temp_path = os.path.join(temp_dir, f"search_image_{int(time.time())}.jpg")
        
        # Optimize image
        img = pil_image.copy()
        max_size = (1200, 800)
        if img.size[0] > max_size[0] or img.size[1] > max_size[1]:
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
        
        img.save(temp_path, "JPEG", quality=85)
        return temp_path
    
    def _fallback_image_search(self, pil_image: Image.Image):
        """Fallback method when direct upload fails"""
        try:
            # Save to temp for manual upload
            temp_dir = self._get_safe_temp_dir()
            image_path = os.path.join(temp_dir, "search_image.jpg")
            pil_image.save(image_path, "JPEG", quality=90)
            
            # Open Google Lens with instructions
            webbrowser.open("https://lens.google.com")
            
            print("📁 Image saved for manual upload:")
            print(f"   📍 Location: {image_path}")
            print("   🌐 Google Lens opened - drag and drop the image file")
            print("   🎯 Click the search button manually")
            print("   📖 Close the browser manually when done searching")
            
            return True
        except Exception as e:
            print(f"❌ Fallback method failed: {e}")
            # Last resort - just open Google Lens
            webbrowser.open("https://lens.google.com")
            return False
    
    def cleanup(self):
        """Clean up browser driver and temp images"""
        self._close_driver()
        
        # Clean temp files at exit
        if hasattr(self, "temp_files"):
            for f in self.temp_files:
                if os.path.exists(f):
                    try:
                        os.remove(f)
                    except:
                        pass
            self.temp_files.clear()
            print("[INFO] Temporary images cleaned up")