"""Collect Olympic and World Indoor finals from Wikipedia's per-event pages into data/raw/ (one file per meet).

Not part of build.sh: it needs the network. Run it to add a championship, then review the report and rebuild.
    python3 scripts/fetch_pro.py 2008-OG 2018-WI ... [--cache DIR]

The final is the results table with medal icons (heats and semis have none). Countries become IOC codes
(List of IOC country codes, plus former and neutral teams). The world record going in comes from the
page's records table; World Indoor pages have none, so their records come from the indoor section of
"List of world records in athletics" as that page stood the day before the meet (its revision history). Fields with more than
20 finishers keep places 1-10 plus the last finisher, as in the rest of the bank.
"""
import json, os, re, sys, time, urllib.request, urllib.parse
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_ncaa import Walker, fetch, clean_mark, event_code, UA   # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEETS = {   # id: (championship name, city, year, title prefix, events)
    "2000-OG": ("Olympic Games", "Sydney", 2000, "Athletics at the 2000 Summer Olympics", "out"),
    "2004-OG": ("Olympic Games", "Athens", 2004, "Athletics at the 2004 Summer Olympics", "out"),
    "2008-OG": ("Olympic Games", "Beijing", 2008, "Athletics at the 2008 Summer Olympics", "out"),
    "2012-OG": ("Olympic Games", "London", 2012, "Athletics at the 2012 Summer Olympics", "out"),
    "2016-WI": ("World Indoor Championships", "Portland", 2016, "2016 IAAF World Indoor Championships", "in"),
    "2018-WI": ("World Indoor Championships", "Birmingham", 2018, "2018 IAAF World Indoor Championships", "in"),
    "2022-WI": ("World Indoor Championships", "Belgrade", 2022, "2022 World Athletics Indoor Championships", "in"),
    "2024-WI": ("World Indoor Championships", "Glasgow", 2024, "2024 World Athletics Indoor Championships", "in"),
    "2025-WI": ("World Indoor Championships", "Nanjing", 2025, "2025 World Athletics Indoor Championships", "in"),
}
RANK_COLS = ("rank", "place", "pos", "pos.", "position")
FIELD_EVENTS = {"HJ", "PV", "LJ", "TJ", "SP", "DT", "HT", "JT"}
mark_value = lambda m: sum(float(p) * 60 ** i for i, p in enumerate(reversed(m.split(":"))))
MEET_START = {"2016-WI": "2016-03-17", "2018-WI": "2018-03-01", "2022-WI": "2022-03-18", "2024-WI": "2024-03-01",
              "2025-WI": "2025-03-21"}
EVENTS = {
    "out": ["100", "200", "400", "800", "1500", "5000", "10000", "marathon", "H", "400H", "3000SC",
            "HJ", "PV", "LJ", "TJ", "SP", "DT", "HT", "JT"],
    "in": ["60", "400", "800", "1500", "3000", "60H", "HJ", "PV", "LJ", "TJ", "SP"],
}
WIKI = {"10000": "10,000 metres", "marathon": "marathon", "60H": "60 metres hurdles", "100H": "100 metres hurdles",
        "110H": "110 metres hurdles", "400H": "400 metres hurdles", "3000SC": "3000 metres steeplechase",
        "HJ": "high jump", "PV": "pole vault", "LJ": "long jump", "TJ": "triple jump", "SP": "shot put",
        "DT": "discus throw", "HT": "hammer throw", "JT": "javelin throw"}
