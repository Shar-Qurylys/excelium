// КАРТОЧКА ДОГОВОРА (лист согласования).
//
// Оформление — по дизайн-системе «Приёмка ERP SHARK»: шалфейная
// палитра, надзаголовок вразрядку, нумерованные разделы, плашки-теги,
// моноширинные числа и даты.
//
// POST /render/typst/contract_card (или GET с ?data=…, тогда ответ —
// сам PDF, см. deploy/README-docv.md). Контракт:
// {
//   "organization": {"name": "ТОО \"СМУ Аргон\"", "code": "СМ",
//                    "blank_filepath": "blank_sm.png",  // или blank_file_name;
//                    "top_margin": 4.2},                // путь режется до имени файла
//   "document_number": "28/П/ДТ2",     // номер либо unix-время (распознаётся)
//   "document_date": "20.08.2026",     // дата либо название документа
//   "subject", "counteragent", "object", "initiator", "department",
//   "lawyer", "work_due", "special_conditions": "строки",
//   "sum": {"sum": 5500000, "currency": "KZT", "vat": "с НДС"},
//   "pre_payment": 5500000,            // 0 не печатается
//   "approved_by": [["№","код визы","uid сотрудника","uid должности",
//                    "2026-08-20T14:48:47+05:00","комментарий","версия"], ...],
//   "rows": [{"fio","position","decision","date","comment"}],  // альтернатива
//   "stage_label": "ЭТАП"              // подпись групп; "" — не группировать
// }
// Коды визы (из справочника поля «Виза»): 1 — Согласен, -1 — Не согласен,
// 2 — Подписан, -2 — Не подписан; незнакомый код печатается как есть.
// UID сотрудников и должностей расшифровывает справочник шлюза
// (/directory/structura, /directory/dolzhnosti).
#let data = if "data" in sys.inputs { json(sys.inputs.data) } else { (:) }
#let meta = if "meta" in sys.inputs { json(sys.inputs.meta) } else { (:) }
#let dir = if "dir" in sys.inputs { json(sys.inputs.dir) } else { (:) }

// ---- токены дизайн-системы ------------------------------------------------
#let paper = rgb("#F4F6F3")
#let surface = rgb("#FFFFFF")
#let surface-2 = rgb("#EBEEE9")
#let ink = rgb("#141A17")
#let ink-2 = rgb("#454F49")
#let ink-3 = rgb("#6E7973")
#let rule = rgb("#D6DCD6")
#let rule-2 = rgb("#C2CBC2")
#let accent = rgb("#2C5545")
#let pass = rgb("#3B7F58")
#let pass-bg = rgb("#E4EFE7")
#let block-c = rgb("#A0361D")
#let block-bg = rgb("#F7E7E2")
#let warn = rgb("#8A6212")
#let warn-bg = rgb("#F6EEDA")

#let sans = ("Liberation Sans", "Arial", "DejaVu Sans")
#let mono = ("Liberation Mono", "SF Mono", "Consolas", "DejaVu Sans Mono")

// ---- организация и бланк --------------------------------------------------
#let org = {
  let o = data.at("organization", default: (:))
  if type(o) == dictionary { o } else { ("name": str(o)) }
}
#let blank = {
  // принимаем и blank_filepath, и blank_file_name; путь режем до имени файла
  let raw = ""
  for key in ("blank_filepath", "blank_file_name", "blank") {
    if raw == "" { raw = str(org.at(key, default: "")) }
  }
  if raw == "" { "" } else { raw.split("/").last().split("\\").last() }
}

