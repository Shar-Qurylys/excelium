// Собрано typst/build.py из prelude.typ + contract_registry.typ. Править исходники в docv-shark-folder/typst/src.
// ---- общее для печатных форм Doc-V (вшивается в каждый шаблон сборкой typst/build.py) ----
// Входы Excelium: data (JSON от Doc-V), meta (generated_at, verify_code), dir (справочники structura, dolzhnosti).
// Excelium передаёт имена файлов: data=data.json, meta=meta.json, dir=dir.json
#let data = json(sys.inputs.at("data", default: "sample.json"))
#let meta = if "meta" in sys.inputs { json(sys.inputs.meta) } else { (generated_at: "25.11.2026 21:40", verify_code: "K7Q4-9XPM") }
#let dir = if "dir" in sys.inputs { json(sys.inputs.dir) } else { (:) }

#let sans = ("PT Sans", "Liberation Sans", "Arial", "DejaVu Sans")
#let serif = ("PT Serif", "Liberation Serif", "DejaVu Serif")
#let mono = ("PT Mono", "Liberation Mono", "DejaVu Sans Mono")

#let s(v) = if v == none { "" } else { str(v).trim() }
// прямые кавычки → «ёлочки»: ТОО "СМУ Аргон" → ТОО «СМУ Аргон»
#let rq(t) = {
  let out = ""
  let open = true
  for ch in t.clusters() {
    if ch == "\"" { out += if open { "«" } else { "»" }; open = not open } else { out += ch }
  }
  out
}
#let get(k) = rq(s(data.at(k, default: "")))
#let num(v) = {
  let t = s(v).replace(" ", "").replace("\u{a0}", "").replace(",", ".")
  if t == "" { 0.0 } else { float(t) }
}
#let has(k) = get(k) != ""

// 70400000 → «70 400 000»; копейки — только если есть
#let money(n) = {
  let v = calc.round(float(n), digits: 2)
  let whole = calc.floor(calc.abs(v))
  let cents = calc.round((calc.abs(v) - whole) * 100)
  let out = ""
  let i = 0
  for ch in str(int(whole)).rev().clusters() {
    if i > 0 and calc.rem(i, 3) == 0 { out = "\u{202F}" + out }
    out = ch + out
    i += 1
  }
  (if v < 0 { "−" } else { "" }) + out + if cents > 0 { "," + (if cents < 10 { "0" } else { "" }) + str(int(cents)) } else { "" }
}
#let cur-sign(c) = if c == "KZT" { "₸" } else if c == "RUB" { "₽" } else if c == "USD" { "$" } else if c == "EUR" { "€" } else if c == "CNY" { "¥" } else { c }
#let vat-text(c) = if s(c) == "0" { "без НДС" } else if s(c) == "1" { "с НДС" } else if s(c) == "2" { "НДС 0 %" } else { s(c) }

// даты: ISO «2024-07-05T22:14:44+05:00», unix-время или «05.07.2024»
#let months = ("января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря")
#let from-unix(ts) = {
  let days = calc.floor((ts + 18000) / 86400)
  let secs = calc.rem(ts + 18000, 86400)
  let z = days + 719468
  let era = calc.floor(z / 146097)
  let doe = z - era * 146097
  let yoe = calc.floor((doe - calc.floor(doe / 1460) + calc.floor(doe / 36524) - calc.floor(doe / 146096)) / 365)
  let doy = doe - (365 * yoe + calc.floor(yoe / 4) - calc.floor(yoe / 100))
  let mp = calc.floor((5 * doy + 2) / 153)
  let d = doy - calc.floor((153 * mp + 2) / 5) + 1
  let m = mp + (if mp < 10 { 3 } else { -9 })
  let y = yoe + era * 400 + (if m <= 2 { 1 } else { 0 })
  (y: y, m: m, d: d, hh: calc.floor(secs / 3600), mi: calc.floor(calc.rem(secs, 3600) / 60))
}
#let is-digits(t) = t.len() > 0 and t.clusters().all(c => "0123456789".contains(c))
#let parts(v) = {
  let t = s(v)
  if t == "" or t == "0" { return none }
  if is-digits(t) { return from-unix(int(t)) }
  if t.len() >= 10 and t.at(4) == "-" {
    return (y: int(t.slice(0, 4)), m: int(t.slice(5, 7)), d: int(t.slice(8, 10)),
      hh: if t.len() >= 16 { int(t.slice(11, 13)) } else { 0 }, mi: if t.len() >= 16 { int(t.slice(14, 16)) } else { 0 })
  }
  if t.len() >= 10 and t.at(2) == "." {
    return (y: int(t.slice(6, 10)), m: int(t.slice(3, 5)), d: int(t.slice(0, 2)), hh: 0, mi: 0)
  }
  none
}
#let p2(x) = if x < 10 { "0" + str(x) } else { str(x) }
#let date-long(v) = { let p = parts(v); if p == none { "—" } else { str(p.d) + " " + months.at(p.m - 1) + " " + str(p.y) } }
#let date-formal(v) = { let p = parts(v); if p == none { "—" } else { "«" + str(p.d) + "» " + months.at(p.m - 1) + " " + str(p.y) + " г." } }
#let date-num(v) = { let p = parts(v); if p == none { "" } else { p2(p.d) + "." + p2(p.m) + "." + str(p.y) } }
#let time(v) = { let p = parts(v); if p == none { "" } else { p2(p.hh) + ":" + p2(p.mi) } }

