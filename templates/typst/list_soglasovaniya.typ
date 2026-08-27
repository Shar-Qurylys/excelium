// ЛИСТ СОГЛАСОВАНИЯ ДОКУМЕНТА — печатная форма по образцу карточки
// договора Doc-V.
//
// POST /render/typst/list_soglasovaniya. Контракт (собирается в Doc-V
// методом add_key, лишние ключи игнорируются, пустые не печатаются):
// {
//   "organization": "ТОО «Шар-Кұрылыс»",        // сторона ГК
//   "document_number": "0099/test/adm",
//   "document_date": "25.08.2026",              // строкой, как на карточке
//   "subject": "Обучение БИОТ",
//   "initiator": "Фамилия Имя (должность)",
//   "department": "Отдел по управлению персоналом",
//   "counteragent": "ТОО «Test»",
//   "object": "Администрация",
//   "sum": [{"sum": 144000, "currency": "KZT", "vat": "с НДС"}],
//   "pre_payment": 0,                            // 0 = строка не печатается
//   "work_due": "Обучение БИОТ",
//   "special_conditions": "",
//   "lawyer": "",
//   "rows": [{"fio": "...", "position": "...", "decision": "Согласен",
//             "date": "...", "comment": "..."}],
//   "org": {"name": "...", "bin": "...", "logo": "...",   // шапка бланка,
//           "blank": "blank_shar.png", "top_margin": 4.2}, // можно опустить
//   "qr": "адрес карточки"                       // можно опустить
// }
// Пустые поля не печатаются. Блок подлинности (QR + код проверки +
// время формирования) шлюз добавляет сам через sys.inputs.meta.
// Оба входа опциональны: шаблон компилируется и вручную, без --input
#let data = if "data" in sys.inputs { json(sys.inputs.data) } else { (:) }
#let meta = if "meta" in sys.inputs { json(sys.inputs.meta) } else { (:) }
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
  // склейка непустых значений через пробел (join пустого массива даёт none)
  let joined = keys.pos().map(k => str(data.at(k, default: ""))).filter(x => x != "").join(" ")
  if joined == none { "" } else { joined }
}
#let rows = ()
#let add(label, value) = { if value != none and value != "" { ((label, value),) } else { () } }

#let doc_line = {
  let n = val("document_number")
  let d = val("document_date")
  if n != "" and d != "" [№ #n от #d] else if n != "" [№ #n] else [#d]
}

// число -> "144 000" / "144 000,50"
#let fmtnum(n) = {
  if type(n) == int or type(n) == float {
    let s = str(n).replace(".", ",")
    let parts = s.split(",")
    let int-part = parts.at(0)
    let group(x) = if x.len() <= 3 { x } else {
      group(x.slice(0, x.len() - 3)) + " " + x.slice(x.len() - 3) }
    group(int-part) + (if parts.len() > 1 { "," + parts.at(1) } else { "" })
  } else { str(n) }
}

// [{"sum": 144000, "currency": "KZT", "vat": "с НДС"}] -> "144 000 KZT с НДС"
#let sum_line = {
  let raw = data.at("sum", default: ())
  if type(raw) == array {
    raw.map(e => (fmtnum(e.at("sum", default: "")), str(e.at("currency", default: "")),
                  str(e.at("vat", default: ""))).filter(x => x != "").join(" "))
       .join("; ")
  } else { str(raw) }
}

#let avans_line = {
  let a = data.at("pre_payment", default: "")
  if a == "" or a == 0 or a == "0" { "" } else {
    let cur = if type(data.at("sum", default: ())) == array and data.sum.len() > 0 {
      str(data.sum.at(0).at("currency", default: "")) } else { "" }
    (fmtnum(a) + " " + cur).trim()
  }
}

#grid(
  columns: (4.6cm, 1fr),
  column-gutter: 1em,
  row-gutter: 0.6em,
  ..(
    add([*Основной договор:*], doc_line)
    + add([*Предмет договора:*], val("subject"))
    + add([*Инициатор:*], val("initiator"))
    + add([*Отдел:*], val("department"))
    + add([*Контрагент:*], val("counteragent"))
    + add([*Сторона ГК:*], val("organization"))
    + add([*Наименование объекта:*], val("object"))
    + add([*Сумма по договору:*], sum_line)
    + add([*Порядок оплат, аванс:*], avans_line)
    + add([*Срок/предмет работ:*], val("work_due"))
    + add([*Примечания:*], val("special_conditions"))
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