#set page(
  paper: "a4",
  margin: if blank != "" {
    (x: 1.8cm, top: org.at("top_margin", default: 4.2) * 1cm, bottom: 2.1cm)
  } else { (x: 1.8cm, top: 1.5cm, bottom: 1.9cm) },
  background: if blank != "" { image("assets/" + blank, width: 100%, height: 100%) },
  footer: context {
    set text(size: 7.5pt, fill: ink-3)
    let total = counter(page).final().at(0)
    grid(columns: (1fr, auto), column-gutter: 8pt, align: horizon,
      align(left)[
        Doc-V · #meta.at("generated_at", default: "")
        #if meta.at("verify_code", default: "") != "" [
          · код подлинности #text(font: mono, weight: "bold")[#meta.verify_code]]
      ],
      align(right)[#if total > 1 [
        #text(font: mono)[#counter(page).display() / #total]]],
    )
  },
)
#set text(font: sans, size: 9.5pt, lang: "ru", fill: ink)
#set par(justify: false, leading: 0.62em)

// ---- вспомогательное ------------------------------------------------------
#let s(v) = if v == none { "" } else { str(v) }

#let fmtnum(n) = {
  if type(n) == int or type(n) == float {
    let parts = str(n).replace(".", ",").split(",")
    let g(x) = if x.len() <= 3 { x } else { g(x.slice(0, x.len() - 3)) + " " + x.slice(x.len() - 3) }
    g(parts.at(0)) + (if parts.len() > 1 { "," + parts.at(1) } else { "" })
  } else { s(n) }
}

// unix-время -> дд.мм.гггг (civil-from-days, сдвиг на астанинское время)
#let from-unix(ts) = {
  let days = calc.floor((ts + 18000) / 86400)
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
#let fmtdate(v, with-time: true) = {
  let t = s(v)
  if t.len() >= 16 and t.slice(4, 5) == "-" {
    (t.slice(8, 10) + "." + t.slice(5, 7) + "." + t.slice(0, 4)
     + (if with-time { " " + t.slice(11, 16) } else { "" }))
  } else if is-digits(t) and t.len() >= 9 and t.len() <= 11 {
    from-unix(int(t))
  } else { t }
}

// коды поля «Виза» -> подпись и вид плашки
#let visa-map = (
  "1": ("Согласен", pass, pass-bg),
  "2": ("Подписан", accent, surface-2),
  "-1": ("Не согласен", block-c, block-bg),
  "-2": ("Не подписан", warn, warn-bg),
)
#let visa(code) = visa-map.at(s(code), default: (s(code), ink-2, surface-2))

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
#let person-dep(uid-person) = people.at(s(uid-person), default: (:)).at("department", default: "")

#let rows = {
  let out = ()
  let ab = data.at("approved_by", default: ())
  let nested = (ab.len() > 0 and type(ab.at(0)) == array and ab.at(0).len() > 0
                and type(ab.at(0).at(0)) == array)
  for r in (if nested { ab.at(0) } else { ab }) {
    if type(r) == array and r.len() >= 5 {
      let v = visa(r.at(1))
      out.push((group: s(r.at(0)), fio: person-name(r.at(2)),
                position: person-pos(r.at(3), r.at(2)), department: person-dep(r.at(2)),
                decision: v.at(0), fg: v.at(1), bg: v.at(2), code: s(r.at(1)),
                ok: s(r.at(1)) == "1" or s(r.at(1)) == "2",
                date: fmtdate(r.at(4)),
                comment: if r.len() > 5 { s(r.at(5)) } else { "" }))
    }
  }
  for r in data.at("rows", default: ()) {
    let code = s(r.at("code", default: "1"))
    let v = visa(code)
    out.push((group: s(r.at("stage", default: "")), fio: s(r.at("fio", default: "")),
              position: s(r.at("position", default: "")),
              department: s(r.at("department", default: "")),
              decision: if s(r.at("decision", default: "")) != "" {
                s(r.at("decision", default: "")) } else { v.at(0) },
              fg: v.at(1), bg: v.at(2), code: code,
              ok: code == "1" or code == "2",
              date: fmtdate(r.at("date", default: "")),
              comment: s(r.at("comment", default: ""))))
  }
  out
}

