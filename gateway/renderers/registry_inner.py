"""Внутренний реестр платежей: группировка по паре компания+объект,
лист на каждую пару, блок подписантов из data/approvers.yaml.

Порт models/inner_registry.py. Отличия от оригинала:
- компания/вид затрат больше не гоняются через служебные ячейки H11/H12
  (данные передаются напрямую, ячейки и так затирались в конце);
- удалена formula_b — она вычислялась и никогда не записывалась,
  а её MATCH не совпадал с именами листа СПР_ОБЪЕКТОВ;
- пустой «Вид затрат» не роняет реестр (раньше .lower() на None).
"""
from collections import defaultdict
from datetime import datetime

import openpyxl
from openpyxl.styles import Alignment, Font

from .approvers import ApproverMatrix
from .common import (add_colontituls, create_concatenated_info, find_last_row_in_col,
                     format_row, hide_sheets, set_border, set_cell_properties,
                     set_print_area)

DATA_COLS = ["F", "G", "H", "I"]
START_ROW = 17

# Формулы подписей: ID строки листа СПР_ПОДПИСАНТОВ пишется в колонку B,
# Excel подставляет ФИО+должность (F) и компанию (I) сам.
FORMULA_F = ('=IFERROR(IF(ISNUMBER(VALUE(INDIRECT("B" & ROW()))), '
             'VLOOKUP(VALUE(INDIRECT("B" & ROW())), СПР_ПОДПИСАНТОВ!$B$14:$K$100, 9, 0) '
             '& " " & VLOOKUP(VALUE(INDIRECT("B" & ROW())), '
             'СПР_ПОДПИСАНТОВ!$B$14:$K$100, 7, 0), ""),"")')
FORMULA_I = ('=IFERROR(IF(ISNUMBER(VALUE(INDIRECT("B" & ROW()))), '
             'VLOOKUP(VALUE(INDIRECT("B" & ROW())), СПР_ПОДПИСАНТОВ!$B$14:$K$100, 5, 0), '
             '""),"")')
AGREED_MARK_ID = 3  # перед этим подписантом пишется строка «СОГЛАСОВАНО»


def render_inner(entries: list[dict], template_path, matrix: ApproverMatrix):
    workbook = openpyxl.load_workbook(template_path)

    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for item in entries:
        groups[(item.get("organization", ""), item.get("object_name", ""))].append(item)

    unique_companies = sorted({company for company, _ in groups})
    company_numbers = {c: i + 1 for i, c in enumerate(unique_companies)}

    template_sheet = workbook["REESTR"]
    for sub, ((company, object_name), group) in enumerate(groups.items(), start=1):
        title = f"C{company_numbers[company]}_{object_name}"[:31]
        sheet = workbook.copy_worksheet(template_sheet)
        sheet.title = title

        sheet["G11"] = object_name
        sheet["G10"] = datetime.today()
        sheet["F7"] = f"{group[0].get('registry_name', '')}/{sub}"

        row = START_ROW
        for entry in group:
            sheet[f"F{row}"] = (f"Заявитель: {entry.get('organization', '')}\n\n"
                                f"Кому: {entry.get('counteragent', '')}")
            sheet[f"G{row}"] = entry.get("zatraty") or ""
            sheet[f"H{row}"] = float(entry.get("payment_sum") or 0)
            sheet[f"I{row}"] = create_concatenated_info(entry)
            format_row(sheet, row, DATA_COLS, height=100, left_align=("F",))
            row += 1

        _add_signatures(sheet, matrix, company, object_name,
                        expense_type=str(group[0].get("zatraty") or ""))
        set_print_area(sheet, anchor_col="F", anchor_col_index=6, area="F1:I{row}")
        add_colontituls(sheet)

    workbook.remove(template_sheet)
    hide_sheets(workbook, ["СПР_ОБЪЕКТОВ", "СПР_ПОДПИСАНТОВ"])
    return workbook


def _add_signatures(sheet, matrix: ApproverMatrix, company: str, object_name: str,
                    *, expense_type: str) -> None:
    """Блок подписей под таблицей: директора в B2/B4 (их читают формулы
    шаблона), согласующие — строками ниже последней позиции."""
    directors, approvers = matrix.lookup(company, object_name)
    approvers = matrix.filter_for_expense_type(approvers, expense_type)

    final_row = find_last_row_in_col(sheet, 6) or START_ROW - 1

    left_bold = Alignment(horizontal="left")
    right_bold = Alignment(horizontal="right")
    bold14 = Font(size=14, bold=True)
    for i, approver_id in enumerate(approvers, start=1):
        row = final_row + i * 3
        if approver_id != AGREED_MARK_ID:
            set_cell_properties(sheet, row, 2, approver_id, set_border("thin"))
            set_cell_properties(sheet, row, 6, FORMULA_F, None, left_bold, bold14)
            set_cell_properties(sheet, row, 9, FORMULA_I, None, right_bold, bold14)
        else:
            set_cell_properties(sheet, row, 6, "СОГЛАСОВАНО", None, left_bold, Font(bold=False))
            set_cell_properties(sheet, row + 2, 2, AGREED_MARK_ID, set_border("thin"))
            set_cell_properties(sheet, row + 2, 6, FORMULA_F, None, left_bold, bold14)
            set_cell_properties(sheet, row + 2, 9, FORMULA_I, None, right_bold, bold14)

    sheet["B2"] = directors[0]
    sheet["B4"] = directors[1]
