// ДОГОВОР — печатная форма. Вёрстка здесь, юридический текст — из Doc-V
// (типовые формы), поэтому один шаблон обслуживает любой вид договора.
//
// POST /render/typst/dogovor. Контракт данных:
// {
//   "title": "ДОГОВОР ПОСТАВКИ",
//   "number": "28/П/ДТ2", "date": "20.08.2026", "city": "г. Астана",
//   "preamble": "ТОО «СМУ Аргон», именуемое в дальнейшем «Покупатель», в лице
//                директора Акшалова Т.М., действующего на основании Устава, ...",
//   "sections": [                       // тело договора, по разделам
//     {"title": "1. Предмет договора", "text": "1.1. Поставщик обязуется...\n1.2. ..."}
//   ],
//   "spec": {                           // спецификация таблицей; можно опустить
//     "title": "Спецификация",
//     "columns": ["№", "Наименование", "Ед.", "Кол-во", "Цена", "Сумма"],
//     "rows": [["1", "Раствор М200", "м³", "200", "27 500", "5 500 000"]],
//     "total": "Итого: 5 500 000,00 KZT с НДС"
//   },
//   "parties": [                        // реквизиты и подписи, обычно две стороны
//     {"role": "Поставщик", "name": "ИП «SUNKAR»", "bin": "123456789012",
//      "address": "г. Астана, ул. ...", "iik": "KZ12...", "bik": "KCJBKZKX",
//      "bank": "Банк ЦентрКредит", "fio": "Иванов И.И.", "position": "Директор"},
//     {"role": "Покупатель", "name": "ТОО «СМУ Аргон»", ...}
//   ],
//   "qr": "адрес карточки"              // блок подлинности; можно опустить
// }
// Переносы строк в text становятся абзацами. Пустые ключи не печатаются.
#let data = if "data" in sys.inputs { json(sys.inputs.data) } else { (:) }
#let meta = if "meta" in sys.inputs { json(sys.inputs.meta) } else { (:) }
#let dir = if "dir" in sys.inputs { json(sys.inputs.dir) } else { (:) }

#let val(k) = str(data.at(k, default: ""))
#let number = val("number")
#let date = val("date")

#set page(
  paper: "a4", margin: (x: 2cm, top: 1.8cm, bottom: 2.2cm),
  footer: context [
    #set text(size: 8.5pt, fill: gray)
    #grid(columns: (1fr, auto),
      [Договор #if number != "" [№ #number] #if date != "" [от #date]],
      [стр. #counter(page).display() из #counter(page).final().at(0)])
  ],
)
#set text(font: ("Times New Roman", "Liberation Serif", "DejaVu Serif"),
          size: 11pt, lang: "ru", hyphenate: true)
#set par(justify: true, leading: 0.6em, first-line-indent: (amount: 1.25cm, all: true))

// ---- шапка ----------------------------------------------------------------
#align(center)[
  #text(weight: "bold", size: 13pt)[#data.at("title", default: "ДОГОВОР")
    #if number != "" [ № #number]]
]
#v(0.4em)
#grid(columns: (1fr, 1fr),
  align(left)[#val("city")],
  align(right)[#if date != "" [«#date»]],
)
#v(0.8em)

// ---- преамбула и тело -----------------------------------------------------
#let paragraphs(t) = for line in str(t).split("\n") {
  let line = line.trim()
  if line != "" { par[#line] }
}

#if val("preamble") != "" { paragraphs(data.preamble); v(0.6em) }

#for section in data.at("sections", default: ()) {
  align(center)[#text(weight: "bold")[#section.at("title", default: "")]]
  v(0.3em)
  paragraphs(section.at("text", default: ""))
  v(0.6em)
}

// ---- спецификация ---------------------------------------------------------
#let spec = data.at("spec", default: (:))
#if spec.at("rows", default: ()).len() > 0 {
  align(center)[#text(weight: "bold")[#spec.at("title", default: "Спецификация")]]
  v(0.4em)
  let cols = spec.at("columns", default: ())
  let n = if cols.len() > 0 { cols.len() } else { spec.rows.at(0).len() }
  set par(first-line-indent: 0cm)
  table(
    columns: (auto,) + (1fr,) * (n - 1),
    stroke: 0.5pt, inset: 6pt,
    ..if cols.len() > 0 { cols.map(c => [*#c*]) },
    ..for row in spec.rows { row.map(c => [#str(c)]) },
  )
  if spec.at("total", default: "") != "" {
    align(right)[#text(weight: "bold")[#spec.total]]
  }
  v(0.6em)
}

// ---- реквизиты и подписи сторон -------------------------------------------
#let parties = data.at("parties", default: ())
#if parties.len() > 0 {
  v(0.8em)
  align(center)[#text(weight: "bold")[Юридические адреса, реквизиты и подписи сторон]]
  v(0.6em)
  set par(first-line-indent: 0cm, justify: false)
  let card(p) = [
    #text(weight: "bold")[#p.at("role", default: "")] \
    #text(weight: "bold")[#p.at("name", default: "")] \
    #for (label, key) in (("БИН/ИИН", "bin"), ("Адрес", "address"), ("ИИК", "iik"),
                          ("БИК", "bik"), ("Банк", "bank")) {
      let v = str(p.at(key, default: ""))
      if v != "" [#label: #v \ ]
    }
    #v(1.6em)
    #p.at("position", default: "") \
    ________________________ #p.at("fio", default: "") \
    #v(0.2em)
    #text(size: 9pt, fill: gray)[М.П.]
  ]
  grid(columns: (1fr,) * calc.min(parties.len(), 2), column-gutter: 1.2cm,
       row-gutter: 1.2em, ..parties.map(card))
}

// ---- блок подлинности -----------------------------------------------------
#v(1fr)
#line(length: 100%, stroke: (paint: gray, thickness: 0.5pt, dash: "dashed"))
#v(0.4em)
#grid(
  columns: if data.at("qr", default: "") != "" { (2.2cm, 1fr) } else { (1fr,) },
  column-gutter: 1em, align: horizon,
  ..if data.at("qr", default: "") != "" { (image("qr.png", width: 2cm),) },
  [
    #set text(size: 8pt, fill: gray)
    #set par(first-line-indent: 0cm)
    Сформировано из системы Doc-V #meta.at("generated_at", default: "") (время астанинское).
    #if meta.at("verify_code", default: "") != "" [
      Код подлинности: #text(weight: "bold")[#meta.verify_code].
    ]
  ],
)