// ---- элементы дизайн-системы ----------------------------------------------
#let eyebrow(body) = text(size: 7pt, weight: "bold", fill: accent, tracking: 1.2pt)[#upper(body)]
#let tag(body, fg, bg) = box(fill: bg, radius: 3pt, inset: (x: 5.5pt, y: 2.5pt),
  text(size: 7pt, weight: "bold", fill: fg, tracking: 0.6pt)[#upper(body)])
#let section(num, title, note: "") = {
  v(0.85em)
  grid(columns: (auto, auto, 1fr), column-gutter: 8pt, align: bottom,
    box(stroke: 0.7pt + accent, radius: 3pt, inset: (x: 4pt, y: 2pt),
        text(font: mono, size: 7.5pt, weight: "bold", fill: accent)[#num]),
    text(size: 11.5pt, weight: "bold")[#title],
    align(right, text(size: 7.5pt, fill: ink-3)[#note]),
  )
  v(0.25em)
  line(length: 100%, stroke: 1.4pt + rule-2)
  v(0.6em)
}

// ---- шапка ----------------------------------------------------------------
#if blank == "" {
  grid(columns: (1fr, auto), align: horizon,
    [
      #eyebrow(org.at("name", default: "Организация"))
      #if org.at("code", default: "") != "" [
        #text(size: 7pt, fill: ink-3, tracking: 1.2pt)[ · #upper(org.code)]]
    ],
    text(size: 7pt, fill: ink-3, tracking: 0.8pt)[DOC-V],
  )
  v(0.5em)
}

#let doc-number = {
  let n = s(data.at("document_number", default: ""))
  let d = s(data.at("document_date", default: ""))
  if is-digits(n) and n.len() >= 9 and not is-digits(d) { d } else { n }
}
#let doc-date = {
  let n = s(data.at("document_number", default: ""))
  let d = s(data.at("document_date", default: ""))
  if is-digits(n) and n.len() >= 9 and not is-digits(d) { fmtdate(n, with-time: false) }
  else { fmtdate(d, with-time: false) }
}

#text(size: 18pt, weight: "bold", tracking: -0.3pt)[Лист согласования]
#if doc-number != "" or doc-date != "" {
  v(0.25em)
  text(size: 10pt, fill: ink-2)[#doc-number #if doc-date != "" [ · #doc-date]]
}

// ---- 01. Документ ---------------------------------------------------------
#let sum-line = {
  let raw = data.at("sum", default: (:))
  let one(e) = (fmtnum(e.at("sum", default: "")), s(e.at("currency", default: "")),
                s(e.at("vat", default: ""))).filter(x => x != "").join(" ")
  if type(raw) == array { raw.map(one).join("; ") }
  else if type(raw) == dictionary { one(raw) } else { s(raw) }
}
#let avans-line = {
  let a = data.at("pre_payment", default: "")
  if a == "" or a == 0 or a == "0" { "" } else {
    let raw = data.at("sum", default: (:))
    let cur = if type(raw) == dictionary { s(raw.at("currency", default: "")) }
              else if type(raw) == array and raw.len() > 0 { s(raw.at(0).at("currency", default: "")) }
              else { "" }
    (fmtnum(a) + " " + cur).trim()
  }
}

#section("01", "Документ", note: data.at("department", default: ""))

#let field(label, value) = if value != none and s(value) != "" {
  (text(size: 8pt, fill: ink-3)[#label], [#value])
} else { () }

#block(fill: surface, stroke: 0.7pt + rule, radius: 6pt, inset: (x: 13pt, y: 9pt), width: 100%)[
  #grid(columns: (auto, 1fr), column-gutter: 14pt, row-gutter: 5pt,
    ..(
      field("Предмет", data.at("subject", default: ""))
      + field("Контрагент", data.at("counteragent", default: ""))
      + field("Объект", data.at("object", default: ""))
      + field("Сторона ГК", org.at("name", default: ""))
      + field("Инициатор", data.at("initiator", default: ""))
      + field("Срок", data.at("work_due", default: ""))
      + field("Особые условия", data.at("special_conditions", default: ""))
      + field("Юрист", data.at("lawyer", default: ""))
    ).flatten()
  )
]

