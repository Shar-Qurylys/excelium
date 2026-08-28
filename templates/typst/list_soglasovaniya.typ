// ЛИСТ СОГЛАСОВАНИЯ ДОКУМЕНТА — печатная форма.
//
// POST /render/typst/list_soglasovaniya. Контракт (собирается в Doc-V
// методом add_key; лишние ключи игнорируются, пустые не печатаются):
// {
//   "organization": {"name": "ТОО \"СМУ Аргон\"", "code": "СМ",
//                    "blank_file_name": "blank_sm.png"},  // бланк подложкой, можно ""
//   "document_number": "28/П/ДТ2",       // номер или unix-время (распознаётся)
//   "document_date": "20.08.2026",       // дата или название документа
//   "subject": "Раствор М200",
//   "counteragent": "ИП «SUNKAR»",
//   "object": "ЖК \"Dream Town\" 3-очередь",
//   "initiator": "Шелевий Ю.В. (Снабженец)",
//   "department": "Отдел материально-технического снабжения",
//   "lawyer": "Кожабаев Н.Р. (Юрист)",
//   "sum": {"sum": 5500000, "currency": "KZT", "vat": "с НДС"},
//   "pre_payment": 5500000,              // 0 = не печатается
//   "work_due": "50 дней",
//   "special_conditions": "",
//   "approved_by": [["этап","код визы","uid сотрудника","uid должности",
//                    "2026-08-20T14:48:47+05:00","комментарий","версия"], ...],
//   "rows": [{"fio","position","decision","date","comment"}],  // альтернатива approved_by
//   "qr": "адрес карточки"               // можно опустить
// }
// UID расшифровываются справочником шлюза (/directory/structura);
// коды визы, ISO-даты и unix-время приводятся к читаемому виду здесь.
#let data = if "data" in sys.inputs { json(sys.inputs.data) } else { (:) }
#let meta = if "meta" in sys.inputs { json(sys.inputs.meta) } else { (:) }
#let dir = if "dir" in sys.inputs { json(sys.inputs.dir) } else { (:) }

// ---- палитра и типографика ------------------------------------------------
#let accent = rgb("#0f766e")
#let ink = rgb("#1b2430")
#let muted = rgb("#6b7480")
#let hairline = rgb("#e2e6ea")
#let band = rgb("#f4f6f7")
#let ok-bg = rgb("#e7f3ec")
#let ok-fg = rgb("#186a3b")
#let no-bg = rgb("#fbe9e7")
#let no-fg = rgb("#a4342a")

#let org = data.at("organization", default: (:))
#let org = if type(org) == dictionary { org } else { ("name": str(org)) }
#let blank = str(org.at("blank_file_name", default: ""))

#set page(
  paper: "a4",
  margin: if blank != "" {
    (x: 1.9cm, top: org.at("top_margin", default: 4.2) * 1cm, bottom: 2.2cm)
  } else { (x: 1.9cm, top: 1.6cm, bottom: 1.8cm) },
  background: if blank != "" { image("assets/" + blank, width: 100%, height: 100%) },
  footer: context {
    set text(size: 7.5pt, fill: rgb("#6b7480"))
    let total = counter(page).final().at(0)
    let has-qr = data.at("qr", default: "") != ""
    grid(
      columns: if has-qr { (1.05cm, 1fr, auto) } else { (1fr, auto) },
      column-gutter: 8pt, align: horizon,
      ..if has-qr { (image("qr.png", width: 1cm),) },
      align(left)[
        Сформировано из системы Doc-V #meta.at("generated_at", default: "")
        #if meta.at("verify_code", default: "") != "" [
          · код подлинности #text(weight: "bold")[#meta.verify_code]]
        #if has-qr [ · QR открывает документ в системе]
      ],
      align(right)[#if total > 1 [стр. #counter(page).display() из #total]],
    )
  },
)
#set text(font: ("Liberation Sans", "Arial", "DejaVu Sans"), size: 9.5pt,
          lang: "ru", fill: ink)
#set par(justify: false)

