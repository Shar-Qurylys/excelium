// Собрано typst/build.py из common.typ + part_request.typ + request_modern.typ. Править исходники в docv-shark-folder/typst/src.
// ---- общее для печатных форм Doc-V (вшивается в каждый шаблон сборкой typst/build.py) ----
// Входы Excelium: data (JSON от Doc-V), meta (generated_at, verify_code), dir (справочники structura, dolzhnosti).
// Excelium передаёт имена файлов: data=data.json, meta=meta.json, dir=dir.json
#let data = json(sys.inputs.at("data", default: "sample_contract.json"))
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


// «Инженер ПТО» → «инженер ПТО»: строчной делается только первая буква, если за ней строчная
#let lower-first(t) = {
  let c = s(t).clusters()
  if c.len() > 1 and lower(c.at(1)) == c.at(1) { lower(c.at(0)) + c.slice(1).join() } else { s(t) }
}

// ---- заявки (любой тип): данные от шагов «## Печать: …» (typst/docv_print_req.py)
// type, number, date, status, version, organization, title, currency, initiator, department, signer, qr,
// tiles / details — объекты {"NNk Подпись": значение}, NN — порядок, k: m — деньги, d — дата, t — текст;
// approvals_html / signing_html — «Результаты согласования» / «Результаты подписания» (HTML Doc-V).
#let org = split-person(get("organization"))
#let type-name = get("type")
#let number = get("number").replace("№", "").trim()
#let version = get("version")
#let status = get("status")
#let currency = if has("currency") { get("currency") } else { "KZT" }
#let initiator = split-person(get("initiator"))
#let signer = split-person(get("signer"))

// «03m Сумма к оплате»: 70400000 → (label, текст значения)
#let entries(key) = {
  let obj = data.at(key, default: (:))
  if type(obj) != dictionary { return () }
  let items = obj.pairs().sorted(key: p => p.at(0))
  items.map(((k, v)) => {
    let cl = k.clusters()                      // «03mСумма_к_оплате»: NN, вид, подпись с «_» вместо пробелов
    let kind = cl.at(2, default: "t")
    let label = cl.slice(3).join().replace("_", " ")
    let raw = rq(s(v).replace(regex("<br\\s*/?>"), "\n").replace(regex("<[^>]+>"), " ").replace("&nbsp;", " ").replace("&quot;", "\"").replace("&amp;", "&").trim())
    let text = if raw == "" or raw == "0" and kind == "d" { "" }
      else if kind == "m" { money(num(raw)) + " " + cur-sign(currency) }
      else if kind == "d" { date-long(raw) }
      else { raw }
    (label: label, value: text, kind: kind, num: if kind == "m" { num(raw) } else { 0 })
  }).filter(e => e.value != "")
}
#let tiles = entries("tiles")
#let details = entries("details")

// HTML решений Doc-V → строки
#let unhtml(t) = t.replace("&quot;", "\"").replace("&#34;", "\"").replace("&amp;", "&").replace("&laquo;", "«").replace("&raquo;", "»").replace("&#39;", "'").replace("&lt;", "<").replace("&gt;", ">").replace("&nbsp;", " ").trim()
#let grab(blk, cls) = {
  let m = blk.match(regex(cls + "\"[^>]*>([^<]*)<"))
  if m == none { "" } else { unhtml(m.captures.at(0)) }
}
#let negative(t) = { let l = lower(t); l.contains("не ") or l.starts-with("не") or l.contains("отклон") or l.contains("доработ") or l.contains("отказ") }
#let parse-results(html, stage) = {
  let h = s(html)
  if h == "" { return () }
  h.split("decision-block").slice(1).map(blk => {
    let author = grab(blk, "decision-author")
    let acting = ""
    let i = author.position(" / ")
    if i != none { acting = author.slice(i + 3); author = author.slice(0, i) }
    let p = split-person(rq(author))
    let title = grab(blk, "decision-title")
    let at = grab(blk, "decision-added")   // «05.09.2025 09:28:46»
    (stage: stage, name: p.name, position: if acting != "" { p.position + ", " + acting } else { p.position },
     decision: title, ok: not negative(title), at: at, comment: rq(grab(blk, "decision-comment")))
  }).filter(a => a.name != "")
}
#let approvals = parse-results(data.at("approvals_html", default: ""), 1) + parse-results(data.at("signing_html", default: ""), 0)
// дата решения «05.09.2025 09:28:46» → «05.09.2025» и «09:28»
#let at-date(t) = s(t).split(" ").at(0, default: "")
#let at-time(t) = { let x = s(t).split(" ").at(1, default: ""); if x.len() >= 5 { x.slice(0, 5) } else { x } }
#let qr-ok = "qr" in data and s(data.qr) != ""

// Карточка заявки — стиль «Современный».
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
#let cap(t, c: ink-3) = text(6.8pt, fill: c, tracking: 0.08em, weight: "bold", upper(t))
#let band = if tiles.len() > 0 { 4.75cm } else { 3.9cm }

