"""
Parsers package for extracting textual representations from various document formats.
"""

from app.parsers.base import BaseParser, ParsedDocument, PageContent
from app.parsers.text_parsers import ParserRegistry, get_parser_for_file
from app.parsers.ocr_parser import OCRParser

__all__ = ["BaseParser", "ParsedDocument", "PageContent", "ParserRegistry", "get_parser_for_file", "OCRParser"]
