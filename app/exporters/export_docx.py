"""
DOCX Exporter for DossierReport.
Uses the advanced DossierDocxBuilder to generate highly stylized Word documents
from Forensic Markdown reports.
"""

from pathlib import Path
from typing import Union
from app.exporters.docx_builder import DossierDocxBuilder

def export_docx(markdown_text: str, output_path: Union[str, Path]) -> Path:
    """
    Генерирует структурированный аналитический отчет Word (.docx) из Markdown текста.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    builder = DossierDocxBuilder()
    if not markdown_text or not markdown_text.strip():
        markdown_text = "# Ошибка\n\nОтчет пуст или не был сгенерирован."
        
    builder.parse_markdown(markdown_text)
    builder.save(str(path))
    
    return path
