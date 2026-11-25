// Собрано typst/build.py из prelude.typ + contract_modern.typ. Править исходники в docv-shark-folder/typst/src.
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

// Карточка договора / ДС — стиль «Современный». Данные: см. typst/src/prelude.typ.
#let night = rgb("#14302A")
#let ink = rgb("#15201C")
#let ink-2 = rgb("#4B5752")
#let ink-3 = rgb("#86918C")
#let line-c = rgb("#DCE3DF")
#let tile = rgb("#F1F5F3")
#let mint = rgb("#2F8F6A")
#let mint-bg = rgb("#E3F2EA")
#let gold = rgb("#C9A24A")
#let bad-c = rgb("#B3261E")
#let old-c = rgb("#9A6A10")
#let cap(t, c: ink-3) = text(6.8pt, fill: c, tracking: 0.08em, weight: "bold", upper(t))

#set page(paper: "a4", margin: (x: 1.5cm, top: 1.1cm, bottom: 1.5cm),
  background: context if here().page() == 1 { place(top, rect(width: 100%, height: 4.75cm, fill: night)) },
  foreground: context if here().page() == counter(page).final().first() and (qr-ok or meta.at("verify_code", default: "") != "") {
    place(right + bottom, dx: -1.5cm, dy: -1.45cm, box(fill: white, stroke: 0.6pt + line-c, radius: 6pt, inset: 7pt,
      grid(columns: if qr-ok { (auto, 1.8cm) } else { (auto,) }, column-gutter: 8pt, align: (right + bottom, right),
        stack(spacing: 4pt,
          if qr-ok { cap("Документ в Doc-V") }, if qr-ok { text(7pt, fill: ink-3, font: sans)[наведите камеру] },
          v(4pt),
          cap("Код подлинности"), text(9pt, font: mono, fill: ink, weight: "bold", meta.at("verify_code", default: ""))),
        ..if qr-ok { (image("qr.png", width: 1.8cm),) })))
  },
  footer: context { set text(7pt, fill: ink-3, font: sans); [Сформировано в Doc-V #meta.at("generated_at", default: "")] })
#set text(font: sans, size: 9pt, fill: ink, lang: "ru")
#set par(leading: 0.5em)

// ---- шапка
#grid(columns: (1fr, auto), align: (left + top, right + top),
  stack(spacing: 6pt,
    [#cap(org.name, c: rgb("#CFE3DA")) #if org.position != "" { h(10pt); cap(org.position, c: rgb("#7FA597")) }],
    v(6pt),
    text(9pt, fill: rgb("#CFE3DA"), if is-ds { "Дополнительное соглашение к договору № " + number } else { kind }),
    text(24pt, fill: white, weight: "bold")[№ #if is-ds { ds-number } else { number }],
    text(9pt, fill: rgb("#CFE3DA"))[от #date-formal(if is-ds { get("ds_date") } else { get("reg_date") }) #h(10pt) #get("subject")]),
  grid(columns: 2, column-gutter: 5pt,
    if version != "" { box(stroke: 0.7pt + rgb("#7FA597"), radius: 10pt, inset: (x: 9pt, y: 4pt), text(8pt, fill: rgb("#CFE3DA"), weight: "bold")[Версия #version]) },
    if status != "" { box(fill: mint, radius: 10pt, inset: (x: 9pt, y: 4.5pt), text(8pt, fill: white, weight: "bold")[● #status]) }))
#v(22pt)

// ---- плитки
#let tilebox(l, v, sub, hl: false) = box(width: 100%, fill: if hl { mint-bg } else { tile }, radius: 6pt, inset: 9pt,
  stack(spacing: 5pt, cap(l, c: if hl { mint } else { ink-3 }), text(15pt, weight: "bold", v), text(7.5pt, fill: ink-2, sub)))
#grid(columns: (1.45fr, 1fr, 1fr, 1fr), column-gutter: 7pt,
  tilebox(if is-ds { "Сумма с учётом ДС" } else { "Сумма договора" }, [#money(amount) #cur-sign(currency)], vat-text(get("vat")), hl: true),
  tilebox("Аванс", [#money(prepay) %], [#money(amount * prepay / 100) #cur-sign(currency)]),
  tilebox("Оплачено", [#money(paid) #cur-sign(currency)], [остаток #money(remaining) #cur-sign(currency)]),
  tilebox("Срок работ", if work-due != "" { work-due } else { "—" }, work-sub))
#v(10pt)

// ---- стороны
#let party(role, name, sub1, sub2) = box(width: 100%, stroke: 0.6pt + line-c, radius: 6pt, inset: 9pt,
  stack(spacing: 4pt, cap(role), text(11pt, weight: "bold", name), text(fill: ink-2, sub1), text(fill: ink-2, sub2)))
#grid(columns: (1fr, auto, 1fr), column-gutter: 6pt, align: horizon,
  party("Заказчик", org.name, org.position, if signer.name != "" [подписант: #short-name(signer.name)]),
  text(14pt, fill: ink-3)[⇄],
  party("Контрагент", get("counterparty"), if has("counterparty_bin") [БИН #get("counterparty_bin")], if has("object") [объект: #get("object")]))
#v(8pt)
#grid(columns: (1fr, 1fr, 1fr), column-gutter: 7pt,
  if initiator.name != "" { stack(spacing: 3pt, cap("Инициатор"), [#short-name(initiator.name)#if initiator.position != "" [, #lower(initiator.position)]], text(7.5pt, fill: ink-3, get("department"))) },
  if lawyer.name != "" { stack(spacing: 3pt, cap("Юрист"), short-name(lawyer.name)) },
  if has("special") { stack(spacing: 3pt, cap("Особые условия"), text(8pt, fill: ink-2, get("special"))) })
#v(12pt)

// ---- лента согласования
#text(11pt, weight: "bold")[Согласование]
#v(4pt)
#let dot(a) = box(width: 17pt, height: 17pt, radius: 50%, fill: if a.ok { mint } else { bad-c },
  align(center + horizon, text(6.5pt, fill: white, weight: "bold", initials(a.name))))
#let item(a) = grid(columns: (17pt, 1fr, auto), column-gutter: 7pt, align: (horizon, horizon, right + horizon),
  dot(a),
  [#text(weight: "bold", short-name(a.name)) #h(4pt) #text(fill: ink-2, a.position) #if a.comment != "" { linebreak(); text(7.5pt, fill: mint, style: "italic")[«#a.comment»] }],
  [#box(fill: if a.ok { mint-bg } else { rgb("#F7E7E2") }, radius: 3pt, inset: (x: 5pt, y: 2pt), text(7.5pt, fill: if a.ok { mint } else { bad-c }, weight: "bold", a.decision)) #h(4pt) #box(width: 1.25cm, align(center, text(7.5pt, fill: if a.version == version or version == "" { ink-3 } else { old-c }, weight: if a.version == version or version == "" { "regular" } else { "bold" })[#if a.version != "" [версия #a.version]])) #box(width: 2.55cm, align(right, text(7.5pt, fill: ink-3, font: mono)[#date-num(a.at) #time(a.at)]))])
#if stages.len() == 0 [#text(fill: ink-3)[Согласований пока нет.]]
#for st in stages {
  grid(columns: (2.2cm, 1fr), column-gutter: 8pt,
    box(inset: (top: 4pt), cap(stage-title(st.n), c: if st.n == 0 { gold } else { ink-2 })),
    box(width: 100%, stroke: (left: 1.2pt + line-c), inset: (left: 8pt, y: 3pt),
      stack(spacing: 5pt, ..st.rows.map(item))))
  v(3pt)
}