# Teams the IOC list doesn't name the way results tables do
EXTRA_CODES = {"Great Britain": "GBR", "Authorised Neutral Athletes": "ANA", "Neutral Athletes": "ANA",
               "Netherlands Antilles": "AHO", "Serbia and Montenegro": "SCG", "Independent Olympic Athletes": "IOA",
               "Chinese Taipei": "TPE", "Ivory Coast": "CIV", "Côte d'Ivoire": "CIV", "Russia": "RUS",
               "Czech Republic": "CZE", "Czechia": "CZE", "Unified Team": "EUN", "Refugee Olympic Team": "EOR",
               "Athlete Refugee Team": "ART", "Hong Kong": "HKG", "South Korea": "KOR", "North Korea": "PRK",
               "Iran": "IRI", "Moldova": "MDA", "Syria": "SYR", "Tanzania": "TAN", "Venezuela": "VEN",
               "Bolivia": "BOL", "Vietnam": "VIE", "Laos": "LAO", "Brunei": "BRU", "Macedonia": "MKD",
               "North Macedonia": "MKD", "Federated States of Micronesia": "FSM", "Virgin Islands": "ISV",
               "United States Virgin Islands": "ISV", "British Virgin Islands": "IVB", "Bahamas": "BAH",
               "The Bahamas": "BAH", "Gambia": "GAM", "The Gambia": "GAM", "Kosovo": "KOS", "Palestine": "PLE",
               "Saint Kitts and Nevis": "SKN", "Saint Lucia": "LCA", "Saint Vincent and the Grenadines": "VIN",
               "Trinidad and Tobago": "TTO", "Republic of the Congo": "CGO", "DR Congo": "COD",
               "Democratic Republic of the Congo": "COD", "Eswatini": "SWZ", "Swaziland": "SWZ", "Turkey": "TUR",
               "Türkiye": "TUR", "Taiwan": "TPE", "Kyrgyzstan": "KGZ", "Cape Verde": "CPV",
               "United Kingdom": "GBR", "Great Britain & N.I.": "GBR", "Turks and Caicos Islands": "TKS",
               "FR Yugoslavia": "YUG", "Yugoslavia": "YUG", "Individual Olympic Athletes": "IOA"}


def ioc_codes(cache):
    """Country name -> IOC code, from Wikipedia's list (current and historic tables)."""
    w = Walker()
    w.feed(fetch("List of IOC country codes", cache)["html"])
    codes = {}
    for it in w.items:
        if it[0] == "table":
            for r in it[2]:
                if len(r) >= 2 and re.fullmatch(r"[A-Z]{3}", r[0].strip()):
                    name = re.sub(r"\s*\{[^}]*\}\s*|\s*\(.*?\)|\[.*?\]", "", r[1]).strip()
                    codes.setdefault(name, r[0].strip())
    codes.update(EXTRA_CODES)
    return codes


def strip(text):
    return re.sub(r"\s+", " ", re.sub(r"\{[^}]*\}", "", text)).strip()


def pro_mark(text, ev):
    """Result cell -> mark string. Marathons keep h:mm:ss; everything else goes through clean_mark."""
    t = strip(text).replace(",", "").replace("seconds", "").replace(" s", " ").replace(" m", " ")
    if ev == "marathon":
        m = re.search(r"\b(\d:\d{2}:\d{2})\b", t)
        return m.group(1) if m else None
    return clean_mark(t)