#set page(paper: "a4", margin: (x: 1.5cm, top: 1.1cm, bottom: 1.5cm),
  background: context if here().page() == 1 { place(top, rect(width: 100%, height: band, fill: night)) },
  foreground: context if here().page() == counter(page).final().first() and qr-ok {
    place(right + bottom, dx: -1.5cm, dy: -1.45cm, box(fill: white, stroke: 0.6pt + line-c, radius: 6pt, inset: 7pt,
      grid(columns: (auto, 1.8cm), column-gutter: 8pt, align: (right + bottom, right),
        stack(spacing: 4pt, cap("Документ в Doc-V"), text(7pt, fill: ink-3, font: sans)[наведите камеру]),
        image("qr.png", width: 1.8cm))))
  },
  footer: context { set text(7pt, fill: ink-3, font: sans); [Сформировано в Doc-V #meta.at("generated_at", default: "")] })
#set text(font: sans, size: 9pt, fill: ink, lang: "ru")
#set par(leading: 0.5em)

// ---- шапка
#grid(columns: (1fr, auto), align: (left + top, right + top), column-gutter: 12pt,
  stack(spacing: 6pt,
    [#cap(org.name, c: rgb("#CFE3DA")) #if org.position != "" { h(10pt); cap(org.position, c: rgb("#7FA597")) }],
    v(6pt),
    text(9pt, fill: rgb("#CFE3DA"), type-name),
    if number != "" { text(24pt, fill: white, weight: "bold")[№ #number] } else { text(16pt, fill: white, weight: "bold", get("title")) },
    text(9pt, fill: rgb("#CFE3DA"))[#if has("date") [от #date-formal(get("date"))] #if number != "" and has("title") { h(10pt); get("title") }]),
  grid(columns: 2, column-gutter: 5pt,
    if version != "" { box(stroke: 0.7pt + rgb("#7FA597"), radius: 10pt, inset: (x: 9pt, y: 4pt), text(8pt, fill: rgb("#CFE3DA"), weight: "bold")[Версия #version]) },
    if status != "" { box(fill: mint, radius: 10pt, inset: (x: 9pt, y: 4.5pt), text(8pt, fill: white, weight: "bold")[● #status]) }))
#v(if tiles.len() > 0 { 22pt } else { 30pt })

// ---- плитки
#if tiles.len() > 0 {
  let shown = tiles.slice(0, calc.min(4, tiles.len()))
  let tb(i, e) = box(width: 100%, fill: if i == 0 { mint-bg } else { tile }, radius: 6pt, inset: 9pt,
    stack(spacing: 5pt, cap(e.label, c: if i == 0 { mint } else { ink-3 }), text(if e.kind == "t" { 11pt } else { 15pt }, weight: "bold", e.value)))
  grid(columns: shown.enumerate().map(((i, e)) => if i == 0 and e.kind == "m" { 1.45fr } else { 1fr }), column-gutter: 7pt,
    ..shown.enumerate().map(((i, e)) => tb(i, e)))
  v(12pt)
}

// ---- сведения: две колонки карточек «подпись — значение»
#let det = details
#if initiator.name != "" { det.push((label: "Инициатор", value: initiator.name + if initiator.position != "" { ", " + lower-first(initiator.position) } else { "" } + if has("department") { "\n" + get("department") } else { "" }, kind: "t", num: 0)) }
#if det.len() > 0 {
  grid(columns: (1fr, 1fr), column-gutter: 7pt, row-gutter: 7pt,
    ..det.map(e => box(width: 100%, stroke: 0.6pt + line-c, radius: 6pt, inset: (x: 9pt, y: 7pt),
      stack(spacing: 4pt, cap(e.label), text(9pt, e.value)))))
  v(12pt)
}

// ---- лента согласования
#if approvals.len() > 0 {
  text(11pt, weight: "bold")[Согласование]
  v(4pt)
  let dot(a) = box(width: 17pt, height: 17pt, radius: 50%, fill: if a.ok { mint } else { bad-c },
    align(center + horizon, text(6.5pt, fill: white, weight: "bold", initials(a.name))))
  let item(a) = grid(columns: (17pt, 1fr, auto), column-gutter: 7pt, align: (horizon, horizon, right + horizon),
    dot(a),
    [#text(weight: "bold", short-name(a.name)) #h(4pt) #text(fill: ink-2, a.position) #if a.comment != "" { linebreak(); text(7.5pt, fill: mint, style: "italic")[«#a.comment»] }],
    [#box(fill: if a.ok { mint-bg } else { rgb("#F7E7E2") }, radius: 3pt, inset: (x: 5pt, y: 2pt), text(7.5pt, fill: if a.ok { mint } else { bad-c }, weight: "bold", a.decision)) #h(4pt) #box(width: 2.55cm, align(right, text(7.5pt, fill: ink-3, font: mono)[#at-date(a.at) #at-time(a.at)]))])
  for st in (1, 0) {
    let rows = approvals.filter(a => a.stage == st)
    if rows.len() > 0 {
      grid(columns: (2.2cm, 1fr), column-gutter: 8pt,
        box(inset: (top: 4pt), cap(if st == 0 { "Подписание" } else { "Согласующие" }, c: if st == 0 { gold } else { ink-2 })),
        box(width: 100%, stroke: (left: 1.2pt + line-c), inset: (left: 8pt, y: 3pt), stack(spacing: 5pt, ..rows.map(item))))
      v(3pt)
    }
  }
}
#if signer.name != "" and approvals.filter(a => a.stage == 0).len() == 0 {
  v(6pt); cap("Подписант"); linebreak(); text(10pt, weight: "bold", signer.name); h(6pt); text(fill: ink-2, signer.position)
}
