"""
Text document parsers for PDF, DOCX, XLSX, HTML, JSON, and plain text files.
Includes intelligent PDF digital vs. scanned page discrimination.
"""

import io
import json
import logging
import mimetypes
from pathlib import Path
from typing import List, Optional

from app.config import settings
from app.parsers.base import BaseParser, PageContent, ParsedDocument
from app.parsers.ocr_parser import OCRParser

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# PDF Parser with Smart Native vs. OCR detection
# ---------------------------------------------------------------------------

class PDFParser(BaseParser):
    """
    Парсер PDF документов.
    Разделяет цифровые страницы с нативным текстовым слоем и сканированные страницы.
    Применяет OCR исключительно к страницам без распознанного текста.
    """

    SUPPORTED_EXTENSIONS = {".pdf"}

    def __init__(self, ocr_parser: Optional[OCRParser] = None):
        self.ocr_parser = ocr_parser or OCRParser()

    def supports(self, file_path: Path, mime_type: str) -> bool:
        return file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS or mime_type == "application/pdf"

    def parse(self, file_path: Path) -> ParsedDocument:
        # 1. Попытка использования PyMuPDF (fitz) - быстрый и точный
        try:
            import fitz  # PyMuPDF
            return self._parse_with_fitz(file_path)
        except ImportError:
            logger.debug("PyMuPDF (fitz) is not installed. Trying pypdf...")

        # 2. Попытка использования pypdf
        try:
            import pypdf
            return self._parse_with_pypdf(file_path)
        except ImportError:
            logger.debug("pypdf is not installed. Trying pdfplumber...")

        # 3. Попытка использования pdfplumber
        try:
            import pdfplumber
            return self._parse_with_pdfplumber(file_path)
        except ImportError:
            raise RuntimeError(
                "No PDF parser library found. Install PyMuPDF (`pip install PyMuPDF`) or pypdf (`pip install pypdf`)."
            )

    def _parse_with_fitz(self, file_path: Path) -> ParsedDocument:
        import fitz
        doc = fitz.open(str(file_path))
        pages: List[PageContent] = []

        try:
            for page_idx in range(len(doc)):
                page = doc[page_idx]
                text = page.get_text("text").strip()
                page_num = page_idx + 1

                # Если текста достаточно - используем нативный цифровой слой
                if len(text) >= settings.PDF_OCR_THRESHOLD_CHARS:
                    pages.append(PageContent(page_number=page_num, text=text, is_ocr=False))
                else:
                    # Страница похожа на скан - извлекаем растровое изображение для OCR
                    logger.info("PDF page %d contains low/no text (%d chars). Running OCR...", page_num, len(text))
                    pix = page.get_pixmap(dpi=150)
                    img_bytes = pix.tobytes("png")
                    ocr_text, conf = self.ocr_parser.recognize_image(img_bytes)
                    combined_text = (text + "\n" + ocr_text).strip() if text else ocr_text
                    pages.append(PageContent(page_number=page_num, text=combined_text, is_ocr=True, confidence=conf))
        finally:
            doc.close()

        return ParsedDocument(
            file_path=file_path,
            file_name=file_path.name,
            mime_type="application/pdf",
            source_type="pdf_fitz",
            pages=pages,
            metadata={"total_pages": len(pages), "engine": "PyMuPDF"}
        )

    def _parse_with_pypdf(self, file_path: Path) -> ParsedDocument:
        from pypdf import PdfReader
        reader = PdfReader(str(file_path))
        pages: List[PageContent] = []

        for page_idx, page in enumerate(reader.pages):
            text = (page.extract_text() or "").strip()
            page_num = page_idx + 1

            if len(text) >= settings.PDF_OCR_THRESHOLD_CHARS or not page.images:
                pages.append(PageContent(page_number=page_num, text=text, is_ocr=False))
            else:
                # Извлечение встроенных картинок для OCR
                ocr_chunks = []
                for img_obj in page.images:
                    ocr_res, conf = self.ocr_parser.recognize_image(img_obj.data)
                    if ocr_res:
                        ocr_chunks.append(ocr_res)
                ocr_full = "\n".join(ocr_chunks)
                final_text = (text + "\n" + ocr_full).strip() if text else ocr_full
                pages.append(PageContent(page_number=page_num, text=final_text, is_ocr=True))

        return ParsedDocument(
            file_path=file_path,
            file_name=file_path.name,
            mime_type="application/pdf",
            source_type="pdf_pypdf",
            pages=pages,
            metadata={"total_pages": len(pages), "engine": "pypdf"}
        )

    def _parse_with_pdfplumber(self, file_path: Path) -> ParsedDocument:
        import pdfplumber
        pages: List[PageContent] = []
        with pdfplumber.open(str(file_path)) as pdf:
            for idx, page in enumerate(pdf.pages):
                text = (page.extract_text() or "").strip()
                page_num = idx + 1
                pages.append(PageContent(page_number=page_num, text=text, is_ocr=False))

        return ParsedDocument(
            file_path=file_path,
            file_name=file_path.name,
            mime_type="application/pdf",
            source_type="pdf_pdfplumber",
            pages=pages,
            metadata={"total_pages": len(pages), "engine": "pdfplumber"}
        )