def parse_event(html, codes, ev):
    """-> (rows, world record going in or None, warnings)"""
    w = Walker(grid=True)
    w.feed(html)
    warnings, wr, finals, heading = [], None, [], ""
    for it in w.items:
        if it[0] == "h":
            heading = it[2]
            continue
        if it[0] != "table":
            continue
        for r in it[2]:
            if r and re.fullmatch(r"world record", strip(r[0]).lower()) and len(r) >= 3 and wr is None:
                cells = [strip(c) for c in r[1:]]
                mark = next((m for m in (pro_mark(c, ev) for c in cells) if m), None)
                who = next((c for c in cells if re.search(r"\([A-Z]{3}\)", c)), cells[0])
                year = next((m.group(0) for c in cells for m in [re.search(r"\b(19|20)\d{2}\b", c)] if m), None)
                if mark and year:
                    wr = (mark, re.sub(r"\s*\([A-Z]{3}\)", "", who).strip(), int(year))
        if len(it[2]) < 3:
            continue
        # the header is the first row starting with Rank/Place/Position (some tables put a caption row first)
        hi = next((i for i, r in enumerate(it[2][:3]) if len(r) >= 3 and strip(r[0]).lower() in RANK_COLS), None)
        if hi is None:
            continue
        hdr, body = [strip(c).lower() for c in it[2][hi]], it[2][hi + 1:]
        where = (heading + " " + " ".join(" ".join(r) for r in it[2][:hi])).lower()
        medals = any(re.search(r"\{\d(?:st|nd|rd) place", r[0]) for r in body if r)
        final = bool(re.search(r"\bfinal", where)) and not re.search(r"semi|quarter", where)
        finals.append((medals, final, hdr, body))
    # The final: a medal table under a "Final" heading, else any table under "Final", else a medal table.
    # (Some pages also have an overall ranking with medals that mixes in the semifinalists.)
    pick = [f for f in finals if f[0] and f[1]] or [f for f in finals if f[1]] or [f for f in finals if f[0]]
    if not pick:
        return [], wr, ["no final table"]
    _, _, hdr, body = pick[-1]
    col = lambda names: next((i for n in names for i, h in enumerate(hdr) if h == n), None)
    ni = col(("athlete", "name"))
    ci = col(("nation", "nationality", "country", "team", "noc"))
    widths = [len(r) for r in body if len(r) > 2]
    if ci is None and ni is not None and widths and max(set(widths), key=widths.count) == len(hdr) + 1:
        hdr = hdr[:ni + 1] + ["nation"] + hdr[ni + 1:]   # a country column with no header cell
        ci = ni + 1
    mi = max((i for i, h in enumerate(hdr) if h in ("time", "result", "mark", "distance", "height", "best mark", "final")),
             default=None)   # the last of these: attempt-by-attempt tables end with the best mark
    if ni is None or mi is None:
        return [], wr, [f"columns not found in {hdr}"]

    def code_of(cell):
        """'Jamaica', 'Qatar (QAT)', 'Jan Železný (CZE)', or a flag icon's country name -> IOC code"""
        m = re.search(r"\(([A-Z]{3})\)", cell)
        if m:
            return m.group(1)
        return codes.get(strip(cell)) or next((codes[a] for a in re.findall(r"\{([^}]+)\}", cell) if a in codes), None)

    rows, top = [], 0
    for r in body:
        if len(r) <= max(ni, mi):
            continue
        m = re.search(r"\{(\d+)(?:st|nd|rd|th) place", r[0]) or re.match(r"^\s*=?T?(\d+)\b", strip(r[0]))
        mark = pro_mark(r[mi], ev)
        if not mark or not (m or not strip(r[0])):
            continue
        # medal rows on some older pages have only an unlabelled medal image in the place cell
        place = int(m.group(1)) if m else (rows[-1][0] + 1 if rows else 1)
        notes = " ".join(strip(c) for c in r[mi + 1:])
        if re.search(r"\b(DQ|DSQ|DPG)\b", notes):   # disqualified (DPG: positive test) but still listed
            warnings.append(f"dropped disqualified {strip(r[ni])}")
            continue
        if place < top and not (rows and place == rows[-1][0]):
            warnings.append(f"dropped out-of-order row {place} {strip(r[ni])} (disqualified/reallocated)")
            continue
        top = max(top, place)
        name = re.sub(r"\s*\([A-Z]{3}\)$", "", strip(r[ni]))
        code = (code_of(r[ci]) if ci is not None else None) or code_of(r[ni]) \
            or (next((c for c in map(code_of, r[ni + 1:mi]) if c), None) if ci is None else None)   # unlabelled column
        if not code:
            warnings.append(f"no code for {strip(r[ci]) if ci is not None else name!r}")
            continue
        rows.append((place, name, code, mark, "WR" if re.search(r"(?<![=\w])WR\b", notes) else ""))
    if len(rows) > 20:   # big fields: places 1-10 plus the last finisher
        rows = rows[:10] + rows[-1:]
    return rows, wr, warnings


