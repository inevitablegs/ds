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
        """Extract text from PIL Image using OCR. Returns list of structured results."""
        self._initialize_reader()
        
        try:
            # Convert to numpy array
            image_np = numpy.array(pil_image)
            
            # Perform OCR (Result: list of [bbox (4 points), text (str), conf (float)])
            result = self.reader.readtext(image_np)
            
            filtered_results = []
            for bbox, text, conf in result:
                if conf > 0.3:
                    # Bounding box is typically [[x1,y1], [x2,y2], [x3,y3], [x4,y4]].
                    # We approximate it as a simple QRect-compatible format: (x, y, w, h)
                    x_coords = [p[0] for p in bbox]
                    y_coords = [p[1] for p in bbox]
                    x_min = int(min(x_coords))
                    y_min = int(min(y_coords))
                    x_max = int(max(x_coords))
                    y_max = int(max(y_coords))
                    
                    filtered_results.append({
                        'text': text,
                        # Store rect as (x, y, w, h) tuple
                        'rect': (x_min, y_min, x_max - x_min, y_max - y_min), 
                        'conf': conf
                    })

            print(f"[INFO] OCR extracted {len(filtered_results)} text elements")
            
            # Clear large variables
            del image_np
            
            # We must adjust coordinates based on the system's device pixel ratio,
            # especially if the image was captured at native resolution.
            # Assuming the image passed here is the native full screen capture.
            
            return filtered_results
            
        except Exception as e:
            print(f"[ERROR] OCR processing failed: {e}")
            return []
    
    def cleanup(self):
        """Cleanup OCR reader to free memory"""
        if self.reader:
            try:
                # Deliberately try to clean up memory used by the model
                del self.reader
                self.reader = None
                print("[INFO] OCR reader cleaned up")
            except Exception:
                pass