# ---------------------------------------------------------------------------
# DOCX Parser with Table-to-Markdown formatting
# ---------------------------------------------------------------------------

class DOCXParser(BaseParser):
    """Парсер документов Microsoft Word (.docx). Извлекает структуру и таблицы."""

    SUPPORTED_EXTENSIONS = {".docx"}

    def supports(self, file_path: Path, mime_type: str) -> bool:
        return (
            file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS or
            "wordprocessingml" in mime_type
        )

    def parse(self, file_path: Path) -> ParsedDocument:
        import docx

        doc = docx.Document(str(file_path))
        lines: List[str] = []

        # Извлечение параграфов
        for p in doc.paragraphs:
            text = p.text.strip()
            if not text:
                continue
            # Форматирование заголовков по стилю
            style_name = p.style.name.lower() if p.style else ""
            if "heading 1" in style_name:
                lines.append(f"\n# {text}\n")
            elif "heading 2" in style_name:
                lines.append(f"\n## {text}\n")
            elif "heading 3" in style_name:
                lines.append(f"\n### {text}\n")
            else:
                lines.append(text)

        # Извлечение таблиц в формате Markdown
        for t_idx, table in enumerate(doc.tables):
            table_md = self._convert_table_to_markdown(table)
            if table_md:
                lines.append(f"\n[Таблица #{t_idx + 1}]\n" + table_md + "\n")

        full_content = "\n".join(lines)
        page = PageContent(page_number=1, text=full_content)

        return ParsedDocument(
            file_path=file_path,
            file_name=file_path.name,
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            source_type="docx",
            pages=[page],
            metadata={"paragraphs_count": len(doc.paragraphs), "tables_count": len(doc.tables)}
        )

    @staticmethod
    def _convert_table_to_markdown(table) -> str:
        """Преобразует таблицу docx в Markdown таблицу."""
        rows_data = []
        for row in table.rows:
            row_cells = [cell.text.replace("\n", " ").strip() for cell in row.cells]
            # Устраняем дублирование ячеек при объединении (merged cells)
            dedup_cells = []
            last_cell = None
            for cell in row_cells:
                if cell != last_cell or cell != "":
                    dedup_cells.append(cell)
                last_cell = cell
            if any(dedup_cells):
                rows_data.append(dedup_cells)

        if not rows_data:
            return ""

        # Выравниваем количество колонок
        max_cols = max(len(r) for r in rows_data)
        normalized_rows = [r + [""] * (max_cols - len(r)) for r in rows_data]

        headers = normalized_rows[0]
        md_lines = [
            "| " + " | ".join(headers) + " |",
            "| " + " | ".join(["---"] * max_cols) + " |"
        ]
        for data_row in normalized_rows[1:]:
            md_lines.append("| " + " | ".join(data_row) + " |")

        return "\n".join(md_lines)


# ---------------------------------------------------------------------------
# XLSX Parser: Sheets to Compact Markdown Tables
# ---------------------------------------------------------------------------