// ---- вспомогательное ------------------------------------------------------
#let s(v) = if v == none { "" } else { str(v) }

#let fmtnum(n) = {
  if type(n) == int or type(n) == float {
    let parts = str(n).replace(".", ",").split(",")
    let g(x) = if x.len() <= 3 { x } else { g(x.slice(0, x.len() - 3)) + " " + x.slice(x.len() - 3) }
    g(parts.at(0)) + (if parts.len() > 1 { "," + parts.at(1) } else { "" })
  } else { s(n) }
}

// unix-время -> дд.мм.гггг (алгоритм civil-from-days)
#let from-unix(ts) = {
  let days = calc.floor((ts + 18000) / 86400)  // сдвиг на астанинское время
  let z = days + 719468
  let era = calc.floor(z / 146097)
  let doe = z - era * 146097
  let yoe = calc.floor((doe - calc.floor(doe / 1460) + calc.floor(doe / 36524)
                        - calc.floor(doe / 146096)) / 365)
  let y = yoe + era * 400
  let doy = doe - (365 * yoe + calc.floor(yoe / 4) - calc.floor(yoe / 100))
  let mp = calc.floor((5 * doy + 2) / 153)
  let d = doy - calc.floor((153 * mp + 2) / 5) + 1
  let m = mp + (if mp < 10 { 3 } else { -9 })
  let y = y + (if m <= 2 { 1 } else { 0 })
  let pad(x) = if x < 10 { "0" + str(x) } else { str(x) }
  pad(d) + "." + pad(m) + "." + str(y)
}

#let is-digits(t) = t.len() > 0 and t.split("").all(c => c == "" or "0123456789".contains(c))

// ISO / unix / как есть
#let fmtdate(v, with-time: true) = {
  let t = s(v)
  if t.len() >= 16 and t.slice(4, 5) == "-" {
    (t.slice(8, 10) + "." + t.slice(5, 7) + "." + t.slice(0, 4)
     + (if with-time { " " + t.slice(11, 16) } else { "" }))
  } else if is-digits(t) and t.len() >= 9 and t.len() <= 11 {
    from-unix(int(t))
  } else { t }
}

#let visa(code) = ("1": "Согласен", "-1": "Не согласен",
                   "2": "Подписан", "-2": "Не подписан").at(s(code), default: s(code))
#let visa-ok(code) = s(code) == "1" or s(code) == "2"

#let people = dir.at("structura", default: (:))
#let positions = dir.at("dolzhnosti", default: (:))
#let short(uid) = { let t = s(uid); if t.len() > 12 { t.slice(0, 8) + "…?" } else { t } }
#let person-name(uid) = people.at(s(uid), default: (:)).at("name", default: short(uid))
#let person-pos(uid-pos, uid-person) = {
  let p = positions.at(s(uid-pos), default: (:)).at("name", default: "")
  if p != "" { p } else {
    people.at(s(uid-person), default: (:)).at("position", default: short(uid-pos))
  }
}

// approved_by (сырая таблица) или rows (готовые объекты) -> единый список
#let rows = {
  let out = ()
  let ab = data.at("approved_by", default: ())
  let nested = (ab.len() > 0 and type(ab.at(0)) == array and ab.at(0).len() > 0
                and type(ab.at(0).at(0)) == array)
  let flat = if nested { ab.at(0) } else { ab }
  for r in flat {
    if type(r) == array and r.len() >= 5 {
      out.push((stage: s(r.at(0)), fio: person-name(r.at(2)),
                position: person-pos(r.at(3), r.at(2)), code: s(r.at(1)),
                decision: visa(r.at(1)), ok: visa-ok(r.at(1)),
                date: fmtdate(r.at(4)), raw-date: s(r.at(4)),
                comment: if r.len() > 5 { s(r.at(5)) } else { "" }))
    }
  }
  for r in data.at("rows", default: ()) {
    out.push((stage: s(r.at("stage", default: "")), fio: s(r.at("fio", default: "")),
              position: s(r.at("position", default: "")), code: "1",
              decision: s(r.at("decision", default: "")), ok: true,
              date: fmtdate(r.at("date", default: "")), raw-date: s(r.at("date", default: "")),
              comment: s(r.at("comment", default: ""))))
  }
  out
}

