"""
Integration test for DossierPipeline with mocked LLM response.
Verifies parsing of real documents, text aggregation, and exporter output.
"""

from pathlib import Path
from unittest.mock import MagicMock
from app.core.schemas import (
    Address,
    ContactInfo,
    DossierReport,
    Employment,
    RelativeRelation,
    SubjectProfile,
)
from app.pipeline import DossierPipeline


def test_full_pipeline(tmp_path):
    # Create sample documents: a TXT notes file and an HTML profile
    txt_file = tmp_path / "candidate_notes.txt"
    txt_file.write_text(
        "Проверка кандидата: Кусаинов Даулет Айдарович, ИИН 820615300981. Проживает в Астане, ул. Сарайшык 5.",
        encoding="utf-8"
    )

    html_file = tmp_path / "resume.html"
    html_file.write_text(
        "<html><body><h1>Резюме</h1><p>Место работы: АО КазТрансГаз, начальник отдела.</p></body></html>",
        encoding="utf-8"
    )

    # Mock LLM Client
    mock_llm = MagicMock()
    mock_llm.model = "qwen2.5:14b"
    mock_llm.provider = "ollama"
    mock_llm.generate_dossier.return_value = DossierReport(
        subject=SubjectProfile(
            full_name="Кусаинов Даулет Айдарович",
            iin="820615300981",
            birth_date="15.06.1982",
            citizenship="Республика Казахстан"
        ),
        contacts=ContactInfo(phone_numbers=["+77015554433"]),
        addresses=[
            Address(address_type="фактический", full_address="г. Астана, ул. Сарайшык, д. 5", city="Астана")
        ],
        employment_history=[
            Employment(organization="АО КазТрансГаз", position="Начальник отдела", period="2018 — н.в.")
        ],
        relatives_and_affiliates=[
            RelativeRelation(
                full_name="Кусаинова Динара Сериковна",
                relation_type="супруга",
                iin="840920400122",
                shared_attributes=["общий адрес: ул. Сарайшык 5"]
            )
        ],
        executive_summary="Субъект проверки успешно идентифицирован. Выявлены родственные связи с супругой."
    )

    out_dir = tmp_path / "reports_output"
    pipeline = DossierPipeline(llm_client=mock_llm, output_dir=out_dir)

    result = pipeline.process_files(
        [txt_file, html_file],
        export_formats=["json", "docx", "xlsx", "pdf"]
    )

    assert result.dossier.subject.full_name == "Кусаинов Даулет Айдарович"
    assert "Кусаинов Даулет Айдарович" in result.raw_cleaned_text
    assert "АО КазТрансГаз" in result.raw_cleaned_text
    assert len(result.generated_files) == 4
    for fmt, file_path in result.generated_files.items():
        assert file_path.exists()
        assert file_path.stat().st_size > 0
