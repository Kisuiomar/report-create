"""
DOCX Builder for Forensic Reports.
Parses Markdown text and generates a highly stylized Microsoft Word document.
"""

import os
import re
from pathlib import Path
from typing import List, Dict, Any, Optional

import docx
from docx import Document
from docx.shared import Cm, Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.oxml.shared import OxmlElement, qn


def _detect_docx_font() -> str:
    """Detect available system font (Arial -> Calibri -> Liberation Sans)."""
    font_candidates = [
        ("Arial", [r"C:\Windows\Fonts\arial.ttf", "/usr/share/fonts/truetype/msttcorefonts/Arial.ttf"]),
        ("Calibri", [r"C:\Windows\Fonts\calibri.ttf"]),
        ("Liberation Sans", ["/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"]),
    ]
    for font_name, paths in font_candidates:
        for path in paths:
            if os.path.exists(path):
                return font_name
    return "Calibri"

_DOCX_FONT_NAME = _detect_docx_font()


def _set_cell_background(cell, fill_hex: str):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), fill_hex)
    tc_pr.append(shd)


def _set_cell_margins(cell, top=120, bottom=120, left=160, right=160): # 6pt/8pt approx
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_mar = OxmlElement('w:tcMar')
    for m, val in [('top', top), ('bottom', bottom), ('left', left), ('right', right)]:
        node = OxmlElement(f'w:{m}')
        node.set(qn('w:w'), str(val))
        node.set(qn('w:type'), 'dxa')
        tc_mar.append(node)
    tc_pr.append(tc_mar)


def _set_table_borders(table, border_color="D9D9D9", inside_hz="single", inside_vt="single"):
    tbl_pr = table._element.xpath('w:tblPr')
    if tbl_pr:
        tbl_borders = OxmlElement('w:tblBorders')
        
        # Top and Bottom thin grey
        for b_type in ['top', 'bottom', 'insideH']:
            border = OxmlElement(f'w:{b_type}')
            border.set(qn('w:val'), 'single')
            border.set(qn('w:sz'), '4') # 1/2 pt
            border.set(qn('w:space'), '0')
            border.set(qn('w:color'), border_color)
            tbl_borders.append(border)
            
        # Inside vertical thin grey
        if inside_vt:
            border = OxmlElement('w:insideV')
            border.set(qn('w:val'), 'single')
            border.set(qn('w:sz'), '4')
            border.set(qn('w:space'), '0')
            border.set(qn('w:color'), border_color)
            tbl_borders.append(border)
            
        tbl_pr[0].append(tbl_borders)


def _add_bottom_border_to_paragraph(p):
    pPr = p._p.get_or_add_pPr()
    pBdr = OxmlElement('w:pBdr')
    bottom = OxmlElement('w:bottom')
    bottom.set(qn('w:val'), 'single')
    bottom.set(qn('w:sz'), '6')
    bottom.set(qn('w:space'), '1')
    bottom.set(qn('w:color'), '1F4E79')
    pBdr.append(bottom)
    pPr.append(pBdr)


def _add_left_thick_border_to_paragraph(p):
    pPr = p._p.get_or_add_pPr()
    pBdr = OxmlElement('w:pBdr')
    left = OxmlElement('w:left')
    left.set(qn('w:val'), 'single')
    left.set(qn('w:sz'), '24') # 3pt
    left.set(qn('w:space'), '14')
    left.set(qn('w:color'), 'C00000')
    pBdr.append(left)
    
    # Background for paragraph
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), 'FDF2F2')
    pPr.append(shd)
    pPr.append(pBdr)


def _create_page_number_field(paragraph):
    # This is a bit complex in python-docx, we add XML fields for Page X of Y
    run = paragraph.add_run("Страница ")
    run.font.name = _DOCX_FONT_NAME
    run.font.size = Pt(9)
    run.font.color.rgb = RGBColor(128, 128, 128)
    
    # Add PAGE field
    fldChar1 = OxmlElement('w:fldChar')
    fldChar1.set(qn('w:fldCharType'), 'begin')
    
    instrText1 = OxmlElement('w:instrText')
    instrText1.set(qn('xml:space'), 'preserve')
    instrText1.text = 'PAGE'
    
    fldChar2 = OxmlElement('w:fldChar')
    fldChar2.set(qn('w:fldCharType'), 'end')
    
    r1 = OxmlElement('w:r')
    r1.append(fldChar1)
    r1.append(instrText1)
    r1.append(fldChar2)
    paragraph._p.append(r1)
    
    run = paragraph.add_run(" из ")
    run.font.name = _DOCX_FONT_NAME
    run.font.size = Pt(9)
    run.font.color.rgb = RGBColor(128, 128, 128)
    
    # Add NUMPAGES field
    fldChar3 = OxmlElement('w:fldChar')
    fldChar3.set(qn('w:fldCharType'), 'begin')
    
    instrText2 = OxmlElement('w:instrText')
    instrText2.set(qn('xml:space'), 'preserve')
    instrText2.text = 'NUMPAGES'
    
    fldChar4 = OxmlElement('w:fldChar')
    fldChar4.set(qn('w:fldCharType'), 'end')
    
    r2 = OxmlElement('w:r')
    r2.append(fldChar3)
    r2.append(instrText2)
    r2.append(fldChar4)
    paragraph._p.append(r2)