class XLSXParser(BaseParser):
    """Парсер таблиц Excel (.xlsx). Конвертирует листы в компактный Markdown."""

    SUPPORTED_EXTENSIONS = {".xlsx", ".xlsm"}

    def supports(self, file_path: Path, mime_type: str) -> bool:
        return (
            file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS or
            "spreadsheetml" in mime_type
        )

    def parse(self, file_path: Path) -> ParsedDocument:
        import openpyxl

        wb = openpyxl.load_workbook(str(file_path), data_only=True, read_only=True)
        pages: List[PageContent] = []

        for sheet_idx, sheet_name in enumerate(wb.sheetnames):
            ws = wb[sheet_name]
            rows_data: List[List[str]] = []

            for row in ws.iter_rows(values_only=True):
                # Пропускаем полностью пустые строки
                if not any(row):
                    continue
                row_str = [str(cell).strip() if cell is not None else "" for cell in row]
                # Отсекаем хвост из пустых ячеек
                while row_str and row_str[-1] == "":
                    row_str.pop()
                if row_str:
                    rows_data.append(row_str)

            if not rows_data:
                continue

            max_cols = max(len(r) for r in rows_data)
            normalized_rows = [r + [""] * (max_cols - len(r)) for r in rows_data]

            md_lines = [f"### Лист: {sheet_name}\n"]
            if len(normalized_rows) > 0:
                headers = normalized_rows[0]
                md_lines.append("| " + " | ".join(headers) + " |")
                md_lines.append("| " + " | ".join(["---"] * max_cols) + " |")
                for data_row in normalized_rows[1:]:
                    md_lines.append("| " + " | ".join(data_row) + " |")

            sheet_text = "\n".join(md_lines)
            pages.append(PageContent(page_number=sheet_idx + 1, text=sheet_text))

        sheet_names = list(wb.sheetnames)  # Save before close
        wb.close()

        return ParsedDocument(
            file_path=file_path,
            file_name=file_path.name,
            mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            source_type="xlsx",
            pages=pages,
            metadata={"sheets": sheet_names}
        )


# ---------------------------------------------------------------------------
# HTML Parser with metadata & script pruning
# ---------------------------------------------------------------------------

class HTMLParser(BaseParser):
    """Парсер HTML-документов. Удаляет CSS, JS, скрипты и баннеры."""

    SUPPORTED_EXTENSIONS = {".html", ".htm", ".xhtml"}

    def supports(self, file_path: Path, mime_type: str) -> bool:
        return file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS or mime_type == "text/html"

    def parse(self, file_path: Path) -> ParsedDocument:
        from bs4 import BeautifulSoup

        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            html_content = f.read()

        soup = BeautifulSoup(html_content, "html.parser")

        # Удаление шума: скриптов, стилей, навигации, шапок и подвалов
        for tag in soup(["script", "style", "nav", "header", "footer", "noscript", "svg", "iframe"]):
            tag.decompose()

        # Преобразование таблиц в markdown
        for table in soup.find_all("table"):
            table_md = self._convert_soup_table(table)
            table.replace_with(f"\n\n{table_md}\n\n")

        # Преобразование заголовков
        for level in range(1, 7):
            for h in soup.find_all(f"h{level}"):
                h.replace_with(f"\n{'#' * level} {h.get_text().strip()}\n")

        # Извлечение чистого текста
        text = soup.get_text(separator="\n")
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        cleaned_text = "\n".join(lines)

        page = PageContent(page_number=1, text=cleaned_text)
        return ParsedDocument(
            file_path=file_path,
            file_name=file_path.name,
            mime_type="text/html",
            source_type="html",
            pages=[page],
            metadata={"title": soup.title.string if soup.title else None}
        )

    @staticmethod
    def _convert_soup_table(table) -> str:
        rows = []
        for tr in table.find_all("tr"):
            cells = [th_td.get_text().strip() for th_td in tr.find_all(["th", "td"])]
            if any(cells):
                rows.append(cells)
        if not rows:
            return ""
        max_cols = max(len(r) for r in rows)
        norm_rows = [r + [""] * (max_cols - len(r)) for r in rows]
        res = ["| " + " | ".join(norm_rows[0]) + " |", "| " + " | ".join(["---"] * max_cols) + " |"]
        for row in norm_rows[1:]:
            res.append("| " + " | ".join(row) + " |")
        return "\n".join(res)