// «Карпсеитов Арман Нургалиевич (Менеджер)» → имя и должность
#let split-person(t) = {
  let t = s(t)
  let i = t.position(" (")
  if i != none and t.ends-with(")") { (name: t.slice(0, i), position: t.slice(i + 2, t.len() - 1)) } else { (name: t, position: "") }
}
#let short-name(full) = {
  let w = s(full).split(" ").filter(x => x != "")
  if w.len() == 0 { return "" }
  if w.len() == 1 { return w.at(0) }
  w.at(0) + " " + w.slice(1).map(x => x.clusters().at(0) + ".").join(" ")
}
#let initials(full) = {
  let w = s(full).split(" ").filter(x => x != "")
  if w.len() == 0 { return "?" }
  if w.len() == 1 { return w.at(0).clusters().at(0) }
  w.at(1).clusters().at(0) + w.at(0).clusters().at(0)
}

// ---- договор / ДС
#let org = split-person(get("organization"))
#let is-ds = get("is_ds") == "1"
#let number = get("number").replace("№", "").trim()
#let ds-number = get("ds_number").replace("№", "").trim()
#let version = get("version")
#let status = get("status")
#let kind = if get("kind") != "" { get("kind") } else { "Договор" }
#let currency = if has("currency") { get("currency") } else { "KZT" }
#let amount = num(data.at("amount", default: 0))
#let prepay = num(data.at("prepay_pct", default: 0))
#let paid = num(data.at("paid", default: 0))
#let remaining = if has("remaining") { num(data.at("remaining")) } else { amount - paid }
#let plural(n, one, few, many) = {
  let n = calc.abs(int(n)); let m10 = calc.rem(n, 10); let m100 = calc.rem(n, 100)
  if m10 == 1 and m100 != 11 { one } else if m10 >= 2 and m10 <= 4 and (m100 < 12 or m100 > 14) { few } else { many }
}
#let wd = get("work_due")
#let wu = get("work_unit")
#let work-due = if is-digits(wd) and (wu == "кд" or wu == "рд") { wd + " " + plural(int(wd), "день", "дня", "дней") } else { (wd + " " + wu).trim() }
#let work-sub = ((if wu == "кд" { "календарных" } else if wu == "рд" { "рабочих" } else { "" }), get("validity")).filter(x => x != "").join(", ")
#let initiator = split-person(get("initiator"))
#let lawyer = split-person(get("lawyer"))
#let signer = split-person(get("signer"))

