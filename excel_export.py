"""Write simple, dependency-free Excel workbooks for exported sales reports."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Sequence
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile


def _column_name(number: int) -> str:
    name = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        name = chr(65 + remainder) + name
    return name


def _cell(reference: str, value: object, *, style_id: int = 0) -> str:
    style = f' s="{style_id}"' if style_id else ""
    if isinstance(value, bool):
        return f'<c r="{reference}" t="b"{style}><v>{int(value)}</v></c>'
    if isinstance(value, (int, float, Decimal)):
        return f'<c r="{reference}"{style}><v>{value}</v></c>'
    text = escape("" if value is None else str(value))
    return (
        f'<c r="{reference}" t="inlineStr"{style}>'
        f'<is><t xml:space="preserve">{text}</t></is></c>'
    )


def _worksheet(
    rows: Sequence[Sequence[object]],
    section_rows: Sequence[int] = (),
    strong_header_rows: Sequence[int] = (),
    currency_cells: set[str] | None = None,
    wrap_cells: set[str] | None = None,
    freeze_rows: int = 1,
    column_widths: dict[int, int] | None = None,
    body_start_row: int = 1,
    row_heights: dict[int, int] | None = None,
) -> str:
    row_xml: list[str] = []
    max_columns = max((len(row) for row in rows), default=1)
    widths = []
    for column in range(max_columns):
        widest = max(
            (len(str(row[column])) for row in rows if column < len(row)),
            default=12,
        )
        widths.append((column_widths or {}).get(column + 1, min(60, max(12, widest + 2))))
    columns_xml = "".join(
        f'<col min="{index}" max="{index}" width="{width}" customWidth="1"/>'
        for index, width in enumerate(widths, start=1)
    )
    for row_index, row in enumerate(rows, start=1):
        cells = "".join(
            _cell(f"{reference}", value, style_id=style_id)
            for column_index, value in enumerate(row, start=1)
            for reference in (f"{_column_name(column_index)}{row_index}",)
            for style_id in (
                5 if row_index == 1 else
                4 if row_index in strong_header_rows else
                1 if row_index in section_rows else
                2 if reference in (currency_cells or set()) else
                3 if reference in (wrap_cells or set()) else
                6 if row_index >= body_start_row else 0,
            )
        )
        height = (row_heights or {}).get(row_index)
        height_xml = f' ht="{height}" customHeight="1"' if height else ""
        row_xml.append(f'<row r="{row_index}"{height_xml}>{cells}</row>')
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<sheetPr><pageSetUpPr fitToPage="1"/></sheetPr>'
        f'<sheetViews><sheetView showGridLines="0" workbookViewId="0"><pane ySplit="{freeze_rows}" '
        f'topLeftCell="A{freeze_rows + 1}" activePane="bottomLeft" state="frozen"/>'
        '</sheetView></sheetViews>'
        f"<cols>{columns_xml}</cols>"
        f'<sheetData>{"".join(row_xml)}</sheetData>'
        '<printOptions gridLines="1" horizontalCentered="1"/>'
        '<pageMargins left="0.25" right="0.25" top="0.45" bottom="0.45" header="0.2" footer="0.2"/>'
        '<pageSetup orientation="landscape" paperSize="8" fitToWidth="1" fitToHeight="0"/>'
        '</worksheet>'
    )


def write_excel_workbook(
    path: str | Path,
    sheets: Sequence[tuple[str, Sequence[Sequence[object]]]],
    *,
    section_rows: dict[str, Sequence[int]] | None = None,
    strong_header_rows: dict[str, Sequence[int]] | None = None,
    currency_cells: dict[str, set[str]] | None = None,
    wrap_cells: dict[str, set[str]] | None = None,
    freeze_rows: dict[str, int] | None = None,
    column_widths: dict[str, dict[int, int]] | None = None,
    body_start_rows: dict[str, int] | None = None,
    print_title_rows: dict[str, tuple[int, int]] | None = None,
    row_heights: dict[str, dict[int, int]] | None = None,
) -> None:
    """Save named tables as a standards-compliant .xlsx workbook using only Python's stdlib."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet_types = "".join(
        f'<Override PartName="/xl/worksheets/sheet{index}.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for index in range(1, len(sheets) + 1)
    )
    sheet_refs = "".join(
        f'<sheet name="{escape(name[:31])}" sheetId="{index}" r:id="rId{index}"/>'
        for index, (name, _rows) in enumerate(sheets, start=1)
    )
    sheet_relationships = "".join(
        f'<Relationship Id="rId{index}" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        f'Target="worksheets/sheet{index}.xml"/>'
        for index in range(1, len(sheets) + 1)
    )
    styles_id = len(sheets) + 1
    defined_names = []
    for sheet_index, (sheet_name, sheet_rows) in enumerate(sheets):
        safe_name = sheet_name.replace("'", "''")
        last_row = max(1, len(sheet_rows))
        last_column = max(1, max((len(row) for row in sheet_rows), default=1))
        area = (
            f"'{safe_name}'!$A$1:${_column_name(last_column)}${last_row}"
        )
        defined_names.append(
            f'<definedName name="_xlnm.Print_Area" localSheetId="{sheet_index}">{escape(area)}</definedName>'
        )
        title_rows = (print_title_rows or {}).get(sheet_name)
        if title_rows:
            defined_names.append(
                f'<definedName name="_xlnm.Print_Titles" localSheetId="{sheet_index}">'
                f"'{safe_name}'!${title_rows[0]}:${title_rows[1]}</definedName>"
            )
    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<sheets>{sheet_refs}</sheets><definedNames>{"".join(defined_names)}</definedNames></workbook>'
    )
    workbook_relationships = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f'{sheet_relationships}<Relationship Id="rId{styles_id}" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
        'Target="styles.xml"/></Relationships>'
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        f'{sheet_types}<Override PartName="/xl/styles.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        '</Types>'
    )
    package_relationships = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/></Relationships>'
    )
    styles_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<numFmts count="1"><numFmt numFmtId="164" formatCode="&quot;₹&quot;#,##0.00"/></numFmts>'
        '<fonts count="3"><font><sz val="11"/><name val="Calibri"/></font>'
        '<font><b/><color rgb="FFFFFFFF"/><sz val="11"/><name val="Calibri"/></font>'
        '<font><b/><color rgb="FF123E43"/><sz val="16"/><name val="Calibri"/></font></fonts>'
        '<fills count="4"><fill><patternFill patternType="none"/></fill>'
        '<fill><patternFill patternType="solid"><fgColor rgb="FF0F766E"/><bgColor indexed="64"/></patternFill></fill>'
        '<fill><patternFill patternType="solid"><fgColor rgb="FF123E43"/><bgColor indexed="64"/></patternFill></fill>'
        '<fill><patternFill patternType="solid"><fgColor rgb="FFD8EEEA"/><bgColor indexed="64"/></patternFill></fill></fills>'
        '<borders count="2"><border><left/><right/><top/><bottom/><diagonal/></border>'
        '<border><left style="thin"><color rgb="FFD3DDE0"/></left><right style="thin"><color rgb="FFD3DDE0"/></right>'
        '<top style="thin"><color rgb="FFD3DDE0"/></top><bottom style="thin"><color rgb="FFD3DDE0"/></bottom><diagonal/></border></borders>'
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
        '<cellXfs count="7"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
        '<xf numFmtId="0" fontId="1" fillId="1" borderId="1" applyFont="1" applyFill="1" applyBorder="1" xfId="0"/>'
        '<xf numFmtId="164" fontId="0" fillId="0" borderId="1" applyNumberFormat="1" applyBorder="1" xfId="0"/>'
        '<xf numFmtId="0" fontId="0" fillId="0" borderId="1" applyAlignment="1" applyBorder="1" xfId="0"><alignment wrapText="1" vertical="top"/></xf>'
        '<xf numFmtId="0" fontId="1" fillId="2" borderId="1" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1" xfId="0"><alignment wrapText="1" vertical="center" horizontal="center"/></xf>'
        '<xf numFmtId="0" fontId="2" fillId="3" borderId="0" applyFont="1" applyFill="1" xfId="0"/>'
        '<xf numFmtId="0" fontId="0" fillId="0" borderId="1" applyBorder="1" xfId="0"/>'
        '</cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
        '</styleSheet>'
    )

    with ZipFile(path, "w", ZIP_DEFLATED) as workbook:
        workbook.writestr("[Content_Types].xml", content_types)
        workbook.writestr("_rels/.rels", package_relationships)
        workbook.writestr("xl/workbook.xml", workbook_xml)
        workbook.writestr("xl/_rels/workbook.xml.rels", workbook_relationships)
        workbook.writestr("xl/styles.xml", styles_xml)
        for index, (name, rows) in enumerate(sheets, start=1):
            workbook.writestr(
                f"xl/worksheets/sheet{index}.xml",
                _worksheet(
                    rows,
                    (section_rows or {}).get(name, ()),
                    (strong_header_rows or {}).get(name, ()),
                    (currency_cells or {}).get(name, set()),
                    (wrap_cells or {}).get(name, set()),
                    (freeze_rows or {}).get(name, 1),
                    (column_widths or {}).get(name),
                    (body_start_rows or {}).get(name, 1),
                    (row_heights or {}).get(name),
                ),
            )
