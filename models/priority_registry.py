from utils.scripts import load_excel, set_cell_properties, format_row, set_border
from datetime import datetime
from openpyxl.styles import Alignment, Font
import logging
from datetime import datetime
from collections import defaultdict
from utils.scripts import (
    load_excel,
    format_row,
)
import logging

def fill_priority_registry(json_data):
    # 1) load workbook and get your template sheet by name
    workbook = load_excel('excel_templates/template_priority_registry.xlsx')
    tpl = workbook["REESTR"]    # ← make sure your xlsx has a sheet with exactly this name

    # 2) group entries by object_name
    groups = defaultdict(list)
    for entry in json_data:
        obj = entry["object_name"]
        groups[obj].append(entry)

    # 3) for each object, copy+fill
    for object_name, entries in groups.items():
        sheet = workbook.copy_worksheet(tpl)
        sheet.title = object_name[:31]  # Excel max-length guard

        # header
        sheet["B4"] = f"Объект: {object_name}"
        sheet["B5"] = f"Дата подачи заявки: {datetime.today().strftime('%d.%m.%y')}г."

        # rows
        row_start = 7
        total = 0.0
        for idx, e in enumerate(entries, start=1):
            row = row_start + idx - 1
            sheet[f"A{row}"] = idx
            sheet[f"B{row}"] = e["payment_number"]
            sheet[f"C{row}"] = e["status"]
            sheet[f"D{row}"] = e["counteragent"]
            sheet[f"E{row}"] = float(e["sum"])
            sheet[f"F{row}"] = e["TRU"]
            sheet[f"G{row}"] = e["object_name"]
            total += float(e["sum"])
            format_row(sheet, row, ["A","B","C","D","E","F","G"])

        # total row + signatures
        total_row = row_start + len(entries)
        sheet[f"D{total_row}"] = "ВСЕГО"
        sheet[f"E{total_row}"] = total

        sheet[f"B{total_row + 2}"] = "Начальник ПТО"
        sheet[f"C{total_row + 2}"] = json_data.get("pto","")
        sheet[f"B{total_row + 4}"] = "Исполнительный директор:"
        sheet[f"C{total_row + 4}"] = json_data.get("director","")

    # 4) remove the original template so it doesn’t show up as an empty sheet
    workbook.remove(tpl)

    return workbook
