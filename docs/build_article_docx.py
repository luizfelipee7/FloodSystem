"""Render the anonymized article draft as an editable RICSS-style DOCX."""

import re
from pathlib import Path

from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "artigo-ricss-ensaio-computacional-rascunho.md"
OUTPUT = ROOT / "artigo" / "FloodSystem_Artigo_RICSS_Rascunho_Ensaio_Computacional.docx"


def font(style, size, bold=False, italic=False):
    style.font.name = "Arial"
    style.font.size = Pt(size)
    style.font.bold = bold
    style.font.italic = italic
    style.font.color.rgb = None


def rich(paragraph, value):
    pattern = re.compile(r"(<sup>.*?</sup>|\*\*.*?\*\*|`.*?`)")
    for piece in pattern.split(value):
        if not piece:
            continue
        if piece.startswith("<sup>"):
            run = paragraph.add_run(piece[5:-6])
            run.font.superscript = True
        elif piece.startswith("**"):
            run = paragraph.add_run(piece[2:-2])
            run.bold = True
        elif piece.startswith("`"):
            paragraph.add_run(piece[1:-1])
        else:
            paragraph.add_run(piece)


def add_table(document, lines):
    rows = [[item.strip() for item in line.strip().strip("|").split("|")]
            for line in lines if not re.match(r"^\|\s*[-:]", line)]
    table = document.add_table(rows=len(rows), cols=len(rows[0]))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    widths = [Cm(x) for x in (2.2, 3.2, 3.0, 3.4, 4.1)]
    for i, row in enumerate(rows):
        for j, value in enumerate(row):
            cell = table.cell(i, j)
            cell.width = widths[j]
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            p = cell.paragraphs[0]
            p.style = document.styles["Table Text"]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER if j else WD_ALIGN_PARAGRAPH.LEFT
            p.paragraph_format.keep_with_next = i < len(rows) - 1
            rich(p, value)
            if i == 0:
                for run in p.runs:
                    run.bold = True
        tr_pr = table.rows[i]._tr.get_or_add_trPr()
        tr_pr.append(OxmlElement("w:cantSplit"))
    table.rows[0]._tr.get_or_add_trPr().append(OxmlElement("w:tblHeader"))
    for edge in ("top", "bottom", "insideH"):
        borders = table._tbl.tblPr.first_child_found_in("w:tblBorders")
        if borders is None:
            borders = OxmlElement("w:tblBorders")
            table._tbl.tblPr.append(borders)
        node = OxmlElement(f"w:{edge}")
        node.set(qn("w:val"), "single")
        node.set(qn("w:sz"), "4")
        node.set(qn("w:color"), "999999")
        borders.append(node)
    document.add_paragraph().paragraph_format.space_after = Pt(0)


def main():
    lines = SOURCE.read_text(encoding="utf-8").splitlines()
    doc = Document()
    section = doc.sections[0]
    section.page_width, section.page_height = Cm(21), Cm(29.7)
    section.top_margin = section.left_margin = Cm(3)
    section.bottom_margin = section.right_margin = Cm(2)

    normal = doc.styles["Normal"]
    font(normal, 12)
    normal.paragraph_format.line_spacing = 1.5
    normal.paragraph_format.space_after = Pt(0)
    normal.paragraph_format.first_line_indent = Cm(1.25)
    normal.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    for name in ("Title", "Heading 1", "Heading 2"):
        style = doc.styles[name]
        font(style, 14 if name == "Title" else 12, bold=True)
        style.paragraph_format.first_line_indent = Cm(0)
        style.paragraph_format.space_before = Pt(10 if name != "Title" else 0)
        style.paragraph_format.space_after = Pt(5)
        style.paragraph_format.keep_with_next = True
        style.paragraph_format.line_spacing = 1.5
    doc.styles["Title"].paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title_ppr = doc.styles["Title"]._element.get_or_add_pPr()
    for border in title_ppr.findall(qn("w:pBdr")):
        title_ppr.remove(border)
    for style_name in ("Subtitle", "Table Text", "Table Caption", "Reference"):
        if style_name not in doc.styles:
            from docx.enum.style import WD_STYLE_TYPE
            doc.styles.add_style(style_name, WD_STYLE_TYPE.PARAGRAPH)
    font(doc.styles["Subtitle"], 12, italic=True)
    doc.styles["Subtitle"].paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.styles["Subtitle"].paragraph_format.first_line_indent = Cm(0)
    doc.styles["Subtitle"].paragraph_format.space_after = Pt(10)
    font(doc.styles["Table Text"], 10)
    doc.styles["Table Text"].paragraph_format.first_line_indent = Cm(0)
    doc.styles["Table Text"].paragraph_format.line_spacing = 1.0
    doc.styles["Table Text"].paragraph_format.space_after = Pt(3)
    font(doc.styles["Table Caption"], 10)
    doc.styles["Table Caption"].paragraph_format.first_line_indent = Cm(0)
    doc.styles["Table Caption"].paragraph_format.keep_with_next = True
    doc.styles["Table Caption"].paragraph_format.space_before = Pt(6)
    doc.styles["Table Caption"].paragraph_format.space_after = Pt(3)
    font(doc.styles["Reference"], 12)
    doc.styles["Reference"].paragraph_format.first_line_indent = Cm(-0.55)
    doc.styles["Reference"].paragraph_format.left_indent = Cm(0.55)
    doc.styles["Reference"].paragraph_format.line_spacing = 1.5
    doc.styles["Reference"].paragraph_format.keep_together = True

    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    footer.style = doc.styles["Table Text"]
    fld = OxmlElement("w:fldSimple")
    fld.set(qn("w:instr"), "PAGE")
    footer._p.append(fld)

    i = 0
    title_seen = False
    abstract_pending = False
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        if line.startswith("| "):
            table_lines = []
            while i < len(lines) and lines[i].startswith("|"):
                table_lines.append(lines[i])
                i += 1
            add_table(doc, table_lines)
            continue
        if line.startswith("# "):
            p = doc.add_paragraph(style="Title")
            rich(p, line[2:])
            title_seen = True
        elif title_seen and line.startswith("**Traceable"):
            p = doc.add_paragraph(style="Subtitle")
            rich(p, line[2:-2])
        elif line.startswith("**Versão de trabalho"):
            # Editorial note belongs to the internal Markdown copy, not the blinded manuscript.
            pass
        elif line.startswith("## "):
            p = doc.add_paragraph(style="Heading 1")
            rich(p, line[3:])
            abstract_pending = line in ("## Resumo preliminar", "## Preliminary abstract")
        elif line.startswith("### "):
            p = doc.add_paragraph(style="Heading 2")
            rich(p, line[4:])
        elif line.startswith("**Tabela ") or line.startswith("Fonte:"):
            p = doc.add_paragraph(style="Table Caption")
            rich(p, line)
        elif re.match(r"^\d+\. ", line):
            p = doc.add_paragraph(style="Reference")
            rich(p, line)
        else:
            p = doc.add_paragraph(style="Normal")
            rich(p, line)
            if abstract_pending:
                p.paragraph_format.keep_together = True
                abstract_pending = False
        i += 1

    doc.core_properties.title = "Conversão rastreável de chuva horária em eventos simulados de pluviômetro"
    doc.core_properties.subject = "Estudo computacional de monitoramento ambiental"
    doc.core_properties.author = ""
    doc.core_properties.last_modified_by = ""
    OUTPUT.parent.mkdir(exist_ok=True)
    doc.save(OUTPUT)
    print(OUTPUT)


if __name__ == "__main__":
    main()
