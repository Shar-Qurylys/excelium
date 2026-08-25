"""Реестр предстоящих оплат (по приоритету): лист на объект.

Порт models/priority_registry.py; прямые обращения по ключам заменены
на .get() с пустыми значениями, дубли импортов убраны.
"""
from collections import defaultdict
from datetime import datetime

import openpyxl
from openpyxl.styles import Font

from .common import add_colontituls, format_row, set_print_area

DATA_COLS = ["A", "B", "C", "D", "E", "F", "G"]
START_ROW = 7


def render_priority(entries: list[dict], template_path):
    workbook = openpyxl.load_workbook(template_path)
    template_sheet = workbook["REESTR"]
    font = Font(name="Arial", size=12)

    groups: dict[str, list[dict]] = defaultdict(list)
    for entry in entries:
        groups[str(entry.get("object_name") or "Без объекта")].append(entry)

    for object_name, group in groups.items():
        sheet = workbook.copy_worksheet(template_sheet)
        sheet.title = object_name[:31]

        sheet["A4"] = f"Объект: {object_name}"
        sheet["A5"] = f"Дата подачи заявки: {datetime.today().strftime('%d.%m.%y')}г."

        total = 0.0
        for idx, item in enumerate(group, start=1):
            row = START_ROW + idx - 1
            sheet[f"A{row}"] = idx
            sheet[f"B{row}"] = item.get("payment_number") or ""
            sheet[f"C{row}"] = item.get("status") or ""
            sheet[f"D{row}"] = item.get("counteragent") or ""
            sheet[f"E{row}"] = float(item.get("payment_sum") or 0)
            sheet[f"F{row}"] = item.get("TRU") or ""
            sheet[f"G{row}"] = item.get("object_name") or ""
            total += float(item.get("payment_sum") or 0)
            format_row(sheet, row, DATA_COLS, height=75)

        total_row = START_ROW + len(group)
        sheet[f"D{total_row}"] = "ВСЕГО"
        sheet[f"E{total_row}"] = total
        sheet[f"B{total_row + 2}"] = "Начальник ПТО"
        sheet[f"D{total_row + 2}"] = "___________________   Королькова Е. В."
        sheet[f"B{total_row + 4}"] = "Исполнительный директор"
        sheet[f"D{total_row + 4}"] = "___________________   Сергачев П.А."
        for ref in (f"D{total_row}", f"E{total_row}", f"B{total_row + 2}",
                    f"D{total_row + 2}", f"B{total_row + 4}", f"D{total_row + 4}"):
            sheet[ref].font = font

    workbook.remove(template_sheet)
    for name in workbook.sheetnames:
        set_print_area(workbook[name], anchor_col="B", anchor_col_index=2, area="A1:I{row}")
        add_colontituls(workbook[name])
    return workbook
