// Лист согласования: печатная форма к документу.
//
// POST /render/typst/list_soglasovaniya, данные:
// {
//   "document": "Договор №12-СМР от 01.08.2026",
//   "counteragent": "ТОО «Пример»",
//   "sum": "12 500 000,00 тг",
//   "initiator": "Иванов И.И., инженер ПТО",
//   "rows": [
//     {"position": "Главный бухгалтер", "company": "ТОО «Шар-Кұрылыс»",
//      "fio": "Абдрахманова Х.М.", "decision": "", "date": ""}
//   ]
// }
// Заполненные decision/date печатаются, пустые остаются для ручной подписи.
#let data = json(sys.inputs.data)

#set page(paper: "a4", margin: (x: 1.8cm, y: 1.6cm))
#set text(font: ("Liberation Sans", "Arial", "DejaVu Sans"), size: 10.5pt, lang: "ru")

#align(center)[
  #text(size: 14pt, weight: "bold")[ЛИСТ СОГЛАСОВАНИЯ]
]
#v(0.6em)

#grid(
  columns: (auto, 1fr),
  column-gutter: 1em,
  row-gutter: 0.55em,
  [*Документ:*],     [#data.at("document", default: "")],
  [*Контрагент:*],   [#data.at("counteragent", default: "")],
  [*Сумма:*],        [#data.at("sum", default: "")],
  [*Инициатор:*],    [#data.at("initiator", default: "")],
)

#v(1em)

#table(
  columns: (auto, 1.2fr, 1fr, 0.8fr, 2.2cm, 2cm),
  stroke: 0.5pt,
  inset: 7pt,
  align: (center, left, left, center, center, center),
  table.header(
    [*№*], [*Должность*], [*Ф.И.О.*], [*Решение*], [*Подпись*], [*Дата*],
  ),
  ..for (i, r) in data.at("rows", default: ()).enumerate() {
    (
      [#(i + 1)],
      [#r.at("position", default: "") \ #text(size: 8.5pt, fill: gray)[#r.at("company", default: "")]],
      [#r.at("fio", default: "")],
      [#r.at("decision", default: "")],
      [],
      [#r.at("date", default: "")],
    )
  }
)

#v(1.5em)
#text(size: 8.5pt, fill: gray)[
  Сформировано Doc-V Gateway #datetime.today().display("[day].[month].[year]")
]
