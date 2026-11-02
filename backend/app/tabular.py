"""Minimal, dependency-free spreadsheet I/O: read .xlsx (first sheet) or .csv, write .xlsx or UTF-8 CSV.

Only the standard library is used (zipfile + xml), so no new runtime dependency is added. Reading supports
shared strings, inline strings, numbers and booleans; formulas are read as their cached value.
"""
from __future__ import annotations

import csv
import io
import re
import zipfile
from typing import Iterable
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
MAX_ROWS = 5000


class TableError(ValueError):
    pass


def _col_index(ref: str) -> int:
    letters = re.match(r"[A-Z]+", ref or "A").group(0)
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def read_table(filename: str, data: bytes) -> list[list[str]]:
    name = (filename or "").lower()
    if name.endswith(".csv") or not data.startswith(b"PK"):
        text = data.decode("utf-8-sig", errors="strict") if data else ""
        rows = [[c.strip() for c in r] for r in csv.reader(io.StringIO(text))]
    else:
        try:
            z = zipfile.ZipFile(io.BytesIO(data))
            shared: list[str] = []
            if "xl/sharedStrings.xml" in z.namelist():
                for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", NS):
                    shared.append("".join(t.text or "" for t in si.iter(f"{{{NS['m']}}}t")))
            sheet = next((n for n in sorted(z.namelist()) if n.startswith("xl/worksheets/sheet")), None)
            if sheet is None:
                raise TableError("برگه‌ای در فایل پیدا نشد")
            rows = []
            for row in ET.fromstring(z.read(sheet)).iter(f"{{{NS['m']}}}row"):
                cells: dict[int, str] = {}
                for c in row.findall("m:c", NS):
                    t = c.get("t")
                    v = c.find("m:v", NS)
                    if t == "s" and v is not None:
                        val = shared[int(v.text)]
                    elif t == "inlineStr":
                        val = "".join(x.text or "" for x in c.iter(f"{{{NS['m']}}}t"))
                    elif v is not None:
                        val = v.text or ""
                        if re.fullmatch(r"-?\d+\.0", val):
                            val = val[:-2]
                    else:
                        val = ""
                    cells[_col_index(c.get("r", "A"))] = val.strip()
                rows.append([cells.get(i, "") for i in range(max(cells) + 1)] if cells else [])
        except (zipfile.BadZipFile, KeyError, ET.ParseError, IndexError, ValueError) as exc:
            if isinstance(exc, TableError):
                raise
            raise TableError("فایل اکسل خوانده نشد؛ آن را با پسوند xlsx یا csv ذخیره کنید") from exc
    rows = [r for r in rows if any(c for c in r)]
    if len(rows) > MAX_ROWS + 1:
        raise TableError(f"حداکثر {MAX_ROWS} ردیف در هر فایل")
    return rows


def _cell(ref: str, value) -> str:
    if isinstance(value, bool):
        return f'<c r="{ref}" t="b"><v>{int(value)}</v></c>'
    if isinstance(value, (int, float)):
        return f'<c r="{ref}"><v>{value}</v></c>'
    return f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{escape(str(value if value is not None else ""))}</t></is></c>'


def _ref(col: int, row: int) -> str:
    s = ""
    col += 1
    while col:
        col, r = divmod(col - 1, 26)
        s = chr(65 + r) + s
    return f"{s}{row}"


def write_xlsx(header: list[str], rows: Iterable[list], sheet_name: str = "Sheet1", rtl: bool = True) -> bytes:
    body = []
    for ri, row in enumerate([header, *rows], start=1):
        body.append(f'<row r="{ri}">' + "".join(_cell(_ref(ci, ri), v) for ci, v in enumerate(row)) + "</row>")
    view = ' rightToLeft="1"' if rtl else ''
    sheet = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
             '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
             f'<sheetViews><sheetView workbookViewId="0"{view}/></sheetViews>'
             f'<sheetData>{"".join(body)}</sheetData></worksheet>')
    files = {
        "[Content_Types].xml": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                               '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>'
                               '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                               '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>',
        "_rels/.rels": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                       '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
        "xl/workbook.xml": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                           'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                           f'<sheets><sheet name="{escape(sheet_name)}" sheetId="1" r:id="rId1"/></sheets></workbook>',
        "xl/_rels/workbook.xml.rels": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                                      '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>',
        "xl/worksheets/sheet1.xml": sheet,
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, content in files.items():
            z.writestr(name, content)
    return buf.getvalue()


def write_csv(header: list[str], rows: Iterable[list]) -> bytes:
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(header)
    for r in rows:
        w.writerow(["" if v is None else v for v in r])
    return ("﻿" + out.getvalue()).encode("utf-8")
