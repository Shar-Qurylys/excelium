"""Операция translit: кириллица -> латиница, результат в stdout.

Казахский языковой пакет — порт utils/kazakh_translit.py (модуль лежал
в репозитории мёртвым, теперь работает как операция шлюза). Единственная
правка: «Yu» давал строчную «ю» — выровнен с остальными заглавными.
"""
import sys

from transliterate import translit
from transliterate.base import TranslitLanguagePack, registry


class KazakhLanguagePack(TranslitLanguagePack):
    language_code = "kz"
    language_name = "Kazakh"

    mapping = (
        "abvgdezijkqlmonprstufcC'y'hABVGDEZIJKQLMNOPRSTFU'Y'H",
        "абвгдезийкқлмонпрстуфцЦъыьһАБВГДЕЗИЙКҚЛМНОПРСТФУЪЫЬҺ",
    )

    reversed_specific_mapping = (  # буквы, повторяющиеся в двух языках
        "ёэЁЭәӘъьЪЬңҢғҒұүҰҮөӨіІ",
        "eeEEaA''''nNgGuuUUoOiI",
    )

    pre_processor_mapping = {
        "zh": "ж", "ts": "ц", "ch": "ч", "sh": "ш", "sch": "щ",
        "ju": "ю", "ja": "я", "yu": "ю", "ya": "я", "kh": "х",
        "Zh": "Ж", "Ts": "Ц", "Ch": "Ч", "Sh": "Ш", "Sch": "Щ",
        "Ju": "Ю", "Ja": "Я", "Yu": "Ю", "Ya": "Я", "Kh": "Х",
    }


registry.register(KazakhLanguagePack)
print(translit(sys.argv[1], "kz", reversed=True))
