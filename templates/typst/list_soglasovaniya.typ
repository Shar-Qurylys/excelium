// Печатная форма карточки договора

#let data = json(sys.inputs.data)

// --- Вспомогательные функции обработки данных ---
#let get-field(dict, key, default: "") = {
  if dict != none and type(dict) == dictionary and key in dict {
    dict.at(key)
  } else {
    default
  }
}

#let format-number(val) = {
  if type(val) == int or type(val) == float {
    let s = str(val)
    let out = ""
    let count = 0
    for i in range(s.len() - 1, -1, step: -1) {
      if count > 0 and calc.rem(count, 3) == 0 {
        out = " " + out
      }
      out = s.at(i) + out
      count += 1
    }
    out
  } else {
    str(val)
  }
}

#let parse-date(d-str) = {
  if d-str == none or d-str == "" { return "" }
  if d-str.contains("T") {
    let parts = d-str.split("T")
    let d = parts.at(0)
    let t = parts.at(1).slice(0, 5)
    d + " " + t
  } else {
    d-str
  }
}

// --- Извлечение ключевых значений ---
#let org-name = {
  let org = data.at("organization", default: none)
  if org != none and type(org) == dictionary {
    org.at("name", default: "")
  } else {
    data.at("org", default: (:)).at("name", default: data.at("storona_gk", default: ""))
  }
}

#let org-bin = {
  let org = data.at("organization", default: none)
  if org != none and type(org) == dictionary {
    org.at("bin", default: "")
  } else {
    data.at("org", default: (:)).at("bin", default: "")
  }
}

#let sum-text = {
  let s = data.at("sum", default: none)
  if type(s) == dictionary {
    let amt = format-number(s.at("sum", default: 0))
    let curr = s.at("currency", default: "KZT")
    let vat = s.at("vat", default: "")
    (amt, curr, vat).filter(x => str(x) != "").join(" ")
  } else if s != none {
    let curr = data.at("currency", default: "")
    let vat = data.at("vat", default: "")
    (str(s), curr, vat).filter(x => str(x) != "").join(" ")
  } else {
    ""
  }
}

#let avans-text = {
  let p = data.at("pre_payment", default: none)
  if p != none {
    let curr = if type(data.at("sum", default: none)) == dictionary {
      data.sum.at("currency", default: "KZT")
    } else {
      data.at("currency", default: "KZT")
    }
    format-number(p) + " " + curr
  } else {
    let a = data.at("avans", default: "")
    if a != "" { a + " " + data.at("currency", default: "") } else { "" }
  }
}

#let srok-text = {
  let w = data.at("work_due", default: "")
  if w != "" {
    w
  } else {
    let s = data.at("srok", default: "")
    let u = data.at("srok_unit", default: "")
    (s, u).filter(x => x != "").join(" ")
  }
}

#let notes-text = {
  let n = data.at("special_conditions", default: "")
  if n != "" { n } else { data.at("notes", default: "") }
}

// --- Настройки страницы и стилей ---
#set page(
  paper: "a4",
  margin: (x: 1.5cm, top: 1.5cm, bottom: 1.8cm),
  footer: [
    #align(right)[
      #text(size: 8pt, fill: rgb("#64748B"))[Стр. #counter(page).display()]
    ]
  ]
)
#set text(font: ("Liberation Sans", "DejaVu Sans", "Arial"), size: 9.5pt, fill: rgb("#1E293B"), lang: "ru")

#let primary-color = rgb("#0F172A")
#let border-color = rgb("#CBD5E1")
#let bg-light = rgb("#F8FAFC")
#let success-color = rgb("#166534")
#let success-bg = rgb("#DCFCE7")

// ---- ШАПКА ДОКУМЕНТА ----
#block(
  width: 100%,
  stroke: (bottom: 1.5pt + primary-color),
  inset: (bottom: 8pt),
  [
    #grid(
      columns: (1fr, auto),
      align: (left + horizon, right + horizon),
      [
        #if org-name != "" [
          #text(size: 11pt, weight: "bold", fill: primary-color)[#org-name] \
        ]
        #if org-bin != "" [
          #text(size: 8.5pt, fill: rgb("#64748B"))[БИН #org-bin]
        ]
      ],
      [
        #text(size: 8pt, fill: rgb("#64748B"))[Система электронного документооборота]
      ]
    )
  ]
)

#v(10pt)

#align(center)[
  #text(size: 13pt, weight: "bold", fill: primary-color)[ЛИСТ СОГЛАСОВАНИЯ ДОКУМЕНТА]
]

#v(10pt)