// ---- согласования: строки «Таблицы решения» [этап, код, uid сотрудника, uid должности, время, комментарий, версия]
#let cards = dir.at("people", default: (:))          // карточки «Сотрудник»: uid → ФИО (витрина «API_Люди»)
#let people = dir.at("structura", default: (:))      // записи «Структуры» (на случай старых данных)
#let posts = dir.at("positions", default: dir.at("dolzhnosti", default: (:)))
#let decision(code) = if code == "1" { ("Согласовано", true) } else if code == "2" { ("Подписано", true) } else if code == "-1" { ("Не согласовано", false) } else if code == "-2" { ("Не подписано", false) } else { (code, true) }
#let approvals = {
  let raw = data.at("approved_by", default: ())
  if type(raw) == str { raw = if raw.trim() == "" { () } else { json(bytes(raw)) } }
  if raw.len() > 0 and type(raw.at(0)) == array and raw.at(0).len() > 0 and type(raw.at(0).at(0)) == array { raw = raw.at(0) }
  raw.filter(r => type(r) == array and r.len() >= 5).map(r => {
    let person = cards.at(s(r.at(2)), default: people.at(s(r.at(2)), default: (:)))
    let post = posts.at(s(r.at(3)), default: (:)).at("name", default: "")
    let nm = split-person(rq(person.at("name", default: s(r.at(2)).slice(0, calc.min(8, s(r.at(2)).len())) + "…")))
    let d = decision(s(r.at(1)))
    (stage: int(num(r.at(0))), code: s(r.at(1)), decision: d.at(0), ok: d.at(1),
     name: nm.name, position: if post != "" { rq(post) } else { person.at("position", default: nm.position) },
     at: s(r.at(4)), comment: if r.len() > 5 { s(r.at(5)) } else { "" }, version: if r.len() > 6 { s(r.at(6)) } else { "" })
  })
}
#let stages = {
  let nums = approvals.map(a => a.stage).dedup().sorted()
  (nums.filter(n => n != 0) + nums.filter(n => n == 0)).map(n => (n: n, rows: approvals.filter(a => a.stage == n)))
}
#let stage-title(n) = if n == 0 { "Подписание" } else { "Этап " + str(n) }
#let qr-ok = "qr" in data and s(data.qr) != ""
// ---- конец общего

// Карточка договора / ДС — стиль «Реестр». Данные: см. typst/src/prelude.typ.
#let ink = rgb("#111418")
#let ink-2 = rgb("#4A5058")
#let ink-3 = rgb("#80868E")
#let hair = rgb("#C9CDD2")
#let accent = rgb("#1C3F94")
#let ok-c = rgb("#1E7B4F")
#let bad-c = rgb("#B3261E")
#let old-c = rgb("#9A6A10")