// ---- шапка организации ----------------------------------------------------
#if blank == "" and org.at("name", default: "") != "" {
  grid(columns: (1fr, auto), align: horizon,
    text(size: 11pt, weight: "bold")[#org.name],
    if org.at("code", default: "") != "" {
      box(fill: accent, radius: 3pt, inset: (x: 7pt, y: 3pt),
          text(fill: white, size: 8.5pt, weight: "bold")[#org.code])
    },
  )
  v(0.35em)
  line(length: 100%, stroke: 1.2pt + accent)
  v(1.1em)
}

// ---- заголовок ------------------------------------------------------------

// ---- документ ---------------------------------------------------------
#let doc-number = {
  let n = s(data.at("document_number", default: ""))
  let d = s(data.at("document_date", default: ""))
  // номер и дата местами перепутаны, если в номере лежит время
  if is-digits(n) and n.len() >= 9 and not is-digits(d) { d } else { n }
}
#let doc-date = {
  let n = s(data.at("document_number", default: ""))
  let d = s(data.at("document_date", default: ""))
  if is-digits(n) and n.len() >= 9 and not is-digits(d) { fmtdate(n, with-time: false) }
  else { fmtdate(d, with-time: false) }
}

#let sum-block = {
  let raw = data.at("sum", default: (:))
  let one(e) = (fmtnum(e.at("sum", default: "")), s(e.at("currency", default: "")),
                s(e.at("vat", default: ""))).filter(x => x != "").join(" ")
  if type(raw) == array { raw.map(one).join("; ") }
  else if type(raw) == dictionary { one(raw) }
  else { s(raw) }
}
#let avans-block = {
  let a = data.at("pre_payment", default: "")
  if a == "" or a == 0 or a == "0" { "" } else {
    let cur = {
      let raw = data.at("sum", default: (:))
      if type(raw) == dictionary { s(raw.at("currency", default: "")) }
      else if type(raw) == array and raw.len() > 0 { s(raw.at(0).at("currency", default: "")) }
      else { "" }
    }
    (fmtnum(a) + " " + cur).trim()
  }
}

// value — строка или готовый контент; пустое поле не печатается
#let field(label, value) = if value != none and value != "" and value != [] {
  (text(size: 8.5pt, fill: muted)[#label], [#value])
} else { () }

#align(center)[
  #text(size: 15pt, weight: "bold", tracking: 1.2pt)[ЛИСТ СОГЛАСОВАНИЯ]
  #if doc-number != "" or doc-date != "" [
    #v(0.25em)
    #text(size: 9.5pt, fill: muted)[#doc-number #if doc-date != "" [от #doc-date]]
  ]
]
#v(0.9em)

#block(fill: band, radius: 4pt, inset: (x: 12pt, y: 10pt), width: 100%)[
  #grid(columns: (auto, 1fr), column-gutter: 12pt, row-gutter: 5.5pt,
    ..(
      field("Предмет", data.at("subject", default: ""))
      + field("Контрагент", data.at("counteragent", default: ""))
      + field("Объект", data.at("object", default: ""))
      + field("Сторона ГК", org.at("name", default: ""))
      + field("Инициатор", data.at("initiator", default: ""))
      + field("Отдел", data.at("department", default: ""))
      + field("Срок", data.at("work_due", default: ""))
      + field("Особые условия", data.at("special_conditions", default: ""))
      + field("Юрист", data.at("lawyer", default: ""))
    ).flatten()
  )
]

