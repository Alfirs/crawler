from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict

import cv2
import numpy as np
import pytesseract


@dataclass(slots=True)
class ImageParser:
    """Simple OCR-based parser for invoices, receipts, and stamps."""

    lang: str = "rus+eng"

    def preprocess(self, image_path: str | Path) -> "np.ndarray":
        """Convert to grayscale and apply adaptive thresholding."""
        image = cv2.imread(str(image_path))
        if image is None:
            raise FileNotFoundError(f"Image not found: {image_path}")
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        thresh = cv2.adaptiveThreshold(
            blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
        )
        return thresh

    def extract_text(self, image_path: str | Path) -> str:
        prepared = self.preprocess(image_path)
        text = pytesseract.image_to_string(prepared, lang=self.lang)
        return text

    def parse_invoice(self, image_path: str | Path) -> Dict[str, str]:
        """Very naive invoice parsing routine."""
        text = self.extract_text(image_path)
        payload: Dict[str, str] = {}
        for line in text.splitlines():
            if "ИНН" in line.upper():
                payload["inn"] = line.split()[-1]
            elif "КПП" in line.upper():
                payload["kpp"] = line.split()[-1]
            elif "СУМ" in line.upper():
                payload["amount"] = line.split()[-1]
        payload["raw_text"] = text
        return payload
