// Собрано typst/build.py из common.typ + part_request.typ + request_registry.typ. Править исходники в docv-shark-folder/typst/src.
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

// Карточка заявки — стиль «Реестр».
#let ink = rgb("#111418")
#let ink-2 = rgb("#4A5058")
#let ink-3 = rgb("#80868E")
#let hair = rgb("#C9CDD2")
#let accent = rgb("#1C3F94")
#let ok-c = rgb("#1E7B4F")
#let bad-c = rgb("#B3261E")

#set page(paper: "a4", margin: (x: 1.6cm, top: 1.4cm, bottom: 1.6cm),
  footer: context {
    set text(7pt, fill: ink-3, font: sans)
    line(length: 100%, stroke: 0.4pt + hair)
    v(-4pt)
    grid(columns: (auto, 1fr, auto), column-gutter: 14pt,
      text(fill: ink-2, weight: "bold", upper("Карточка заявки")),
      [Сформировано в Doc-V #meta.at("generated_at", default: "")],
      [Стр. #counter(page).display() из #counter(page).final().first()])
  })
#set text(font: sans, size: 9pt, fill: ink, lang: "ru")
#set par(leading: 0.5em)
#let label(t) = text(6.8pt, fill: ink-3, tracking: 0.06em, upper(t))

// ---- шапка
#if org.name != "" [#text(7.5pt, tracking: 0.12em, weight: "bold", upper(org.name)) #if org.position != "" { h(10pt); text(7.5pt, tracking: 0.12em, fill: ink-3, upper(org.position)) }]
#v(2pt)
#line(length: 100%, stroke: 1.4pt + ink)
#v(8pt)
#grid(columns: (1fr, auto), align: (left + bottom, right + bottom), column-gutter: 12pt,
  stack(spacing: 5pt,
    text(8.5pt, fill: ink-2, type-name),
    if number != "" { text(26pt, weight: "bold", tracking: -0.01em)[№ #number] } else { text(18pt, weight: "bold", get("title")) },
    if has("date") { text(9.5pt, fill: ink-2)[от #date-long(get("date"))] }),
  grid(columns: 2, column-gutter: 6pt,
    if version != "" { box(stroke: 0.8pt + hair, inset: (x: 8pt, y: 5pt), text(8pt, fill: ink-2, weight: "bold", upper("Версия " + version))) },
    if status != "" { box(stroke: 0.8pt + accent, inset: (x: 8pt, y: 5pt), text(8pt, fill: accent, weight: "bold", upper(status))) }))
#if number != "" and has("title") { v(6pt); text(11pt, weight: "bold", get("title")) }
#v(8pt)

// ---- ключевые цифры
#if tiles.len() > 0 {
  let cell(e) = box(width: 100%, inset: (x: 0pt, y: 7pt), stack(spacing: 4pt, label(e.label), text(if e.kind == "t" { 11pt } else { 15pt }, weight: "bold", e.value)))
  line(length: 100%, stroke: 0.5pt + hair)
  grid(columns: tiles.slice(0, calc.min(4, tiles.len())).enumerate().map(((i, e)) => if i == 0 and e.kind == "m" { 1.5fr } else { 1fr }), column-gutter: 14pt,
    ..tiles.slice(0, calc.min(4, tiles.len())).map(cell))
  line(length: 100%, stroke: 0.5pt + hair)
  v(10pt)
}

// ---- сведения
#let rows = details.map(e => (text(8pt, fill: ink-2, e.label), e.value)).flatten()
#if initiator.name != "" { rows += (text(8pt, fill: ink-2, "Инициатор"), [#initiator.name#if initiator.position != "" [ — #lower-first(initiator.position)]#if has("department") [, #get("department")]]) }
#if rows.len() > 0 { grid(columns: (3.6cm, 1fr), row-gutter: 9pt, column-gutter: 10pt, ..rows) }
#v(14pt)

// ---- согласование
#if approvals.len() > 0 {
  grid(columns: (1fr, auto), align: bottom, text(11pt, weight: "bold")[Лист согласования], [])
  v(4pt)
  line(length: 100%, stroke: 1pt + ink)
  table(columns: (1fr, 1.35fr, 2.6cm, 3.1cm), stroke: (x, y) => (bottom: 0.4pt + hair), inset: (x: 0pt, y: 5pt),
    align: (left + top, left + top, left + top, right + top),
    table.header(..("Согласующий", "Должность", "Решение", "Дата и время").map(t => label(t))),
    ..approvals.map(a => (
      [#text(weight: "bold", short-name(a.name)) #if a.stage == 0 { h(4pt); text(7pt, fill: accent, weight: "bold", upper("подписант")) } #if a.comment != "" { linebreak(); text(7.5pt, fill: ink-2, style: "italic")[«#a.comment»] }],
      text(fill: ink-2, a.position),
      text(fill: if a.ok { ok-c } else { bad-c }, weight: "bold", [#if a.ok [✓] else [✕] #a.decision]),
      text(font: mono, size: 7.8pt, fill: ink-2)[#at-date(a.at)#h(5pt)#at-time(a.at)],
    )).flatten())
  v(14pt)
}

// ---- подписант и QR
#line(length: 100%, stroke: 0.5pt + hair)
#v(6pt)
#grid(columns: (1fr, 1fr), column-gutter: 16pt, align: (top, right),
  if signer.name != "" and approvals.filter(a => a.stage == 0).len() == 0 { stack(spacing: 5pt, label("Подписант"), text(10pt, weight: "bold", signer.name), text(fill: ink-2, signer.position)) },
  if qr-ok { grid(columns: (auto, 1.9cm), column-gutter: 8pt, align: (right + bottom, right),
    stack(spacing: 4pt, label("Документ в Doc-V"), text(7pt, fill: ink-3)[наведите камеру]),
    image("qr.png", width: 1.9cm)) })
