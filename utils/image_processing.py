from PIL import Image

class ImageProcessor:
    @staticmethod
    def enhance_for_ocr(pil_image: Image.Image):
        """Basic enhancement for OCR"""
        return pil_image
    
    @staticmethod
    def enhance_for_search(pil_image: Image.Image):
        """Basic enhancement for search"""
        if pil_image.mode != 'RGB':
            pil_image = pil_image.convert('RGB')
        return pil_image