#if sum-block != "" or avans-block != "" {
  v(0.7em)
  grid(columns: (1fr,) * (if avans-block != "" { 2 } else { 1 }), column-gutter: 10pt,
    ..((
      block(width: 100%, inset: (x: 12pt, y: 9pt), radius: 4pt,
            stroke: 0.7pt + hairline)[
        #text(size: 8.5pt, fill: muted)[Сумма по документу] \
        #text(size: 12.5pt, weight: "bold")[#sum-block]
      ],
    ) + if avans-block != "" {(
      block(width: 100%, inset: (x: 12pt, y: 9pt), radius: 4pt,
            stroke: 0.7pt + hairline)[
        #text(size: 8.5pt, fill: muted)[Аванс] \
        #text(size: 12.5pt, weight: "bold")[#avans-block]
      ],
    )} else { () })
  )
}

// ---- сводка по согласованиям ----------------------------------------------
#let ok-count = rows.filter(r => r.ok).len()
#let all-dates = rows.map(r => r.date).filter(d => d != "")
#if rows.len() > 0 {
  v(0.7em)
  block(width: 100%, fill: band, radius: 3pt, inset: (x: 10pt, y: 7pt))[
    #set text(size: 8.5pt, fill: muted)
    Решений: #text(fill: ink, weight: "bold")[#rows.len()],
    из них положительных: #text(fill: if ok-count == rows.len() { ok-fg } else { no-fg },
                                weight: "bold")[#ok-count].
    #if all-dates.len() > 1 [ Период: #all-dates.first() — #all-dates.last().]
  ]
}

// ---- согласования ---------------------------------------------------------
#v(1em)
#grid(columns: (auto, 1fr), align: horizon, column-gutter: 8pt,
  text(size: 11pt, weight: "bold")[Согласования по документу],
  line(length: 100%, stroke: 0.7pt + hairline),
)
#v(0.6em)

#let badge(r) = box(
  fill: if r.ok { ok-bg } else { no-bg }, radius: 2.5pt, inset: (x: 6pt, y: 2.5pt),
  text(size: 8pt, weight: "bold", fill: if r.ok { ok-fg } else { no-fg })[#r.decision])

#if rows.len() == 0 [
  #text(fill: muted)[Согласований пока нет.]
] else {
  // группировка по этапам маршрута
  let stages = ()
  for r in rows {
    if stages.len() > 0 and stages.last().at("stage") == r.stage {
      stages.last().rows.push(r)
    } else { stages.push((stage: r.stage, rows: (r,))) }
  }
  let cells = ()
  let idx = 0
  for (si, g) in stages.enumerate() {
    if g.stage != "" and stages.len() > 1 {
      cells.push(table.cell(colspan: 4, fill: white, align: left,
        inset: (left: 8pt, top: if si == 0 { 2pt } else { 8pt }, bottom: 3pt),
        text(size: 8pt, weight: "bold", fill: accent, tracking: 0.5pt)[ЭТАП #g.stage]))
    }
    for r in g.rows {
      idx += 1
      cells.push([#text(fill: muted)[#idx]])
      cells.push([#text(weight: "bold")[#r.fio] #if r.position != "" [
        \ #text(size: 8pt, fill: muted)[#r.position]]])
      cells.push(badge(r))
      cells.push(text(size: 8.5pt)[#r.date])
      if r.comment != "" {
        cells.push(table.cell(colspan: 4, align: left,
          inset: (left: 26pt, right: 8pt, top: 0pt, bottom: 6pt),
          text(size: 8pt, fill: muted, style: "italic")[#r.comment]))
      }
    }
  }
  table(
    columns: (auto, 1fr, auto, auto),
    stroke: (x, y) => (bottom: 0.5pt + hairline),
    inset: (x: 8pt, y: 4.5pt),
    align: (center + horizon, left + horizon, center + horizon, right + horizon),
    table.header(
      table.cell(inset: (x: 8pt, y: 5pt), text(size: 8pt, fill: muted)[№]),
      table.cell(inset: (x: 8pt, y: 5pt), text(size: 8pt, fill: muted)[Согласующий]),
      table.cell(inset: (x: 8pt, y: 5pt), text(size: 8pt, fill: muted)[Решение]),
      table.cell(inset: (x: 8pt, y: 5pt), text(size: 8pt, fill: muted)[Дата]),
    ),
    ..cells,
  )
}


