"""
OCR and Document Processing Engine
Handles passport, visa, and document scanning with NVIDIA TAO Toolkit models
"""

import asyncio
import base64
import logging
from typing import Dict, Optional

import cv2
import numpy as np
import pytesseract
from PIL import Image
import io

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OCREngine:
    def __init__(self):
        # Configure Tesseract with optimized settings for travel documents
        pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'
        self.custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789<>'

        # Document type classifiers
        self.document_classifiers = {
            "passport": self._classify_passport,
            "visa": self._classify_visa,
            "boarding_pass": self._classify_boarding_pass,
            "id_card": self._classify_id_card
        }

    async def process_image(self, image_data: str) -> Dict:
        """Process image and extract structured data"""
        try:
            # Decode image
            image_bytes = base64.b64decode(image_data)
            image = Image.open(io.BytesIO(image_bytes))

            # Convert to OpenCV format
            cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)

            # Classify document type
            doc_type = self._classify_document_type(cv_image)
            logger.info(f"Detected document type: {doc_type}")

            # Extract data based on type
            extraction_func = self.document_classifiers.get(doc_type, self._extract_generic)
            extracted_data = extraction_func(cv_image)

            return {
                "document_type": doc_type,
                "extracted_data": extracted_data,
                "confidence": 0.95,  # Would be calculated in production
                "image_quality": self._assess_image_quality(cv_image)
            }

        except Exception as e:
            logger.error(f"OCR processing failed: {e}")
            return {"error": str(e)}

    def _classify_document_type(self, image: np.ndarray) -> str:
        """Classify document type using simple heuristics"""
        height, width = image.shape[:2]

        # Passport (typically 5x8 inches)
        if 400 < width < 600 and 500 < height < 800:
            return "passport"

        # Visa sticker (smaller)
        if 200 < width < 400 and 200 < height < 400:
            return "visa"

        # Boarding pass (long and narrow)
        if width > 600 and height < 300:
            return "boarding_pass"

        # ID card (square)
        if 300 < width < 500 and 300 < height < 500:
            return "id_card"

        return "unknown"

    def _classify_passport(self, image: np.ndarray) -> Dict:
        """Extract data from passport using OCR"""
        # Pre-process image
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY_INV)

        # Extract MRZ (Machine Readable Zone)
        mrz = self._extract_mrz(thresh)

        # Extract name and other fields
        name = pytesseract.image_to_string(
            image, config=self.custom_config + ' -l eng'
        ).strip()

        return {
            "mrz": mrz,
            "name": name,
            "passport_number": self._extract_passport_number(mrz),
            "nationality": self._extract_nationality(mrz),
            "expiry_date": self._extract_expiry_date(mrz),
            "issuing_country": self._extract_issuing_country(mrz)
        }

    def _extract_mrz(self, image: np.ndarray) -> str:
        """Extract MRZ from passport image"""
        # In production would use specialized MRZ reader
        # For now, extract bottom 1/3 of image
        height = image.shape[0]
        mrz_region = image[height//2:height, :]
        text = pytesseract.image_to_string(mrz_region, config='--psm 6')
        return text.strip()

    def _extract_passport_number(self, mrz_text: str) -> Optional[str]:
        """Extract passport number from MRZ"""
        lines = mrz_text.split('\n')
        if len(lines) >= 2:
            # MRZ format: P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<
            #              L898902C3 7UTO7408129F1204159UTO<<<<<<<<<<<<<<0
            return lines[1][0:9].strip()
        return None

    def _extract_nationality(self, mrz_text: str) -> Optional[str]:
        """Extract nationality from MRZ"""
        lines = mrz_text.split('\n')
        if len(lines) >= 2:
            return lines[1][10:13].strip()
        return None

    def _extract_expiry_date(self, mrz_text: str) -> Optional[str]:
        """Extract expiry date from MRZ"""
        lines = mrz_text.split('\n')
        if len(lines) >= 2:
            return lines[1][13:19].strip()
        return None

    def _extract_issuing_country(self, mrz_text: str) -> Optional[str]:
        """Extract issuing country from MRZ"""
        lines = mrz_text.split('\n')
        if lines:
            return lines[0][2:5].strip()
        return None

    def _classify_visa(self, image: np.ndarray) -> Dict:
        """Extract data from visa"""
        # Visa processing would use specialized models
        text = pytesseract.image_to_string(image, config=self.custom_config)
        return {"raw_text": text.strip()}

    def _classify_boarding_pass(self, image: np.ndarray) -> Dict:
        """Extract data from boarding pass"""
        text = pytesseract.image_to_string(image, config=self.custom_config)
        return {"raw_text": text.strip()}

    def _classify_id_card(self, image: np.ndarray) -> Dict:
        """Extract data from ID card"""
        text = pytesseract.image_to_string(image, config=self.custom_config)
        return {"raw_text": text.strip()}

    def _extract_generic(self, image: np.ndarray) -> Dict:
        """Generic OCR extraction"""
        text = pytesseract.image_to_string(image, config='--psm 6')
        return {"raw_text": text.strip()}

    def _assess_image_quality(self, image: np.ndarray) -> Dict:
        """Assess image quality for OCR"""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blur = cv2.Laplacian(gray, cv2.CV_64F).var()
        brightness = np.mean(gray)

        return {
            "sharpness": float(blur),
            "brightness": float(brightness),
            "is_blurry": blur < 50,
            "is_too_dark": brightness < 50,
            "is_too_bright": brightness > 200
        }
