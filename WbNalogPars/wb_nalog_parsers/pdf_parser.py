from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List

import pdfplumber


class PDFParser:
    """Parse PDF invoices/acts into structured text sections."""

    def extract_text(self, pdf_path: str | Path) -> List[str]:
        sections: List[str] = []
        with pdfplumber.open(str(pdf_path)) as pdf:
            for page in pdf.pages:
                sections.append(page.extract_text() or "")
        return sections

    def extract_tables(self, pdf_path: str | Path) -> Iterable[List[List[str]]]:
        with pdfplumber.open(str(pdf_path)) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                if not tables:
                    continue
                for table in tables:
                    yield table

    def parse_invoice(self, pdf_path: str | Path) -> Dict[str, str]:
        """Very light heuristic mapping of invoice fields."""
        sections = self.extract_text(pdf_path)
        payload: Dict[str, str] = {}
        for section in sections:
            for line in section.splitlines():
                if "ИНН" in line.upper() and "inn" not in payload:
                    payload["inn"] = line.split()[-1]
                elif "КПП" in line.upper() and "kpp" not in payload:
                    payload["kpp"] = line.split()[-1]
                elif "ДОГОВОР" in line.upper():
                    payload.setdefault("contract", line)
        payload["raw_text"] = "\n".join(sections)
        return payload
