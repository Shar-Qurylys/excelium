// ЛИСТ СОГЛАСОВАНИЯ ДОКУМЕНТА — печатная форма по образцу карточки
// договора Doc-V.
//
// POST /render/typst/list_soglasovaniya. Пример данных:
// {
//   "org": {"name": "ТОО «Шар-Кұрылыс»", "bin": "000940001102",
//           "logo": "org_shar.png",                   // логотип — из «Картинок», можно опустить
//           "blank": "blank_shar.png",                // фирменный бланк подложкой всей страницы
//           "top_margin": 4.2},                       // отступ (см) под шапку бланка; низ 2.4 см
//   С "blank" текстовая шапка (название/БИН/логотип) не печатается —
//   бланк уже несёт её. PNG бланка делает операция blank_to_png.
//   "document_number": "12-СМР", "document_date": "01.08.2026",
//   "subject": "Строительно-монтажные работы ...",
//   "initiator": "Иванов И.И., инженер ПТО",
//   "counteragent": "ТОО «Подрядчик»",
//   "storona_gk": "ТОО «Шар-Кұрылыс»",
//   "object": "ЖК \"Grand Victoria 3\"",
//   "sum": "12 500 000,00", "currency": "KZT", "vat": "с НДС",
//   "avans": "3 000 000,00",
//   "srok": "120", "srok_unit": "календарных дней",
//   "notes": "Особые условия ...",
//   "rows": [{"position": "Главный бухгалтер", "company": "ТОО «Шар-Кұрылыс»",
//             "fio": "Абдрахманова Х.М.", "decision": "Согласовано",
//             "date": "25.08.2026 14:02", "comment": ""}],
//   "lawyer": "Бекмуратов Е.И.",
//   "qr": "{{ГИПЕРССЫЛКА НА ТЕКУЩИЙ ДОКУМЕНТ}}"      // шлюз сам построит qr.png
// }
// Пустые поля не печатаются. Блок подлинности (QR + код проверки +
// время формирования) шлюз добавляет сам через sys.inputs.meta.
#let data = json(sys.inputs.data)
#let meta = json(sys.inputs.meta)
#let org = data.at("org", default: (:))
#let blank = org.at("blank", default: "")

#set page(
  paper: "a4",
  margin: if blank != "" {
    (x: 1.7cm, top: org.at("top_margin", default: 4.2) * 1cm, bottom: 2.4cm)
  } else {
    (x: 1.6cm, top: 1.4cm, bottom: 1.6cm)
  },
  background: if blank != "" { image("assets/" + blank, width: 100%, height: 100%) },
)
#set text(font: ("Liberation Sans", "Arial", "DejaVu Sans"), size: 10pt, lang: "ru")

// ---- шапка организации (не печатается поверх бланка) ----------------------
#if blank == "" {
  let logo = org.at("logo", default: "")
  let name = org.at("name", default: "")
  let bin = org.at("bin", default: "")
  if name != "" or logo != "" {
    grid(
      columns: if logo != "" { (auto, 1fr) } else { (1fr,) },
      column-gutter: 1em,
      align: horizon,
      ..if logo != "" { (box(height: 1.6cm, image("assets/" + logo)),) },
      [
        #text(size: 12pt, weight: "bold")[#name] \
        #if bin != "" [ #text(size: 9pt, fill: gray)[БИН #bin] ]
      ],
    )
    v(0.4em)
    line(length: 100%, stroke: 0.8pt)
    v(0.8em)
  }
}

#align(center)[
  #text(size: 14pt, weight: "bold")[ЛИСТ СОГЛАСОВАНИЯ ДОКУМЕНТА]
]
#v(0.8em)

// ---- реквизиты документа --------------------------------------------------
#let val(..keys) = {
  // склейка непустых значений через пробел
  keys.pos().map(k => str(data.at(k, default: ""))).filter(x => x != "").join(" ")
}
#let rows = ()
#let add(label, value) = { if value != none and value != "" { ((label, value),) } else { () } }

#let doc_line = {
  let n = val("document_number")
  let d = val("document_date")
  if n != "" and d != "" [№ #n от #d] else if n != "" [№ #n] else [#d]
}

#grid(
  columns: (4.6cm, 1fr),
  column-gutter: 1em,
  row-gutter: 0.6em,
  ..(
    add([*Основной договор:*], doc_line)
    + add([*Предмет договора:*], val("subject"))
    + add([*Инициатор:*], val("initiator"))
    + add([*Контрагент:*], val("counteragent"))
    + add([*Сторона ГК:*], val("storona_gk"))
    + add([*Наименование объекта:*], val("object"))
    + add([*Сумма по договору:*], val("sum", "currency", "vat"))
    + add([*Порядок оплат, аванс:*], val("avans", "currency"))
    + add([*Срок выполнения работ:*], val("srok", "srok_unit"))
    + add([*Примечания:*], val("notes"))
  ).flatten().chunks(2).map(p => (p.at(0), [#p.at(1)])).flatten()
)

#v(1.2em)

// ---- решения --------------------------------------------------------------
#align(center)[
  #text(size: 12pt, weight: "bold")[Список согласований и исполнений по документу]
]
#v(0.5em)

#table(
  columns: (auto, 1.15fr, 0.95fr, 0.75fr, 2.1cm, 1.1fr),
  stroke: 0.5pt,
  inset: 6.5pt,
  align: (center + horizon, left + horizon, left + horizon,
          center + horizon, center + horizon, left + horizon),
  table.header(
    [*№*], [*Должность*], [*Ф.И.О.*], [*Решение*], [*Дата*], [*Комментарий*],
  ),
  ..for (i, r) in data.at("rows", default: ()).enumerate() {
    (
      [#(i + 1)],
      [#r.at("position", default: "")
       #if r.at("company", default: "") != "" [ \ #text(size: 8pt, fill: gray)[#r.at("company")] ]],
      [#r.at("fio", default: "")],
      [#r.at("decision", default: "")],
      [#r.at("date", default: "")],
      [#r.at("comment", default: "")],
    )
  }
)

#if val("lawyer") != "" {
  v(0.8em)
  [*Ответственный юрист:* #val("lawyer")]
}

// ---- блок подлинности -----------------------------------------------------
#v(1fr)
#line(length: 100%, stroke: (paint: gray, thickness: 0.5pt, dash: "dashed"))
#v(0.5em)
#grid(
  columns: if data.at("qr", default: "") != "" { (2.4cm, 1fr) } else { (1fr,) },
  column-gutter: 1em,
  align: horizon,
  ..if data.at("qr", default: "") != "" { (image("qr.png", width: 2.2cm),) },
  [
    #set text(size: 8.5pt, fill: gray)
    Документ сформирован из системы Doc-V #meta.at("generated_at", default: "")
    (время астанинское).
    #if data.at("qr", default: "") != "" [
      QR-код открывает документ в системе — сверьте состав согласований с карточкой. \
    ]
    #if meta.at("verify_code", default: "") != "" [
      Код подлинности: #text(font: ("SF Mono", "Consolas", "Liberation Mono"), weight: "bold")[#meta.verify_code] —
      при повторном формировании того же документа код совпадает;
      расхождение означает, что лист изменён вне системы.
    ]
  ],
)
