"""
Comprehensive test suite for offline dossier pipeline:
Schemas, parsers, text cleaner, JSON fallback repair, and all report exporters.
"""

import json
from pathlib import Path
import pytest
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


@pytest.fixture
def sample_dossier() -> DossierReport:
    """Создает образец досье для тестов экспорта."""
    return DossierReport(
        subject=SubjectProfile(
            full_name="Сейфуллин Ерлан Болатович",
            iin="850412300145",
            birth_date="12.04.1985",
            birth_place="г. Алматы",
            citizenship="Республика Казахстан",
            gender="Мужской"
        ),
        contacts=ContactInfo(
            phone_numbers=["+7 (777) 123-45-67", "+7 (701) 987-65-43"],
            emails=["yerlan.seifullin@example.kz"],
            social_profiles=["@yerlan_kz", "telegram: @seifullin85"]
        ),
        addresses=[
            Address(
                address_type="прописка",
                full_address="РК, г. Алматы, Медеуский р-н, пр. Достык, д. 45, кв. 12",
                city="Алматы",
                region="Алматы"
            ),
            Address(
                address_type="фактический",
                full_address="РК, г. Астана, район Есиль, ул. Достык, д. 18, оф. 504",
                city="Астана",
                region="Астана"
            )
        ],
        employment_history=[
            Employment(
                organization="ТОО «Kazakhstan Digital Solutions»",
                bin="180540023412",
                position="Генеральный директор",
                period="2020 — настоящее время",
                notes="Учредитель с долей 51%"
            ),
            Employment(
                organization="АО «Национальный холдинг Инновации»",
                bin="091140011234",
                position="Главный аналитик проектов",
                period="2015 — 2020"
            )
        ],
        relatives_and_affiliates=[
            RelativeRelation(
                full_name="Сейфуллина Алия Маратовна",
                relation_type="супруга",
                iin="870825401290",
                birth_date="25.08.1987",
                shared_attributes=["общий адрес: пр. Достык 45", "общий контактный телефон"],
                notes="Совместное владение недвижимостью"
            ),
            RelativeRelation(
                full_name="Сейфуллин Болат Касымович",
                relation_type="отец",
                iin="580110300021",
                birth_date="10.01.1958",
                shared_attributes=["совместное участие в ТОО"],
                notes="Пенсионер"
            )
        ],
        executive_summary=(
            "Субъект проверки Сейфуллин Е.Б. является действующим руководителем и мажоритарным "
            "учредителем ТОО «Kazakhstan Digital Solutions». Выявлены устойчивые связи с супругой "
            "Сейфуллиной А.М. (общий адрес проживания и средства связи) и отцом Сейфуллиным Б.К. "
            "Факторов высокого риска и стоп-факторов не обнаружено."
        ),
        metadata={"test_run": True, "created_at": "2026-09-15"}
    )


# ---------------------------------------------------------------------------
# Test Schemas
# ---------------------------------------------------------------------------

def test_dossier_schema_validation(sample_dossier):
    json_data = sample_dossier.model_dump()
    assert json_data["subject"]["full_name"] == "Сейфуллин Ерлан Болатович"
    assert len(json_data["relatives_and_affiliates"]) == 2
    assert "общий адрес" in json_data["relatives_and_affiliates"][0]["shared_attributes"][0]

    # JSON Schema generation
    schema = DossierReport.get_json_schema()
    assert "properties" in schema
    assert "subject" in schema["properties"]
    assert "relatives_and_affiliates" in schema["properties"]


# ---------------------------------------------------------------------------
# Test Text Cleaner
# ---------------------------------------------------------------------------