class DossierDocxBuilder:
    def __init__(self):
        self.doc = Document()
        self._setup_page()

    def _setup_page(self):
        for section in self.doc.sections:
            section.top_margin = Cm(2.0)
            section.bottom_margin = Cm(2.0)
            section.left_margin = Cm(2.5)
            section.right_margin = Cm(1.5)
            
            # Header
            header = section.header
            p_hdr = header.paragraphs[0]
            p_hdr.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            r_hdr = p_hdr.add_run("КОНФИДЕНЦИАЛЬНО / ДСП")
            r_hdr.font.name = _DOCX_FONT_NAME
            r_hdr.font.size = Pt(9)
            r_hdr.font.bold = True
            r_hdr.font.color.rgb = RGBColor(192, 0, 0)
            
            # Footer
            footer = section.footer
            p_ftr = footer.paragraphs[0]
            p_ftr.alignment = WD_ALIGN_PARAGRAPH.CENTER
            _create_page_number_field(p_ftr)

        # Default style for body
        style = self.doc.styles['Normal']
        style.font.name = _DOCX_FONT_NAME
        style.font.size = Pt(10.5)
        style.font.color.rgb = RGBColor(38, 38, 38) # #262626
        style.paragraph_format.line_spacing = 1.15
        style.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        style.paragraph_format.space_after = Pt(8)

    def add_title_block(self, title: str, subtitle: str = ""):
        p = self.doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        p.paragraph_format.space_after = Pt(12)
        r = p.add_run(title.upper())
        r.font.name = _DOCX_FONT_NAME
        r.font.size = Pt(20)
        r.font.bold = True
        r.font.color.rgb = RGBColor(31, 78, 121) # #1F4E79
        
        if subtitle:
            p2 = self.doc.add_paragraph()
            p2.paragraph_format.space_after = Pt(16)
            r2 = p2.add_run(subtitle)
            r2.font.name = _DOCX_FONT_NAME
            r2.font.size = Pt(11)
            r2.font.italic = True
            r2.font.color.rgb = RGBColor(89, 89, 89) # #595959

    def add_heading_1(self, text: str):
        p = self.doc.add_paragraph()
        p.paragraph_format.space_before = Pt(18)
        p.paragraph_format.space_after = Pt(6)
        r = p.add_run(text)
        r.font.name = _DOCX_FONT_NAME
        r.font.size = Pt(14)
        r.font.bold = True
        r.font.color.rgb = RGBColor(31, 78, 121) # #1F4E79
        _add_bottom_border_to_paragraph(p)

    def add_heading_2(self, text: str):
        p = self.doc.add_paragraph()
        p.paragraph_format.space_before = Pt(12)
        p.paragraph_format.space_after = Pt(4)
        r = p.add_run(text)
        r.font.name = _DOCX_FONT_NAME
        r.font.size = Pt(12)
        r.font.bold = True
        r.font.color.rgb = RGBColor(47, 85, 151) # #2F5597

    def add_callout_box(self, text: str, level: str = "critical"):
        # We can implement it as a 1x1 table or a styled paragraph.
        # Using a styled paragraph is cleaner for simple callouts.
        p = self.doc.add_paragraph()
        p.paragraph_format.space_before = Pt(8)
        p.paragraph_format.space_after = Pt(8)
        
        # Apply left border and pink background
        _add_left_thick_border_to_paragraph(p)
        
        # Set text indents so text isn't cramped on the border
        p.paragraph_format.left_indent = Pt(12)
        
        r = p.add_run(text)
        r.font.name = _DOCX_FONT_NAME
        r.font.size = Pt(10)
        r.font.color.rgb = RGBColor(38, 38, 38)
        
        if level == "critical":
            r.font.bold = True

    def add_risk_badge(self, text: str):
        table = self.doc.add_table(rows=1, cols=1)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        cell = table.cell(0, 0)
        _set_cell_background(cell, "C00000") # Red
        _set_cell_margins(cell, top=100, bottom=100, left=200, right=200)
        
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(0)
        
        r = p.add_run(text.upper())
        r.font.name = _DOCX_FONT_NAME
        r.font.size = Pt(12)
        r.font.bold = True
        r.font.color.rgb = RGBColor(255, 255, 255) # White
        
        self.doc.add_paragraph() # Spacer

    def add_styled_table(self, headers: List[str], rows_data: List[List[str]]):
        table = self.doc.add_table(rows=1, cols=len(headers))
        table.alignment = WD_TABLE_ALIGNMENT.LEFT
        table.autofit = True
        _set_table_borders(table, border_color="D9D9D9")
        
        # Header row
        hdr_row = table.rows[0]
        # Repeat header row on new page
        tr = hdr_row._tr
        trPr = tr.get_or_add_trPr()
        tblHeader = OxmlElement('w:tblHeader')
        tblHeader.set(qn('w:val'), "true")
        trPr.append(tblHeader)
        cantSplit = OxmlElement('w:cantSplit')
        cantSplit.set(qn('w:val'), "true")
        trPr.append(cantSplit)
        
        for idx, text in enumerate(headers):
            cell = hdr_row.cells[idx]
            _set_cell_background(cell, "1F4E79")
            _set_cell_margins(cell)
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            r = p.add_run(text.strip())
            r.font.name = _DOCX_FONT_NAME
            r.font.size = Pt(10)
            r.font.bold = True
            r.font.color.rgb = RGBColor(255, 255, 255)
            
        # Data rows
        for row_idx, row_data in enumerate(rows_data):
            row = table.add_row()
            # Zebra striping: even rows white (index 0 is white), odd rows light grey
            bg_color = "F2F4F7" if row_idx % 2 == 1 else "FFFFFF"
            
            for col_idx, text in enumerate(row_data):
                # Handle missing columns if malformed
                if col_idx >= len(headers):
                    break
                cell = row.cells[col_idx]
                _set_cell_background(cell, bg_color)
                _set_cell_margins(cell)
                p = cell.paragraphs[0]
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                
                # Apply bold formatting if ** exists
                parts = re.split(r'(\*\*.*?\*\*)', text.strip())
                for part in parts:
                    if part.startswith('**') and part.endswith('**'):
                        r = p.add_run(part[2:-2])
                        r.font.bold = True
                    else:
                        r = p.add_run(part)
                    r.font.name = _DOCX_FONT_NAME
                    r.font.size = Pt(9.5)

        self.doc.add_paragraph().paragraph_format.space_after = Pt(12)

    def parse_markdown(self, markdown_text: str):
        lines = markdown_text.split('\n')
        i = 0
        
        in_table = False
        table_headers = []
        table_rows = []
        
        while i < len(lines):
            line = lines[i].strip()
            
            # Skip empty lines unless we're not in a table
            if not line:
                if in_table:
                    # Flush table
                    self.add_styled_table(table_headers, table_rows)
                    in_table = False
                    table_headers = []
                    table_rows = []
                i += 1
                continue
                
            # Table processing (Simple parser for | Col 1 | Col 2 | format)
            if line.startswith('|') and line.endswith('|'):
                cells = [cell.strip() for cell in line.split('|')[1:-1]]
                
                if not in_table:
                    in_table = True
                    table_headers = cells
                    # Skip separator line if it exists on the next line
                    if i + 1 < len(lines) and lines[i+1].strip().startswith('|') and '-' in lines[i+1]:
                        i += 1
                else:
                    # Ignore separator lines within table (shouldn't happen but just in case)
                    if all(c == '' or set(c).issubset({'-', ':', ' '}) for c in cells):
                        pass
                    else:
                        table_rows.append(cells)
                i += 1
                continue
            elif '\t' in line and not in_table and len(line.split('\t')) > 1:
                # Tab separated parser (fallback for some markdown/copy-pastes)
                cells = [cell.strip() for cell in line.split('\t')]
                if not in_table:
                    in_table = True
                    table_headers = cells
                else:
                    table_rows.append(cells)
                i += 1
                continue
            
            if in_table:
                # Flush table if we hit non-table line
                self.add_styled_table(table_headers, table_rows)
                in_table = False
                table_headers = []
                table_rows = []

            # Risk Badge / Callout
            if "УРОВЕНЬ РИСКА: ВЫСОКИЙ" in line.upper() or "НЕБЛАГОНАДЁЖНЫЙ КОНТРАГЕНТ" in line.upper():
                self.add_risk_badge(line)
            elif line.startswith("Критическое замечание:") or line.startswith(">"):
                self.add_callout_box(line.lstrip(">").strip())
            # Headings
            elif line.startswith("### "):
                self.add_heading_2(line[4:])
            elif line.startswith("## "):
                self.add_heading_1(line[3:])
            elif line.startswith("# "):
                # Usually Title
                self.add_title_block(line[2:])
            elif re.match(r'^\d+\.\s+[А-Я]', line) and "Резюме" not in line and len(line) < 100:
                # Custom H1 matcher for lines like "1. Резюме (Executive Summary)" if # is missing
                self.add_heading_1(line)
            elif re.match(r'^\d+\.\d+\.\s+[А-Я]', line) and len(line) < 100:
                # Custom H2 matcher
                self.add_heading_2(line)
            elif "КОНСОЛИДИРОВАННЫЙ" in line.upper() or "АНАЛИТИЧЕСКИЙ ОТЧЁТ" in line.upper():
                 self.add_title_block(line)
            else:
                # Normal paragraph
                p = self.doc.add_paragraph()
                
                # Apply bold formatting if ** exists
                parts = re.split(r'(\*\*.*?\*\*)', line)
                for part in parts:
                    if part.startswith('**') and part.endswith('**'):
                        r = p.add_run(part[2:-2])
                        r.font.bold = True
                    else:
                        r = p.add_run(part)
                    
            i += 1
            
        # Flush table if document ends with one
        if in_table:
            self.add_styled_table(table_headers, table_rows)

    def save(self, output_path: str):
        self.doc.save(output_path)
