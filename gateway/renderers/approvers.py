"""Матрица подписантов реестра платежей (data/approvers.yaml).

Источник исторический — utils/firmen_und_objekte.py; идентификаторы
расшифровывает лист СПР_ПОДПИСАНТОВ шаблона template.xlsx (VLOOKUP).
Словари строятся один раз при загрузке. Неизвестная пара компания/объект
даёт реестр с пустыми блоками подписей — с warning в лог, а не молча.

Планируемая замена (веха M8): Doc-V присылает согласующих прямо в
payload, и этот модуль перестаёт быть нужным.
"""
import logging
from pathlib import Path

import yaml

log = logging.getLogger(__name__)

EMPTY = ([0, 0], [0] * 8)  # нули гасятся IFERROR в формулах шаблона


class ApproverMatrix:
    def __init__(self, path: Path):
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        lists = raw["approver_lists"]
        self._pairs: dict[tuple[str, str], tuple[list[int], list[int]]] = {}
        for rule in raw["rules"]:
            value = (rule["directors"], lists[rule["approvers"]])
            for obj in rule["objects"]:
                self._pairs[(rule["company"], obj)] = value
        self._fallbacks = {
            fb["company"]: (fb["directors"], lists[fb["approvers"]])
            for fb in raw.get("company_fallbacks", [])
        }
        excl = raw.get("expense_type_exclusions", {})
        self._excl_types = {t.lower() for t in excl.get("expense_types", [])}
        self._excl_ids = set(excl.get("remove_ids", []))

    def lookup(self, company: str, object_name: str) -> tuple[list[int], list[int]]:
        found = self._pairs.get((company, object_name))
        if found is None:
            found = self._fallbacks.get(company)
        if found is None:
            log.warning(
                "нет подписантов для пары компания/объект — реестр выйдет без подписей",
                extra={"data": {"company": company, "object": object_name}},
            )
            return EMPTY
        directors, approvers = found
        return list(directors), list(approvers)

    def filter_for_expense_type(self, approvers: list[int], expense_type: str) -> list[int]:
        """Для коммерческих расходов/зарплаты/налогов часть согласующих исключается."""
        if (expense_type or "").strip().lower() in self._excl_types:
            return [a for a in approvers if a not in self._excl_ids]
        return list(approvers)