def test_text_cleaner():
    dirty_text = (
        "Страница 1 из 10\n"
        "+-------------------+\n"
        "Сейфуллин   Ерлан    Болатович\n\n\n\n"
        "Повторяющийся длинный фрагмент текста для проверки дедупликации.\n"
        "Повторяющийся длинный фрагмент текста для проверки дедупликации.\n"
        "Страница 2 из 10"
    )
    cleaned = TextCleaner.clean(dirty_text)
    assert "+-------------------+" not in cleaned
    assert "Страница 1 из 10" not in cleaned
    # Check deduplication
    assert cleaned.count("Повторяющийся длинный фрагмент текста для проверки дедупликации.") == 1
    # Check token estimation
    tokens = TextCleaner.estimate_tokens(cleaned)
    assert tokens > 0


# ---------------------------------------------------------------------------
# Test LLM JSON Repair Fallback
# ---------------------------------------------------------------------------

def test_json_repair_fallback():
    client = LLMClient()

    # Broken JSON with trailing commas, markdown fences and unquoted keys
    malformed_llm_output = """
    ```json
    {
      "subject": {
        "full_name": "Иванов Иван Иванович",
        "iin": "900101300000",
      },
      "contacts": {
        "phone_numbers": ["+77001112233",],
      },
      "relatives_and_affiliates": [],
    }
    ```
    """
    repaired_dict = client._parse_and_repair_json(malformed_llm_output)
    assert repaired_dict["subject"]["full_name"] == "Иванов Иван Иванович"
    assert repaired_dict["contacts"]["phone_numbers"] == ["+77001112233"]


# ---------------------------------------------------------------------------
# Test Document Exporters
# ---------------------------------------------------------------------------

def test_exporters(tmp_path, sample_dossier):
    # 1. JSON Export
    json_path = tmp_path / "test_report.json"
    export_json(sample_dossier, json_path)
    assert json_path.exists()
    with open(json_path, "r", encoding="utf-8") as f:
        loaded = json.load(f)
        assert loaded["subject"]["full_name"] == "Сейфуллин Ерлан Болатович"

    # 2. DOCX Export
    docx_path = tmp_path / "test_report.docx"
    export_docx("# Отчет\n\nЭто тестовый отчет.", docx_path)
    assert docx_path.exists()
    assert docx_path.stat().st_size > 5000

    # 3. XLSX Export
    xlsx_path = tmp_path / "test_report.xlsx"
    export_xlsx(sample_dossier, xlsx_path)
    assert xlsx_path.exists()
    assert xlsx_path.stat().st_size > 5000

    # 4. PDF Export
    pdf_path = tmp_path / "test_report.pdf"
    export_pdf(sample_dossier, pdf_path)
    assert pdf_path.exists()
    assert pdf_path.stat().st_size > 1000


# ---------------------------------------------------------------------------
# Test Parsers
# ---------------------------------------------------------------------------

def test_html_parser(tmp_path):
    html_content = """
    <html>
      <head><style>body { color: red; }</style></head>
      <body>
        <script>console.log('noise');</script>
        <h1>Досье кандидата</h1>
        <p>ФИО: Асанов Арман Серикович</p>
        <table>
          <tr><th>Организация</th><th>Должность</th></tr>
          <tr><td>ТОО Самал</td><td>Директор</td></tr>
        </table>
      </body>
    </html>
    """
    html_file = tmp_path / "test.html"
    html_file.write_text(html_content, encoding="utf-8")

    parser = HTMLParser()
    doc = parser.parse(html_file)
    assert "console.log" not in doc.full_text
    assert "Асанов Арман Серикович" in doc.full_text
    assert "ТОО Самал" in doc.full_text


def test_json_parser(tmp_path):
    data = {
        "status": 200,
        "person": {
            "name": "Нурланов Данияр",
            "phones": ["+77051234567"]
        }
    }
    json_file = tmp_path / "test_data.json"
    json_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    parser = JSONParser()
    doc = parser.parse(json_file)
    assert "Нурланов Данияр" in doc.full_text
    assert "status" not in doc.full_text  # Filtered metadata noise


def test_parser_registry_routing(tmp_path):
    txt_file = tmp_path / "notes.txt"
    txt_file.write_text("Заметки по проверке лица", encoding="utf-8")
    parser = get_parser_for_file(txt_file)
    assert isinstance(parser, PlainTextParser)


