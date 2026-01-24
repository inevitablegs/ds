import easyocr
import numpy
from PIL import Image

class OCRProcessor:
    """Handles OCR text extraction from images with memory optimization"""
    
    def __init__(self):
        self.reader = None
        
    def _initialize_reader(self):
        """Initialize EasyOCR reader only when needed"""
        if self.reader is None:
            print("[INFO] Initializing EasyOCR Reader...")
            # Use CPU only to save memory and avoid GPU issues
            self.reader = easyocr.Reader(['en'], gpu=False)
            print("[INFO] EasyOCR Reader initialized.")
    
    def extract_text(self, pil_image: Image.Image):
        """Extract text from PIL Image using OCR"""
        self._initialize_reader()
        
        try:
            # Convert to numpy array
            image_np = numpy.array(pil_image)
            
            # Perform OCR with confidence threshold
            result = self.reader.readtext(image_np)
            
            # Filter results by confidence
            recognized_texts = [text for bbox, text, conf in result if conf > 0.3]
            full_text = "\n".join(recognized_texts)
            
            print(f"[INFO] OCR extracted {len(recognized_texts)} text elements")
            
            # Clear large variables
            del image_np
            del result
            
            return full_text
            
        except Exception as e:
            print(f"[ERROR] OCR processing failed: {e}")
            return ""
    
    def cleanup(self):
        """Cleanup OCR reader to free memory"""
        if self.reader:
            try:
                del self.reader
                self.reader = None
                print("[INFO] OCR reader cleaned up")
            except:
                pass