"""
Self-contained system verification runner.
Tests schemas, exporters, parsers, and outputs sample files for manual inspection.
"""

import os
import sys
from pathlib import Path

# Ensure UTF-8 console output
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Ensure root in path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.core.schemas import (
    Address,
    ContactInfo,
    DossierReport,
    Employment,
    RelativeRelation,
    SubjectProfile,
)
from app.core.cleaner import TextCleaner
from app.core.llm_client import LLMClient
from app.exporters import export_docx, export_json, export_pdf, export_xlsx
from app.parsers.text_parsers import (
    DOCXParser,
    HTMLParser,
    JSONParser,
    PlainTextParser,
    XLSXParser,
    get_parser_for_file,
)


def run_checks():
    print("=" * 60)
    print("RUNNING SYSTEM VERIFICATION CHECKS")
    print("=" * 60)

    # 1. Pydantic Schemas Check
    print("[1/5] Checking Pydantic schemas...")
    dossier = DossierReport(
        subject=SubjectProfile(
            full_name="Сейфуллин Ерлан Болатович",
            iin="850412300145",
            birth_date="12.04.1985",
            birth_place="г. Алматы",
            citizenship="Республика Казахстан"
        ),
        contacts=ContactInfo(
            phone_numbers=["+7 (777) 123-45-67"],
            emails=["yerlan@example.kz"]
        ),
        addresses=[
            Address(
                address_type="прописка",
                full_address="г. Алматы, пр. Достык, д. 45, кв. 12",
                city="Алматы"
            )
        ],
        employment_history=[
            Employment(
                organization="ТОО «Kazakhstan Digital Solutions»",
                bin="180540023412",
                position="Генеральный директор",
                period="2020 — н.в."
            )
        ],
        relatives_and_affiliates=[
            RelativeRelation(
                full_name="Сейфуллина Алия Маратовна",
                relation_type="супруга",
                iin="870825401290",
                shared_attributes=["общий адрес: пр. Достык 45"],
                notes="Совместное владение недвижимостью"
            )
        ],
        executive_summary="Тестовое аналитическое заключение. Факторы высокого риска отсутствуют."
    )
    assert dossier.subject.full_name == "Сейфуллин Ерлан Болатович"
    schema = DossierReport.get_json_schema()
    assert "properties" in schema
    print("  ✓ Pydantic schemas validated and JSON Schema generated successfully.")

    # 2. Text Cleaner Check
    print("[2/5] Checking TextCleaner...")
    raw = "Страница 1 из 5\n\n+----+\n\nСейфуллин Ерлан Болатович\n\nСтраница 2 из 5"
    cleaned = TextCleaner.clean(raw)
    assert "+----+" not in cleaned
    assert "Страница 1" not in cleaned
    print("  ✓ Text cleaner successfully stripped artifacts and normalized tokens.")

    # 3. LLM JSON Repair Check
    print("[3/5] Checking LLM JSON fallback repair...")
    client = LLMClient()
    malformed = """
    ```json
    {
      "subject": {
        "full_name": "Тестовый Субъект",
        "iin": "990101300000",
      },
      "contacts": {
        "phone_numbers": ["+77770001122",],
      },
    }
    ```
    """
    repaired = client._parse_and_repair_json(malformed)
    assert repaired["subject"]["full_name"] == "Тестовый Субъект"
    print("  ✓ JSON regex-repair successfully recovered valid dictionary from broken payload.")

    # 4. Report Exporters Check
    print("[4/5] Checking Report Exporters (PDF, DOCX, XLSX, JSON)...")
    out_dir = Path("./data/test_output")
    out_dir.mkdir(parents=True, exist_ok=True)

    json_f = export_json(dossier, out_dir / "test_dossier.json")
    print(f"  ✓ JSON export: {json_f.name} ({json_f.stat().st_size} bytes)")

    docx_f = export_docx("# Тестовый отчет\n\nТест генерации.", out_dir / "test_dossier.docx")
    print(f"  ✓ DOCX export: {docx_f.name} ({docx_f.stat().st_size} bytes)")

    xlsx_f = export_xlsx(dossier, out_dir / "test_dossier.xlsx")
    print(f"  ✓ XLSX export: {xlsx_f.name} ({xlsx_f.stat().st_size} bytes)")

    pdf_f = export_pdf(dossier, out_dir / "test_dossier.pdf")
    print(f"  ✓ PDF export: {pdf_f.name} ({pdf_f.stat().st_size} bytes)")

    # 5. CLI & FastAPI imports check
    print("[5/5] Checking FastAPI and CLI initialization...")
    import main
    assert main.app is not None
    assert main.cli is not None
    print("  ✓ FastAPI and Typer CLI loaded without errors.")

    print("=" * 60)
    print("ALL VERIFICATION CHECKS PASSED PERFECTLY!")
    print("=" * 60)


if __name__ == "__main__":
    run_checks()
