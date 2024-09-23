from transliterate import get_available_language_codes
from transliterate.discover import autodiscover
autodiscover()
from transliterate.base import TranslitLanguagePack, registry

class KazakhLanguagePack(TranslitLanguagePack):
    language_code = "kz"
    language_name = "Kazakh"

    mapping = (
        u"abvgdezijkqlmonprstufcC'y'hABVGDEZIJKQLMNOPRSTFU'Y'H",
        u"абвгдезийкқлмонпрстуфцЦъыьһАБВГДЕЗИЙКҚЛМНОПРСТФУЪЫЬҺ",
    )

    reversed_specific_mapping = ( # used for repeating letters in two languages
        u"ёэЁЭәӘъьЪЬңҢғҒұүҰҮөӨіІ",
        u"eeEEaA''''nNgGuuUUoOiI"
    )

    pre_processor_mapping = {
        u"zh": u"ж",
        u"ts": u"ц",
        u"ch": u"ч",
        u"sh": u"ш",
        u"sch": u"щ",
        u"ju": u"ю",
        u"ja": u"я",
        u"Zh": u"Ж",
        u"Ts": u"Ц",
        u"Ch": u"Ч",
        u"Kh": u"Х",
        u"kh": u"х",
        u"Sh": u"Ш",
        u"Sch": u"Щ",
        u"Ju": u"Ю",
        u"Ja": u"Я",
        u"yu": u"ю",
        u"ya": u"я",
        u"Yu": u"ю",
        u"Ya": u"Я",
    }

registry.register(KazakhLanguagePack)

# from transliterate import translit
# text = "ТОО Қар қар Сән сән Әң әң әңгіме дүкен Ғарышкер ғәріп Әріп Өңдеу өнді һайуан Роза Нанның ізі Үш үй ұн Ұнамайды»"

# text2 = translit(text, "kz", reversed = True)
# text3 = translit('Yan', "kz")

# print(text2)
# print('\n')
# print(text3)