// ---- РЕКВИЗИТЫ ДОКУМЕНТА ----
#let doc-number = data.at("document_number", default: "")
#let doc-date = data.at("document_date", default: "")
#let doc-title = {
  if doc-number != "" and doc-date != "" [№ #doc-number (#doc-date)]
  else if doc-number != "" [№ #doc-number]
  else [#doc-date]
}

#let attr-row(label, value) = {
  if value != none and str(value).trim() != "" {
    (
      table.cell(fill: bg-light, align: left + horizon)[#text(weight: "bold")[#label]],
      table.cell(align: left + horizon)[#value]
    )
  } else {
    ()
  }
}

#let attr-cells = (
  attr-row("Документ:", doc-title) +
  attr-row("Предмет договора:", data.at("subject", default: "")) +
  attr-row("Инициатор:", data.at("initiator", default: "")) +
  attr-row("Подразделение:", data.at("department", default: "")) +
  attr-row("Контрагент:", data.at("counteragent", default: "")) +
  attr-row("Наименование объекта:", data.at("object", default: "")) +
  attr-row("Сумма договора:", sum-text) +
  attr-row("Предоплата / Аванс:", avans-text) +
  attr-row("Срок выполнения:", srok-text) +
  attr-row("Ответственный юрист:", data.at("lawyer", default: "")) +
  attr-row("Особые условия:", notes-text)
)

#if attr-cells.len() > 0 {
  table(
    columns: (3.8cm, 1fr),
    stroke: 0.5pt + border-color,
    inset: 6pt,
    ..attr-cells.flatten()
  )
}

#v(12pt)

// ---- ХОД СОГЛАСОВАНИЯ ----
#text(size: 11pt, weight: "bold", fill: primary-color)[Ход согласования и решения]
#v(6pt)

#let raw-rows = if "approved_by" in data { data.approved_by } else { data.at("rows", default: ()) }

#if raw-rows.len() > 0 {
  table(
    columns: (0.8cm, 1.2fr, 1.5fr, 1fr, 1.2fr, 1.5fr),
    stroke: 0.5pt + border-color,
    inset: 5.5pt,
    fill: (col, row) => if row == 0 { bg-light } else { none },
    align: (col, row) => {
      if row == 0 { center + horizon }
      else if col == 0 or col == 3 { center + horizon }
      else { left + horizon }
    },
    table.header(
      [*№*], [*Этап / Идентификатор*], [*Исполнитель*], [*Решение*], [*Дата и время*], [*Комментарий*]
    ),
    ..for (idx, item) in raw-rows.enumerate() {
      let is-tuple = type(item) == array
      
      let step = if is-tuple { item.at(0, default: str(idx + 1)) } else { str(idx + 1) }
      let user-info = if is-tuple { item.at(3, default: "") } else { item.at("fio", default: "") }
      let pos-info = if is-tuple { "" } else { item.at("position", default: "") }
      let is-approved = if is-tuple { item.at(1, default: "1") == "1" } else { item.at("decision", default: "") == "Согласовано" }
      let decision-text = if is-approved { "Согласовано" } else if is-tuple { "Отклонено" } else { item.at("decision", default: "-") }
      let dt = if is-tuple { parse-date(item.at(4, default: "")) } else { item.at("date", default: "") }
      let comment = if is-tuple { item.at(5, default: "") } else { item.at("comment", default: "") }

      (
        [#(idx + 1)],
        [Этап #step],
        [
          #if pos-info != "" [#text(size: 8pt, fill: rgb("#64748B"))[#pos-info] \ ]
          #user-info
        ],
        [
          #if is-approved [
            #box(
              fill: success-bg,
              inset: (x: 5pt, y: 3pt),
              radius: 3pt,
              outset: 0pt,
              text(fill: success-color, weight: "bold", size: 8.5pt)[#decision-text]
            )
          ] else [
            #decision-text
          ]
        ],
        [#dt],
        [#text(size: 8.5pt)[#comment]]
      )
    }.flatten()
  )
} else [
  #text(style: "italic", fill: rgb("#64748B"))[Информация о согласовании отсутствует.]
]

// ---- БЛОК ПРОВЕРКИ И ПОДЛИННОСТИ (ЭЦП / QR) ----
#v(1fr)

#block(
  width: 100%,
  stroke: 0.8pt + primary-color,
  inset: 8pt,
  radius: 2pt,
  fill: rgb("#FAFAFA"),
  [
    #grid(
      columns: if data.at("qr", default: "") != "" or "approved_by" in data { (2.2cm, 1fr) } else { (1fr,) },
      column-gutter: 12pt,
      align: horizon,
      ..if data.at("qr", default: "") != "" or "approved_by" in data {
        (
          box(
            stroke: 0.5pt + border-color,
            inset: 2pt,
            fill: rgb("#FFFFFF"),
            image("qr.png", width: 2cm)
          ),
        )
      },
      [
        #text(size: 9pt, weight: "bold", fill: primary-color)[ДОКУМЕНТ ПОДПИСАН ЭЛЕКТРОННОЙ ЦИФРОВОЙ ПОДПИСЬЮ] \
        #v(2pt)
        #text(size: 8pt, fill: rgb("#475569"))[
          Штамп электронного согласования карточки документа #doc-title \
          Сформировано в СЭД | Организация: #org-name \
          Статус: Согласовано всеми участниками маршрута
        ]
      ]
    )
  ]
)