// Образец Typst-шаблона для шлюза.
//
// Данные приходят из тела POST /render/typst/primer и доступны как
// обычный JSON-объект. Скопируйте файл под новым именем — новое имя
// сразу станет адресом /render/typst/<имя>.
#let data = if "data" in sys.inputs { json(sys.inputs.data) } else { (:) }

#set page(paper: "a4", margin: 2cm)
#set text(font: ("Liberation Sans", "Arial", "DejaVu Sans"), size: 11pt, lang: "ru")

#align(center)[
  #text(size: 14pt, weight: "bold")[#data.at("title", default: "Документ")]
]

#v(1em)

#table(
  columns: (1fr, 2fr),
  stroke: 0.5pt,
  ..for (key, value) in data.at("fields", default: (:)) {
    ([#key], [#value])
  }
)

#v(2em)
#text(size: 9pt, fill: gray)[Сформировано Doc-V Gateway]