# ---------------------------------------------------------------------------
# Test split_into_chunks
# ---------------------------------------------------------------------------

def test_split_into_chunks_small_text():
    """Text smaller than chunk limit should return single chunk."""
    result = TextCleaner.split_into_chunks("Short text.", max_chunk_tokens=1000)
    assert len(result) == 1
    assert result[0] == "Short text."


def test_split_into_chunks_large_text():
    """Long text should be split into multiple chunks."""
    # ~10000 chars → at 3.2 chars/token ≈ 3125 tokens
    long_text = ("Предложение для тестирования чанкинга. " * 250).strip()
    result = TextCleaner.split_into_chunks(long_text, max_chunk_tokens=500, overlap_tokens=50)
    assert len(result) > 1
    # Every chunk should have content
    for chunk in result:
        assert len(chunk.strip()) > 0


def test_split_into_chunks_no_infinite_loop():
    """Ensure split doesn't hang with edge-case overlap >= chunk size."""
    text = "a " * 5000
    result = TextCleaner.split_into_chunks(text, max_chunk_tokens=100, overlap_tokens=200)
    assert len(result) > 1  # Just ensure it terminates


# ---------------------------------------------------------------------------
# Test _balance_brackets
# ---------------------------------------------------------------------------

def test_balance_brackets_unclosed():
    client = LLMClient()
    broken = '{"name": "test", "items": [1, 2, 3'
    balanced = client._balance_brackets(broken)
    assert balanced.endswith("]}")
    parsed = json.loads(balanced)
    assert parsed["name"] == "test"


def test_balance_brackets_already_valid():
    client = LLMClient()
    valid = '{"key": "value"}'
    assert client._balance_brackets(valid) == valid


# ---------------------------------------------------------------------------
# Test edge cases
# ---------------------------------------------------------------------------

def test_cleaner_empty_input():
    assert TextCleaner.clean("") == ""
    assert TextCleaner.clean("   ") == ""
    assert TextCleaner.estimate_tokens("") == 0


def test_dossier_merge(sample_dossier):
    """Test _merge_partial_dossier deduplication logic."""
    from app.pipeline import DossierPipeline

    partial = DossierReport(
        subject=SubjectProfile(full_name="Partial Subject"),
        contacts=ContactInfo(phone_numbers=["+77051112233", "+7 (777) 123-45-67"]),  # one duplicate
        addresses=[
            Address(
                address_type="фактический",
                full_address="РК, г. Алматы, Медеуский р-н, пр. Достык, д. 45, кв. 12"  # duplicate
            ),
            Address(
                address_type="прежний",
                full_address="г. Караганда, ул. Ленина 10"  # new
            )
        ],
        employment_history=[
            Employment(organization="АО «Национальный холдинг Инновации»"),  # duplicate
            Employment(organization="ИП «СтартАп»"),  # new
        ],
        relatives_and_affiliates=[
            RelativeRelation(full_name="Сейфуллин Болат Касымович", relation_type="отец"),  # duplicate
            RelativeRelation(full_name="Сейфуллин Тимур Ерланович", relation_type="сын"),  # new
        ],
        executive_summary="Partial summary"
    )

    original_rel_count = len(sample_dossier.relatives_and_affiliates)
    original_emp_count = len(sample_dossier.employment_history)

    DossierPipeline._merge_partial_dossier(sample_dossier, partial)

    # Should add 1 new relative, not the duplicate
    assert len(sample_dossier.relatives_and_affiliates) == original_rel_count + 1
    # Should add 1 new employment, not the duplicate
    assert len(sample_dossier.employment_history) == original_emp_count + 1
    # Should add 1 new address
    assert len(sample_dossier.addresses) == 3
    # Should add 1 new phone (not the duplicate)
    assert "+77051112233" in sample_dossier.contacts.phone_numbers
