"""
Base parser interface and data structures for document ingestion.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class PageContent:
    """Содержимое отдельной страницы или листа документа."""
    page_number: int
    text: str
    is_ocr: bool = False
    confidence: Optional[float] = None
    tables: List[str] = field(default_factory=list)


@dataclass
class ParsedDocument:
    """Результат разбора документа произвольного типа."""
    file_path: Path
    file_name: str
    mime_type: str
    source_type: str
    pages: List[PageContent] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def full_text(self) -> str:
        """Объединенный текст всех страниц документа в Markdown формате."""
        return "\n\n".join(
            f"--- [Страница {p.page_number}{' (OCR)' if p.is_ocr else ''}] ---\n{p.text}"
            for p in self.pages
            if p.text.strip()
        )

    @property
    def total_pages(self) -> int:
        return len(self.pages)


class BaseParser(ABC):
    """Абстрактный интерфейс для парсеров документов."""

    @abstractmethod
    def supports(self, file_path: Path, mime_type: str) -> bool:
        """Проверяет, поддерживается ли данный файл парсером."""
        pass

    @abstractmethod
    def parse(self, file_path: Path) -> ParsedDocument:
        """Выполняет разбор документа и возвращает ParsedDocument."""
        pass
