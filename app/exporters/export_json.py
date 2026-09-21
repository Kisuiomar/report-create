"""
JSON Exporter for DossierReport.
Saves validated Pydantic model into a clean UTF-8 JSON file.
"""

from pathlib import Path
from typing import Union

from app.core.schemas import DossierReport


def export_json(dossier: DossierReport, output_path: Union[str, Path]) -> Path:
    """
    Экспортирует досье в файл JSON с поддержкой Unicode (кириллица, спецсимволы).
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    json_str = dossier.model_dump_json(indent=2, by_alias=False)
    with open(path, "w", encoding="utf-8") as f:
        f.write(json_str)

    return path