#if sum-line != "" or avans-line != "" {
  v(0.6em)
  let card(label, value, strong) = block(width: 100%, fill: if strong { surface-2 } else { surface },
      stroke: 0.7pt + rule, radius: 6pt, inset: (x: 13pt, y: 8pt))[
    #eyebrow(label)
    #v(0.15em)
    #text(font: mono, size: 12pt, weight: "bold")[#value]
  ]
  grid(columns: if avans-line != "" { (1fr, 1fr) } else { (1fr,) }, column-gutter: 9pt,
    ..((card("Сумма по документу", sum-line, true),)
       + if avans-line != "" { (card("Аванс", avans-line, false),) } else { () }))
}

// ---- 02. Согласования -----------------------------------------------------
#let ok-count = rows.filter(r => r.ok).len()
#let all-dates = rows.map(r => r.date).filter(d => d != "")
#let period = {
  // даты без времени, крайние точки маршрута
  let d = all-dates.map(x => x.split(" ").at(0)).filter(x => x != "")
  if d.len() > 1 { " · " + d.first() + " — " + d.last() } else { "" }
}
#section("02", "Согласования",
  note: if rows.len() > 0 {
    "решений: " + str(rows.len()) + " · положительных: " + str(ok-count) + period
  } else { "" })

#if rows.len() == 0 [
  #text(fill: ink-3)[Согласований по документу пока нет.]
] else {
  let label = s(data.at("stage_label", default: "ЭТАП"))
  let groups = ()
  for r in rows {
    if label != "" and groups.len() > 0 and groups.last().at("key") == r.group {
      groups.last().rows.push(r)
    } else { groups.push((key: r.group, rows: (r,))) }
  }
  let cells = ()
  let idx = 0
  for (gi, g) in groups.enumerate() {
    if label != "" and g.key != "" and groups.len() > 1 {
      cells.push(table.cell(colspan: 5, align: left, stroke: none,
        inset: (left: 2pt, top: if gi == 0 { 1pt } else { 9pt }, bottom: 4pt),
        eyebrow(label + " " + g.key)))
    }
    for r in g.rows {
      idx += 1
      cells.push(text(font: mono, size: 8pt, fill: ink-3)[#idx])
      cells.push([#text(weight: "bold")[#r.fio]])
      cells.push([
        #text(size: 8.5pt, fill: ink-2)[#r.position]
        #if r.department != "" [ \ #text(size: 7.5pt, fill: ink-3)[#r.department]]
      ])
      cells.push(tag(r.decision, r.fg, r.bg))
      cells.push(text(font: mono, size: 8pt, fill: ink-2)[#r.date])
      if r.comment != "" {
        cells.push(table.cell(colspan: 5, align: left, stroke: none,
          inset: (left: 24pt, right: 8pt, top: 0pt, bottom: 5pt),
          block(fill: surface-2, radius: 4pt, inset: (x: 8pt, y: 5pt), width: 100%,
                text(size: 8pt, fill: ink-2)[#r.comment])))
      }
    }
  }
  table(
    columns: (auto, 1.05fr, 1.15fr, auto, auto),
    stroke: (x, y) => (bottom: 0.5pt + rule),
    inset: (x: 7pt, y: 4.5pt),
    align: (center + horizon, left + horizon, left + horizon,
            center + horizon, right + horizon),
    table.header(
      ..("№", "Ф.И.О.", "Должность", "Решение", "Дата").map(h =>
        table.cell(inset: (x: 7pt, y: 5pt),
          text(size: 7pt, fill: ink-3, weight: "bold", tracking: 0.8pt)[#upper(h)])),
    ),
    ..cells,
  )
}