def indoor_records(day, cache):
    """{(gender, event): [(mark, holder, date)]} from "List of world records in athletics" as of a day."""
    title = "List of world records in athletics"
    q = urllib.parse.urlencode({"action": "query", "format": "json", "prop": "revisions", "titles": title,
                                "rvlimit": 1, "rvdir": "older", "rvprop": "ids|timestamp", "rvstart": day + "T00:00:00Z"})
    rev = next(iter(json.load(urllib.request.urlopen(urllib.request.Request(
        "https://en.wikipedia.org/w/api.php?" + q, headers=UA), timeout=60))["query"]["pages"].values()))["revisions"][0]
    path = os.path.join(cache, f"wr_list_{rev['revid']}.json") if cache else None
    if path and os.path.exists(path):
        html = json.load(open(path))["html"]
    else:
        url = "https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode(
            {"action": "parse", "format": "json", "oldid": rev["revid"], "prop": "text", "formatversion": 2})
        html = json.load(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=90))["parse"]["text"]
        if path:
            json.dump({"html": html}, open(path, "w"))
        time.sleep(3)
    w = Walker(grid=True)
    w.feed(html)
    # Older versions have an "Indoor" section; newer ones a "Short track world records" section, or mark
    # indoor rows in the World records tables with "sh" after the event or "i" in the N column.
    out, indoor, g, section = {}, False, None, ""
    for it in w.items:
        if it[0] == "h":
            t = it[2].lower()
            if it[1] == 2:
                indoor, section = "indoor" in t or "short track" in t, t
            if "women" in t:
                g = "W"
            elif re.search(r"\bmen", t):
                g = "M"
            continue
        marked = section == "world records"
        if not (indoor or marked) or not g or "wikitable" not in it[1]:
            continue
        hdr = [strip(c).lower() for c in it[2][0]]
        if "event" not in hdr:
            continue
        idx = lambda pred, default=None: next((i for i, h in enumerate(hdr) if pred(h)), default)
        ni, di, ai = idx(lambda h: h == "n"), idx(lambda h: h == "date"), idx(lambda h: h.startswith("athlete"), 2)
        pi = idx(lambda h: h in ("perf.", "record", "mark"), 1)
        for r in it[2][1:]:
            if len(r) <= max(pi, ai):
                continue
            if marked and not (strip(r[0]).endswith(" sh") or (ni is not None and "i" in strip(r[ni]).split())):
                continue
            ev = event_code(re.sub(r" sh$", "", strip(r[0])))
            mark = clean_mark(strip(r[pi]).replace(" m", " "))
            when = None
            if di is not None and di < len(r):
                try:
                    when = datetime.strptime(re.sub(r"\[.*?\]|\s+", " ", strip(r[di])).strip()[:11].strip(), "%d %b %Y").date()
                except ValueError:
                    try:
                        when = datetime.strptime(strip(r[di]).strip()[:20].strip(), "%d %B %Y").date()
                    except ValueError:
                        pass
            # The first row for an event is the ratified record. Rows after it count only if newer (pending
            # records); older ones are annulled marks the list keeps for reference (e.g. a 1993 doping case).
            if ev and mark and when and (not out.get((g, ev)) or when >= out[(g, ev)][0][2]):
                out.setdefault((g, ev), []).append((mark, strip(r[ai]), when))
    return out, rev["timestamp"]


def main():
    ids = [a for a in sys.argv[1:] if a in MEETS]
    cache = sys.argv[sys.argv.index("--cache") + 1] if "--cache" in sys.argv else None
    codes = ioc_codes(cache)
    for cid in ids:
        name, city, year, prefix, kind = MEETS[cid]
        out, notes = [f"#CH {cid}|{name}|{city}|{year}"], []
        fallback = {}
        if cid in MEET_START:
            # The list can lag a few days behind a new record, so merge every version we use (one before each
            # meet, plus today's) and take the best mark dated before this meet.
            start = date.fromisoformat(MEET_START[cid])
            for day in list(MEET_START.values()) + [date.today().isoformat()]:
                for key, recs in indoor_records(day, cache)[0].items():
                    for mark, who, when in recs:
                        if when < start:
                            v = mark_value(mark)
                            best = fallback.get(key)
                            if best is None or (v > mark_value(best[0]) if key[1] in FIELD_EVENTS else v < mark_value(best[0])):
                                fallback[key] = (mark, who, when.year)
            notes.append(f"indoor world records before {start}: {len(fallback)}")
        for g in ("M", "W"):
            for ev in EVENTS[kind]:
                ev = ("110H" if g == "M" else "100H") if ev == "H" else ev
                if ev == "3000SC" and g == "W" and year < 2008:
                    continue   # women's steeplechase joined the Olympics in 2008
                title = f"{prefix} – {'Men' if g == 'M' else 'Women'}'s {WIKI.get(ev, ev + ' metres')}"
                try:
                    page = fetch(title, cache)
                except Exception as e:
                    notes.append(f"{g}{ev}: page not found ({e})")
                    continue
                rows, wr, warnings = parse_event(page["html"], codes, ev)
                if cid in MEET_START:
                    wr = None   # indoor pages' own tables are rare and can be stale; use the dated list
                notes += [f"{g}{ev}: {x}" for x in warnings]
                if len(rows) < 5:
                    notes.append(f"{g}{ev}: only {len(rows)} finishers, skipped")
                    continue
                out.append(f"@{g}{ev}")
                wr = wr or fallback.get((g, ev))
                if wr:
                    out.append(f"WR|{wr[0]}|{wr[1]}|{wr[2]}")
                else:
                    notes.append(f"{g}{ev}: no world record on the page")
                out += [f"{p}|{n}|{c}|{m}|{f}" for p, n, c, m, f in rows]
        with open(os.path.join(ROOT, "data", "raw", cid + ".txt"), "w", encoding="utf-8") as fh:
            fh.write("\n".join(out) + "\n")
        print(f"{cid}: {sum(l.startswith('@') for l in out)} finals" + "".join("\n  " + n for n in notes))


if __name__ == "__main__":
    main()
