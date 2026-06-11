#!/usr/bin/env python3
"""Converte DASHBOARD.md para PDF usando fpdf2."""

import re
from pathlib import Path
from fpdf import FPDF

MD_FILE = Path(__file__).parent / "DASHBOARD.md"
PDF_FILE = Path(__file__).parent / "DASHBOARD.pdf"


class DashboardPDF(FPDF):
    def __init__(self):
        super().__init__()
        self.add_page()
        self.set_auto_page_break(auto=True, margin=20)
        self.set_font("Helvetica", size=10)

    def header(self):
        if self.page_no() > 1:
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(150, 150, 150)
            self.cell(0, 8, "Dashboard Globoplay - Qualidade de Software", align="R")
            self.ln(4)
            self.set_draw_color(200, 200, 200)
            self.line(10, self.get_y(), 200, self.get_y())
            self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, "Pagina %d/{nb}" % self.page_no(), align="C")

    def _clean(self, text):
        text = re.sub(r'[\U00010000-\U0010ffff]', '', text)
        return text.encode('latin-1', errors='replace').decode('latin-1')

    def write_title(self, text, level=1):
        sizes = {1: 18, 2: 15, 3: 13, 4: 11}
        colors = {1: (26, 26, 46), 2: (22, 33, 62), 3: (15, 52, 96), 4: (51, 51, 51)}
        sz = sizes.get(level, 10)
        r, g, b = colors.get(level, (0, 0, 0))
        self.set_font("Helvetica", "B", sz)
        self.set_text_color(r, g, b)
        self.ln(4 if level > 2 else 6)
        self.multi_cell(0, sz * 0.6, self._clean(text))
        if level <= 2:
            if level == 1:
                self.set_draw_color(233, 69, 96)
            else:
                self.set_draw_color(200, 200, 200)
            self.line(10, self.get_y() + 1, 200, self.get_y() + 1)
            self.ln(3)
        self.ln(2)

    def write_paragraph(self, text):
        self.set_font("Helvetica", size=10)
        self.set_text_color(34, 34, 34)
        clean = re.sub(r'`([^`]+)`', r'\1', text)
        parts = re.split(r'\*\*(.*?)\*\*', clean)
        for idx, part in enumerate(parts):
            if idx % 2 == 1:
                self.set_font("Helvetica", "B", 10)
            else:
                self.set_font("Helvetica", "", 10)
            self.write(5, self._clean(part))
        self.ln(6)

    def write_bullet(self, text, indent=0):
        self.set_font("Helvetica", size=10)
        self.set_text_color(34, 34, 34)
        x = 12 + indent * 6
        self.set_x(x)
        self.cell(4, 5, "-")
        self.set_x(x + 5)
        clean = re.sub(r'`([^`]+)`', r'\1', text)
        parts = re.split(r'\*\*(.*?)\*\*', clean)
        for idx, part in enumerate(parts):
            if idx % 2 == 1:
                self.set_font("Helvetica", "B", 10)
            else:
                self.set_font("Helvetica", "", 10)
            self.write(5, self._clean(part))
        self.ln(5)

    def write_table(self, headers, rows):
        self.ln(2)
        col_count = len(headers)
        col_w = 190 / col_count
        self.set_font("Helvetica", "B", 8)
        self.set_fill_color(22, 33, 62)
        self.set_text_color(255, 255, 255)
        for h in headers:
            self.cell(col_w, 7, self._clean(h.strip()), border=1, fill=True, align="C")
        self.ln()
        self.set_font("Helvetica", size=8)
        self.set_text_color(34, 34, 34)
        for idx, row in enumerate(rows):
            if idx % 2 == 1:
                self.set_fill_color(245, 245, 245)
            else:
                self.set_fill_color(255, 255, 255)
            for cell_text in row:
                clean = re.sub(r'[`*]', '', cell_text.strip())
                self.cell(col_w, 6, self._clean(clean), border=1, fill=True)
            self.ln()
        self.ln(4)

    def write_code_block(self, code):
        self.set_font("Courier", size=8)
        self.set_text_color(50, 50, 50)
        self.set_fill_color(240, 240, 240)
        for cline in code.split('\n'):
            self.set_x(12)
            self.cell(186, 5, self._clean(cline), fill=True)
            self.ln()
        self.ln(4)

    def write_hr(self):
        self.ln(3)
        self.set_draw_color(220, 220, 220)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(5)


def parse_and_generate():
    text = MD_FILE.read_text(encoding="utf-8")
    lines = text.split('\n')
    pdf = DashboardPDF()
    pdf.alias_nb_pages()

    in_code = False
    code_buf = []
    in_table = False
    table_headers = []
    table_rows = []
    in_math = False
    math_buf = []

    idx = 0
    while idx < len(lines):
        line = lines[idx]

        # Math block
        if line.strip() == '$$':
            if not in_math:
                in_math = True
                idx += 1
                continue
            else:
                in_math = False
                formula = ' '.join(math_buf)
                math_buf = []
                pdf.set_font("Courier", "I", 9)
                pdf.set_text_color(80, 80, 80)
                pdf.set_x(14)
                pdf.multi_cell(180, 5, pdf._clean(formula))
                pdf.ln(3)
                idx += 1
                continue
        if in_math:
            math_buf.append(line.strip())
            idx += 1
            continue

        # Code block
        if line.strip().startswith('```'):
            if in_code:
                pdf.write_code_block('\n'.join(code_buf))
                code_buf = []
                in_code = False
            else:
                in_code = True
            idx += 1
            continue
        if in_code:
            code_buf.append(line)
            idx += 1
            continue

        # Table
        if '|' in line and line.strip().startswith('|'):
            cells = [c.strip() for c in line.strip().strip('|').split('|')]
            if all(re.match(r'^[-:]+$', c) for c in cells):
                idx += 1
                continue
            if not in_table:
                in_table = True
                table_headers = cells
            else:
                table_rows.append(cells)
            idx += 1
            continue
        else:
            if in_table:
                pdf.write_table(table_headers, table_rows)
                in_table = False
                table_headers = []
                table_rows = []

        stripped = line.strip()
        if not stripped:
            idx += 1
            continue
        if stripped == '---':
            pdf.write_hr()
            idx += 1
            continue

        m = re.match(r'^(#{1,4})\s+(.+)$', stripped)
        if m:
            pdf.write_title(m.group(2), len(m.group(1)))
            idx += 1
            continue

        m = re.match(r'^(\s*)[-*]\s+(.+)$', line)
        if m:
            pdf.write_bullet(m.group(2), len(m.group(1)) // 2)
            idx += 1
            continue

        pdf.write_paragraph(stripped)
        idx += 1

    if in_table:
        pdf.write_table(table_headers, table_rows)

    pdf.output(str(PDF_FILE))
    print("PDF gerado com sucesso: " + str(PDF_FILE))


if __name__ == "__main__":
    parse_and_generate()