# ---------------------------------------------------------------------------
# JSON and Plain Text Parsers
# ---------------------------------------------------------------------------

class JSONParser(BaseParser):
    """Парсер JSON файлов: очистка от технических оберток и форматирование."""

    SUPPORTED_EXTENSIONS = {".json"}

    def supports(self, file_path: Path, mime_type: str) -> bool:
        return file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS or mime_type == "application/json"

    def parse(self, file_path: Path) -> ParsedDocument:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            data = json.load(f)

        formatted_text = self._format_json_data(data)
        page = PageContent(page_number=1, text=formatted_text)

        return ParsedDocument(
            file_path=file_path,
            file_name=file_path.name,
            mime_type="application/json",
            source_type="json",
            pages=[page],
            metadata={"keys_count": len(data) if isinstance(data, dict) else len(data) if isinstance(data, list) else 1}
        )

    def _format_json_data(self, data, indent: int = 0) -> str:
        """Форматирует JSON дерево в читаемый и экономный текст."""
        lines = []
        prefix = "  " * indent
        if isinstance(data, dict):
            for k, v in data.items():
                if k.lower() in ("status", "code", "debug", "trace_id", "csrf_token"):
                    continue  # Пропускаем технический шум
                if isinstance(v, (dict, list)):
                    lines.append(f"{prefix}- **{k}**:")
                    lines.append(self._format_json_data(v, indent + 1))
                else:
                    lines.append(f"{prefix}- **{k}**: {v}")
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, (dict, list)):
                    lines.append(self._format_json_data(item, indent + 1))
                else:
                    lines.append(f"{prefix}* {item}")
        else:
            lines.append(f"{prefix}{data}")
        return "\n".join(lines)


class PlainTextParser(BaseParser):
    """Парсер плоского текста: TXT, CSV, TSV, Markdown, LOG."""

    SUPPORTED_EXTENSIONS = {".txt", ".csv", ".tsv", ".md", ".log", ".text"}

    def supports(self, file_path: Path, mime_type: str) -> bool:
        return file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS or mime_type.startswith("text/")

    def parse(self, file_path: Path) -> ParsedDocument:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        page = PageContent(page_number=1, text=content)
        return ParsedDocument(
            file_path=file_path,
            file_name=file_path.name,
            mime_type="text/plain",
            source_type="text",
            pages=[page],
            metadata={"char_count": len(content)}
        )


# ---------------------------------------------------------------------------
# Registry for Automatic Document Type Routing
# ---------------------------------------------------------------------------

class ParserRegistry:
    """Реестр всех парсеров с автоматическим определением формата документа."""

    def __init__(self):
        self.ocr_parser = OCRParser()
        self.parsers: List[BaseParser] = [
            PDFParser(ocr_parser=self.ocr_parser),
            DOCXParser(),
            XLSXParser(),
            HTMLParser(),
            JSONParser(),
            PlainTextParser(),
            self.ocr_parser,  # Для картинок и сканов
        ]

    def get_parser(self, file_path: Path) -> BaseParser:
        """Определяет подходящий парсер на основе расширения и MIME-типа."""
        mime_type, _ = mimetypes.guess_type(str(file_path))
        mime_type = mime_type or "application/octet-stream"

        for parser in self.parsers:
            if parser.supports(file_path, mime_type):
                return parser

        # Fallback на PlainTextParser
        logger.warning("No specialized parser found for '%s' (mime: %s). Using PlainText fallback.", file_path.name, mime_type)
        return PlainTextParser()


_global_registry = ParserRegistry()


def get_parser_for_file(file_path: Path) -> BaseParser:
    """Глобальный фасад для получения парсера под файл."""
    return _global_registry.get_parser(file_path)
