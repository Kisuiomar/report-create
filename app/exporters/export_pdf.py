"""
PDF Exporter for DossierReport.
Renders an analytical report with structured tables, executive summary,
and Unicode font support for Russian, Kazakh, and English texts.
"""

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Union

from app.core.schemas import DossierReport

logger = logging.getLogger(__name__)


def _register_unicode_font() -> str:
    """Регистрирует системный или встроенный TTF-шрифт с полной поддержкой кириллицы и казахских букв."""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    # Font pairs: (regular_name, regular_path, bold_name, bold_path)
    font_families = [
        # Windows system fonts with comprehensive Unicode support
        ("CustomArial", r"C:\Windows\Fonts\arial.ttf", "CustomArialBold", r"C:\Windows\Fonts\arialbd.ttf"),
        ("CustomTahoma", r"C:\Windows\Fonts\tahoma.ttf", "CustomTahomaBold", r"C:\Windows\Fonts\tahomabd.ttf"),
        ("CustomCalibri", r"C:\Windows\Fonts\calibri.ttf", "CustomCalibriBold", r"C:\Windows\Fonts\calibrib.ttf"),
        # Linux standard paths
        ("CustomDejaVu", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
         "CustomDejaVuBold", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ]

    registered_font_name = "Helvetica"  # Default fallback
    for name, font_path, bold_name, bold_path in font_families:
        if os.path.exists(font_path):
            try:
                pdfmetrics.registerFont(TTFont(name, font_path))
                registered_font_name = name
                logger.debug("Successfully registered font '%s' from %s", name, font_path)

                # Register bold variant if available
                if os.path.exists(bold_path):
                    pdfmetrics.registerFont(TTFont(bold_name, bold_path))
                    from reportlab.pdfbase.pdfmetrics import registerFontFamily
                    registerFontFamily(name, normal=name, bold=bold_name)
                    logger.debug("Registered bold variant '%s' from %s", bold_name, bold_path)
                break
            except Exception as exc:
                logger.warning("Could not register font %s: %s", font_path, exc)

    return registered_font_name


class NumberedCanvas:
    """Кастомный канвас для нумерации страниц формата 'Стр. X из Y' и верхнего колонтитула."""
    def __init__(self, *args, **kwargs):
        from reportlab.pdfgen import canvas
        self._canvas_class = canvas.Canvas

    @classmethod
    def create_canvas_factory(cls, title: str, font_name: str):
        from reportlab.pdfgen import canvas

        class PageNumCanvas(canvas.Canvas):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.pages = []

            def showPage(self):
                self.pages.append(dict(self.__dict__))
                self._startPage()

            def save(self):
                num_pages = len(self.pages)
                for page in self.pages:
                    self.__dict__.update(page)
                    self.draw_page_decorations(num_pages)
                    super().showPage()
                super().save()

            def draw_page_decorations(self, total_pages: int):
                self.saveState()
                self.setFont(font_name, 8)
                self.setFillColorRGB(0.4, 0.45, 0.5)

                # Нижний колонтитул
                page_str = f"Страница {self._pageNumber} из {total_pages}"
                self.drawRightString(550, 30, page_str)
                self.drawString(45, 30, "Конфиденциально • Сформировано автономной системой анализа досье")

                # Тонкая разделительная линия внизу
                self.setStrokeColorRGB(0.88, 0.9, 0.94)
                self.setLineWidth(0.5)
                self.line(45, 42, 550, 42)

                self.restoreState()

        return PageNumCanvas


def export_pdf(dossier: DossierReport, output_path: Union[str, Path]) -> Path:
    """
    Формирует элегантный PDF-документ досье с табличной версткой.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError:
        logger.warning("ReportLab is not installed. Trying fpdf2 fallback...")
        return _export_pdf_fpdf_fallback(dossier, path)

    font_name = _register_unicode_font()

    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=40,
        rightMargin=40,
        topMargin=40,
        bottomMargin=50
    )

    styles = getSampleStyleSheet()

    # Стили текста
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#0F172A"),
        fontBold=True
    )
    meta_style = ParagraphStyle(
        "DocMeta",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#64748B")
    )
    h1_style = ParagraphStyle(
        "SectionH1",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#1E3A8A"),
        fontBold=True,
        spaceBefore=10,
        spaceAfter=4
    )
    body_style = ParagraphStyle(
        "TableBody",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#1E293B")
    )
    body_bold_style = ParagraphStyle(
        "TableBodyBold",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#0F172A"),
        fontBold=True
    )
    summary_style = ParagraphStyle(
        "SummaryText",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#1E293B")
    )
    header_style = ParagraphStyle(
        "TableHeader",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=8.5,
        leading=11,
        textColor=colors.white,
        fontBold=True
    )

    story = []

    # 1. Заголовок
    story.append(Paragraph("АНАЛИТИЧЕСКОЕ ДОСЬЕ И КАРТА СВЯЗЕЙ", title_style))
    story.append(Paragraph(
        f"Субъект проверки: <b>{dossier.subject.full_name}</b> &nbsp;|&nbsp; Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
        meta_style
    ))
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#2563EB"), spaceBefore=2, spaceAfter=8))

    # 2. Выводы аналитика
    story.append(Paragraph("1. Сводные выводы аналитика (Executive Summary)", h1_style))
    summary_p = Paragraph(f"<i>{dossier.executive_summary}</i>", summary_style)
    summary_table = Table([[summary_p]], colWidths=[515])
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#CBD5E1")),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 10))

    # 3. Карточка субъекта
    story.append(Paragraph("2. Анкета проверяемого лица", h1_style))
    subj_data = [
        [Paragraph("ФИО:", body_bold_style), Paragraph(dossier.subject.full_name, body_style)],
        [Paragraph("ИИН / ИНН:", body_bold_style), Paragraph(dossier.subject.iin or "Не указан", body_style)],
        [Paragraph("Дата рождения:", body_bold_style), Paragraph(dossier.subject.birth_date or "Не указана", body_style)],
        [Paragraph("Место рождения:", body_bold_style), Paragraph(dossier.subject.birth_place or "Не указано", body_style)],
        [Paragraph("Гражданство:", body_bold_style), Paragraph(dossier.subject.citizenship or "Не указано", body_style)],
    ]
    subj_table = Table(subj_data, colWidths=[130, 385])
    subj_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F1F5F9")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(subj_table)
    story.append(Spacer(1, 10))

    # 4. Контакты и адреса
    story.append(Paragraph("3. Контакты и адреса", h1_style))
    phones_txt = ", ".join(dossier.contacts.phone_numbers) if dossier.contacts.phone_numbers else "Не выявлены"
    emails_txt = ", ".join(dossier.contacts.emails) if dossier.contacts.emails else "Не выявлены"
    addrs_txt = "<br/>".join([f"• <b>[{a.address_type}]</b> {a.full_address}" for a in dossier.addresses]) if dossier.addresses else "Не выявлены"

    contacts_data = [
        [Paragraph("Телефоны:", body_bold_style), Paragraph(phones_txt, body_style)],
        [Paragraph("Email адреса:", body_bold_style), Paragraph(emails_txt, body_style)],
        [Paragraph("Адреса регистрации и факт.:", body_bold_style), Paragraph(addrs_txt, body_style)],
    ]
    contacts_tbl = Table(contacts_data, colWidths=[130, 385])
    contacts_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F1F5F9")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(contacts_tbl)
    story.append(Spacer(1, 10))

    # 5. Родственные связи
    story.append(Paragraph("4. Родственные и аффилированные связи", h1_style))
    if dossier.relatives_and_affiliates:
        rel_headers = [
            Paragraph("ФИО лица", header_style),
            Paragraph("Связь", header_style),
            Paragraph("ИИН", header_style),
            Paragraph("Общие признаки (совпадения)", header_style),
            Paragraph("Примечания", header_style)
        ]
        rel_rows = [rel_headers]
        for idx, rel in enumerate(dossier.relatives_and_affiliates):
            shared_text = "; ".join(rel.shared_attributes) if rel.shared_attributes else "—"
            row = [
                Paragraph(rel.full_name, body_bold_style),
                Paragraph(rel.relation_type, body_style),
                Paragraph(rel.iin or "—", body_style),
                Paragraph(f"<font color='#B45309'><b>{shared_text}</b></font>" if rel.shared_attributes else "—", body_style),
                Paragraph(rel.notes or "—", body_style),
            ]
            rel_rows.append(row)

        rel_tbl = Table(rel_rows, colWidths=[120, 75, 75, 140, 105])
        tbl_styles = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E293B")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]
        for i in range(1, len(rel_rows)):
            if i % 2 == 0:
                tbl_styles.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#F8FAFC")))
        rel_tbl.setStyle(TableStyle(tbl_styles))
        story.append(rel_tbl)
    else:
        story.append(Paragraph("<i>Родственные связи не выявлены.</i>", body_style))

    story.append(Spacer(1, 10))

    # 6. Места работы
    story.append(Paragraph("5. Места работы и занятость", h1_style))
    if dossier.employment_history:
        emp_headers = [
            Paragraph("Организация / Работодатель", header_style),
            Paragraph("БИН / ИНН", header_style),
            Paragraph("Должность", header_style),
            Paragraph("Период", header_style)
        ]
        emp_rows = [emp_headers]
        for emp in dossier.employment_history:
            emp_rows.append([
                Paragraph(emp.organization, body_bold_style),
                Paragraph(emp.bin or "—", body_style),
                Paragraph(emp.position or "—", body_style),
                Paragraph(emp.period or "—", body_style)
            ])
        emp_tbl = Table(emp_rows, colWidths=[185, 90, 140, 100])
        tbl_styles = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E293B")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]
        for i in range(1, len(emp_rows)):
            if i % 2 == 0:
                tbl_styles.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#F8FAFC")))
        emp_tbl.setStyle(TableStyle(tbl_styles))
        story.append(emp_tbl)
    else:
        story.append(Paragraph("<i>Сведения о местах работы не выявлены.</i>", body_style))

    # Генерация через кастомный канвас с нумерацией
    canvas_factory = NumberedCanvas.create_canvas_factory(dossier.subject.full_name, font_name)
    doc.build(story, canvasmaker=canvas_factory)
    return path


def _export_pdf_fpdf_fallback(dossier: DossierReport, path: Path) -> Path:
    """Отказоустойчивый генератор через fpdf2 при отсутствии reportlab."""
    from fpdf import FPDF

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, f"DOSSIER: {dossier.subject.full_name}", ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 8, f"Summary: {dossier.executive_summary}")
    pdf.output(str(path))
    return path
