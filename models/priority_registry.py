from utils.scripts import load_excel, set_cell_properties, format_row, set_border
from datetime import datetime
from openpyxl.styles import Alignment, Font
import logging
from datetime import datetime
from collections import defaultdict
from utils.scripts import (
    load_excel,
    format_row_priority_registry,
)
import logging

def fill_priority_registry(json_data):
    # 1) load workbook and get your template sheet by name
    workbook = load_excel('excel_templates/template_priority_registry.xlsx')
    tpl = workbook["REESTR"]    # ← make sure your xlsx has a sheet with exactly this name
    font = Font(name="Arial", size = 12)
    # 2) group entries by object_name
    entries = json_data.get('request', [])

    groups: dict[str, list] = defaultdict(list) 
    for entry in entries:
        obj = str(entry.get('object_name', 'Без объекта'))
        groups[obj].append(entry)

    # 3) for each object, copy+fill
    for object_name, entries in groups.items():
        sheet = workbook.copy_worksheet(tpl)
        sheet.title = object_name[:31]  # Excel max-length guard

        # header
        sheet["A4"] = f"Объект: {object_name}"
        sheet["A5"] = f"Дата подачи заявки: {datetime.today().strftime('%d.%m.%y')}г."

        # rows
        row_start = 7
        total = 0.0
        for idx, e in enumerate(entries, start=1):
            row = row_start + idx - 1
            sheet[f"A{row}"] = idx
            sheet[f"B{row}"] = e["payment_number"]
            sheet[f"C{row}"] = e["status"]
            sheet[f"D{row}"] = e["counteragent"]
            sheet[f"E{row}"] = float(e["payment_sum"])
            sheet[f"F{row}"] = e["TRU"]
            sheet[f"G{row}"] = e["object_name"]
            total += float(e["payment_sum"])
            format_row_priority_registry(sheet, row, ["A","B","C","D","E","F","G"])

        # total row + signatures
        total_row = row_start + len(entries)
        sheet[f"D{total_row}"] = "ВСЕГО"
        sheet[f"D{total_row}"].font = font
        sheet[f"E{total_row}"] = total
        sheet[f"E{total_row}"].font = font

        sheet[f"B{total_row + 2}"] = "Начальник ПТО"
        sheet[f"C{total_row + 2}"] = "___________________   Королькова Е. В."
        sheet[f"B{total_row + 4}"] = "Исполнительный директор"
        sheet[f"C{total_row + 4}"] = "___________________   Сергачев П.А."

        sheet[f"B{total_row + 2}"].font = font
        sheet[f"C{total_row + 2}"].font = font 
        sheet[f"B{total_row + 4}"].font = font 
        sheet[f"C{total_row + 4}"].font = font

    # 4) remove the original template so it doesn’t show up as an empty sheet
    workbook.remove(tpl)

    return workbook