#set page(paper: "a4", margin: (x: 1.6cm, top: 1.4cm, bottom: 1.6cm),
  footer: context {
    set text(7pt, fill: ink-3, font: sans)
    line(length: 100%, stroke: 0.4pt + hair)
    v(-4pt)
    grid(columns: (auto, 1fr, auto), column-gutter: 14pt,
      text(fill: ink-2, weight: "bold", upper(if is-ds { "Карточка доп. соглашения" } else { "Карточка договора" })),
      [Сформировано в Doc-V #meta.at("generated_at", default: "")],
      [Стр. #counter(page).display() из #counter(page).final().first()])
  })
#set text(font: sans, size: 9pt, fill: ink, lang: "ru")
#set par(leading: 0.5em)
#let label(t) = text(6.8pt, fill: ink-3, tracking: 0.06em, upper(t))

// ---- шапка
#[#text(7.5pt, tracking: 0.12em, weight: "bold", upper(org.name)) #if org.position != "" { h(10pt); text(7.5pt, tracking: 0.12em, fill: ink-3, upper(org.position)) }]
#v(2pt)
#line(length: 100%, stroke: 1.4pt + ink)
#v(8pt)
#grid(columns: (1fr, auto), align: (left + bottom, right + bottom),
  stack(spacing: 5pt,
    text(8.5pt, fill: ink-2, if is-ds { "Дополнительное соглашение к договору № " + number } else { kind }),
    text(26pt, weight: "bold", tracking: -0.01em)[№ #if is-ds { ds-number } else { number }],
    text(9.5pt, fill: ink-2)[от #date-long(if is-ds { get("ds_date") } else { get("reg_date") })]),
  grid(columns: 2, column-gutter: 6pt,
    if version != "" { box(stroke: 0.8pt + hair, inset: (x: 8pt, y: 5pt), text(8pt, fill: ink-2, weight: "bold", upper("Версия " + version))) },
    if status != "" { box(stroke: 0.8pt + accent, inset: (x: 8pt, y: 5pt), text(8pt, fill: accent, weight: "bold", upper(status))) }))
#v(10pt)

// ---- ключевые цифры
#let cell(l, v, sub: none) = box(width: 100%, inset: (x: 0pt, y: 7pt), stack(spacing: 4pt, label(l), text(15pt, weight: "bold", v), if sub != none { text(7.5pt, fill: ink-3, sub) }))
#line(length: 100%, stroke: 0.5pt + hair)
#grid(columns: (1.5fr, 1fr, 1fr, 1fr), column-gutter: 14pt,
  cell(if is-ds { "Сумма с учётом ДС" } else { "Сумма договора" }, [#money(amount) #cur-sign(currency)], sub: vat-text(get("vat"))),
  cell("Аванс", [#money(prepay) %], sub: [#money(amount * prepay / 100) #cur-sign(currency)]),
  cell("Оплачено", [#money(paid) #cur-sign(currency)], sub: [остаток #money(remaining) #cur-sign(currency)]),
  cell("Срок работ", if work-due != "" { work-due } else { "—" }, sub: work-sub))
#line(length: 100%, stroke: 0.5pt + hair)
#v(12pt)

// ---- сведения
#let row(l, v) = if type(v) == content or s(v) != "" { (text(8pt, fill: ink-2, l), v) } else { () }
#grid(columns: (3.2cm, 1fr), row-gutter: 9pt, column-gutter: 10pt,
  ..row("Предмет", text(10.5pt, weight: "bold", get("subject"))),
  ..if has("counterparty") { row("Контрагент", [#get("counterparty") #if has("counterparty_bin") { h(6pt); text(fill: ink-3, font: mono, size: 8pt)[БИН #get("counterparty_bin")] }]) },
  ..row("Объект", get("object")),
  ..row("Организация", get("organization")),
  ..if initiator.name != "" { row("Инициатор", [#initiator.name#if initiator.position != "" [ — #lower(initiator.position)]#if has("department") [, #get("department")]]) },
  ..row("Особые условия", get("special")),
)
#v(16pt)

// ---- лист согласования
#grid(columns: (1fr, auto), align: bottom, text(11pt, weight: "bold")[Лист согласования], text(7.5pt, fill: ink-3)[#approvals.filter(a => a.stage != 0).len() виз])
#v(4pt)
#line(length: 100%, stroke: 1pt + ink)
#let rows = ()
#for st in stages.filter(x => x.n != 0) {
  for (i, a) in st.rows.enumerate() {
    if i == 0 { rows.push(table.cell(rowspan: st.rows.len(), text(8pt, weight: "bold", fill: accent, str(st.n)))) }
    rows += (
      [#text(weight: "bold", short-name(a.name)) #if a.comment != "" { linebreak(); text(7.5pt, fill: ink-2, style: "italic")[«#a.comment»] }],
      text(fill: ink-2, a.position),
      text(fill: if a.ok { ok-c } else { bad-c }, weight: "bold", [#if a.ok [✓] else [✕] #a.decision]),
      text(fill: if a.version == version or version == "" { ink-2 } else { old-c }, a.version),
      text(font: mono, size: 7.8pt, fill: ink-2)[#date-num(a.at)#h(5pt)#time(a.at)],
    )
  }
}
#if rows.len() == 0 [#v(6pt) #text(fill: ink-3)[Согласований пока нет.]] else {
  table(columns: (0.9cm, 1fr, 1.35fr, 2.5cm, 1.3cm, 3.1cm), stroke: (x, y) => (bottom: 0.4pt + hair), inset: (x: 0pt, y: 5pt),
    align: (left + top, left + top, left + top, left + top, center + top, right + top),
    table.header(..("Этап", "Согласующий", "Должность", "Решение", "Версия", "Дата и время").map(t => label(t))),
    ..rows)
}
#v(14pt)

// ---- подписант, юрист, QR
#line(length: 100%, stroke: 0.5pt + hair)
#v(6pt)
#grid(columns: (1fr, 1.2fr, 1fr), column-gutter: 16pt, align: (top, top, right),
  if signer.name != "" { stack(spacing: 5pt, label("Подписант"), text(10pt, weight: "bold", signer.name), text(fill: ink-2, signer.position)) },
  if lawyer.name != "" { stack(spacing: 5pt, label("Ответственный юрист"), text(10pt, weight: "bold", lawyer.name), text(fill: ink-2, lawyer.position)) },
  if qr-ok { grid(columns: (auto, 1.9cm), column-gutter: 8pt, align: (right + bottom, right),
    stack(spacing: 4pt, label("Документ в Doc-V"), text(7pt, fill: ink-3)[наведите камеру]),
    image("qr.png", width: 1.9cm)) })
