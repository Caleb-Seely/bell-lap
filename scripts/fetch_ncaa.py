"""Collect NCAA Division I indoor and outdoor finals from Wikipedia into data/raw/ (one file per meet).

Not part of build.sh: it needs the network. Run it to add a year, then review the report and rebuild.
    python3 scripts/fetch_ncaa.py 2016-2025 [--cache DIR]

Reads each championship page's rendered results tables. Relays and combined events are skipped, as are
rows without a valid mark (DNF, DNS, DQ, NM). The school goes where pro finals have the country. Notes
with CL/CR (collegiate record, not "=CL") mark a record set in the final. Pages that list only the
scoring places get a "CUT" line so the game doesn't claim to know the field size. When an event has
several tables (heats, then the final), the one with medal icons is the final; otherwise the last one.
"""
import json, os, re, sys, time, urllib.request, urllib.parse
from html.parser import HTMLParser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = {"User-Agent": "bell-lap-build/1.0 (https://github.com/Caleb-Seely/bell-lap)"}
CANCELLED = {2020}
# Wikipedia errors checked against the official results: (meet, event, athlete as on Wikipedia) ->
# (mark, source[, fixed name][, (place, team) to add a row Wikipedia lost])
CORRECTIONS = {
    ("2023-NCAAO", "MDT", "Rojé Stona"): ("65.55", "flashresults.ncaa.com/Outdoor/2023/018-1.pdf"),
    ("2023-NCAAO", "M400H", "Nathaniel Eziekel"): ("48.54", "flashresults.ncaa.com/Outdoor/2023/010-2.pdf", "Nathaniel Ezekiel"),
    ("2021-NCAAO", "M800", "Yusuf Bizimana"): ("1:46.76", "dt8v5llb2dwhs.cloudfront.net/Outdoor/2021/004-2.pdf"),
    ("2021-NCAAO", "M800", "Eric Brown"): ("1:46.76", "dt8v5llb2dwhs.cloudfront.net/Outdoor/2021/004-2.pdf"),
    ("2017-NCAAI", "MWT", "James Hubbard"): ("20.11", "tfrrs.org/results/49567_3023724.html"),
    ("2024-NCAAI", "WWT", "Gudrun Hallgrimsdottir"): ("22.07", "flashresults.ncaa.com/Indoor/2024/032-1.pdf"),
    ("2024-NCAAI", "W400", "Rosey Effiong"): ("51.03", "flashresults.ncaa.com/Indoor/2024/019-2.pdf", None, (3, "Arkansas")),
}
NAME_COLS = ("athlete", "name")
TEAM_COLS = ("team", "university", "school")
MARK_COLS = ("mark", "time", "best mark", "best jump", "best throw", "distance", "height")
# Usual size of a final; a list well short of it only shows the scoring places.
FIELD_SIZE = {"O": {"1500": 12, "3000SC": 12, "5000": 24, "10000": 24, "HJ": 24, "PV": 24, "LJ": 24, "TJ": 24,
                    "SP": 24, "DT": 24, "HT": 24, "JT": 24},
              "I": {"mile": 10, "3000": 16, "5000": 16, "HJ": 16, "PV": 16, "LJ": 16, "TJ": 16, "SP": 16, "WT": 16}}


class Walker(HTMLParser):
    """Headings and tables in document order: ("h", level, text) and ("table", class, rows of cell text)."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.items, self.h, self.depth, self.rows, self.cell, self.skip = [], None, 0, None, None, 0

    def handle_starttag(self, tag, a):
        a = dict(a)
        cls, style = a.get("class") or "", (a.get("style") or "").replace(" ", "")
        if self.skip or tag in ("style", "script") or (tag == "sup" and "reference" in cls) \
                or (tag == "span" and ("sortkey" in cls or style.startswith("display:none"))):
            if tag in ("sup", "span", "style", "script"):
                self.skip += 1
            return
        if re.fullmatch(r"h[2-5]", tag) and not self.depth:
            self.h = [int(tag[1]), ""]
        if tag == "table":
            self.depth += 1
            if self.depth == 1:
                self.rows, self.tclass = [], cls
        if self.depth == 1:
            if tag == "tr":
                self.rows.append([])
            elif tag in ("td", "th"):
                self.cell = ""
            elif tag == "br" and self.cell is not None:
                self.cell += " "
        if tag == "img" and self.cell is not None and a.get("alt"):
            self.cell += " {" + a["alt"] + "} "

    def handle_endtag(self, tag):
        if self.skip:
            if tag in ("sup", "span", "style", "script"):
                self.skip -= 1
            return
        if self.h and re.fullmatch(r"h[2-5]", tag):
            self.items.append(("h", self.h[0], self.h[1].strip()))
            self.h = None
        if tag in ("td", "th") and self.depth == 1 and self.cell is not None:
            if self.rows:
                self.rows[-1].append(re.sub(r"\s+", " ", self.cell).strip())
            self.cell = None
        if tag == "table" and self.depth:
            self.depth -= 1
            if not self.depth:
                self.items.append(("table", self.tclass, self.rows))

    def handle_data(self, d):
        if self.skip:
            return
        if self.h is not None:
            self.h[1] += d
        if self.cell is not None:
            self.cell += d


def event_code(heading):
    """Heading text -> event code, or None for relays, combined events and anything else."""
    h = heading.lower().replace("metres", "meters").replace("-meter", " meters").replace(",", "")
    h = re.sub(r"\b(wo)?men'?s\b", "", h)
    if re.search(r"relay|medley|athlon|dmr", h):
        return None
    if "steeple" in h:
        return "3000SC"
    m = re.search(r"(\d+)\s*(?:meters|m)?\s*hurdles", h) or (re.search(r"(\d+)", h) if "hurdles" in h else None)
    if m:
        return {"60": "60H", "100": "100H", "110": "110H", "400": "400H"}.get(m.group(1))
    for k, c in (("mile", "mile"), ("high jump", "HJ"), ("pole vault", "PV"), ("long jump", "LJ"), ("triple jump", "TJ"),
                 ("shot put", "SP"), ("discus", "DT"), ("hammer", "HT"), ("javelin", "JT"), ("weight", "WT")):
        if k in h:
            return c
    m = re.search(r"\b(60|100|200|400|800|1500|3000|5000|10000)\b", h)
    return m.group(1) if m else None


def gender_of(heading):
    h = heading.lower()
    return "W" if re.search(r"\bwomen", h) else "M" if re.search(r"\bmen", h) else None


MARK_RE = re.compile(r"^(\d{1,2}:)?\d{1,3}\.\d{1,3}$")   # NCAA has no marathon, so no h:mm:ss


def clean_mark(text):
    """'9.97 [.964]', '20.29 m', '13:22.34', '6.82 (+1.2)' -> '9.97', '20.29', ... or None."""
    for tok in re.split(r"[\s\[\(]+", text.replace("m ", " ").rstrip("m")):
        tok = tok.strip().rstrip("m").rstrip("*").rstrip("A").rstrip("h")
        tok = re.sub(r"^(\d{1,2}):(\d{2}):(\d{2})$", r"\1:\2.\3", tok)   # source typo 9:30:85 -> 9:30.85
        tok = re.sub(r"^0(\d)", r"\1", tok)   # "01.88"
        if MARK_RE.match(tok) and float(tok.split(":")[-1]) > 0:
            if len(tok.split(".")[-1]) == 3:   # thousandths split ties; the official time rounds up
                head, frac = tok.rsplit(".", 1)
                hund = -(-int(frac) // 10)
                tok = head + "." + f"{hund:02d}" if hund < 100 else None
                if tok is None:
                    continue
            return tok + "0" if len(tok.split(".")[-1]) == 1 else tok   # "32:47.7" -> "32:47.70"
    return None


def rank_of(text):
    m = re.search(r"\{(\d+)(?:st|nd|rd|th) place", text) or re.match(r"^\s*=?T?(\d+)\b", text)
    return int(m.group(1)) if m else None


def page_countries(html):
    """Flag-icon alt texts are country names; some tables also print them after the athlete."""
    names = set(m for m in re.findall(r'<img[^>]*alt="([A-Z][A-Za-z .\'-]+)"', html) if "place" not in m)
    return names | {n[4:] for n in names if n.startswith("The ")}


def parse_page(html, countries):
    items = Walker()
    items.feed(html)
    info = next((t for t in items.items if t[0] == "table" and "infobox" in t[1]), None)
    meta = {}
    for r in (info[2] if info else []):
        if len(r) == 2:
            meta[r[0].lower()] = r[1]
    tables, gender, event, warnings = {}, None, None, []
    countries = sorted(countries, key=len, reverse=True)
    for it in items.items:
        if it[0] == "h":
            g = gender_of(it[2])
            if g:
                gender = g
            event = event_code(it[2]) if it[1] >= 3 else None
            if event is None and g and it[1] >= 3:
                event = event_code(it[2])
            continue
        if it[0] != "table" or "wikitable" not in it[1] or not it[2] or not event or not gender:
            continue
        hdr = [c.lower() for c in it[2][0]]
        if not hdr or hdr[0] != "rank":
            continue
        col = lambda names: next((i for n in names for i, h in enumerate(hdr) if h == n), None)
        ni, ti, mi = col(NAME_COLS), col(TEAM_COLS), col(MARK_COLS)
        notes = col(("notes",))
        if ni is None or mi is None:
            continue
        key = f"{gender}{event}"
        rows, medals = [], any("{1st place" in r[0] for r in it[2][1:] if r)
        prev = None
        for r in it[2][1:]:
            # a tied rank is one cell spanning several rows; the later rows arrive one cell short
            if prev and len(r) == len(hdr) - 1 and rank_of(r[0]) is None and not re.search(r"\{\d", r[0]):
                r = [prev] + r
            prev = r[0] if r and rank_of(r[0]) else prev
            if len(r) <= max(ni, mi):
                continue
            # merged cells (a "Round" header over six attempts, or passes spanning several heights) make rows
            # wider or narrower than the header; columns after the merge line up from the right
            mark = clean_mark(r[mi - len(hdr) + len(r)] if len(r) != len(hdr) and mi > ti else r[mi])
            place = rank_of(r[0]) if r[0].strip() else None
            if mark is None or place is None:
                continue
            name = re.sub(r"\s*\{[^}]*\}\s*", " ", r[ni]).strip()
            name = re.sub(r"\s*\([A-Z]{3}\)$", "", name)                    # "Isaiah Jewett (USA)"
            name = re.sub(r"\s*\((athlete|sprinter|runner|hurdler|jumper|thrower)\)", "", name)
            tag = re.search(r"\s+(=?(?:CR|CL|NR|AR|WL|MR|FR|PB|SB))$", name)   # notes printed after the name
            if tag:
                name = name[:tag.start()]
            name = re.sub(r"\s+(" + "|".join(map(re.escape, countries)) + r")$", "", name) if countries else name
            if not name or "[[" in name:   # empty placeholder rows on some pages
                continue
            team = re.sub(r"\s*\{[^}]*\}\s*", " ", r[ti]).strip() if ti is not None and ti < len(r) else ""
            note = r[notes] if notes is not None and notes < len(r) else ""
            flag = "CR" if re.search(r"(?<![=\w])(CR|CL)\b", note) or (tag and tag.group(1) in ("CR", "CL")) else ""
            rows.append((place, name, team, mark, flag))
        if rows:
            tables.setdefault(key, []).append((medals, rows))
    finals = {}
    for key, ts in tables.items():
        final = next((rows for medals, rows in ts if medals), ts[-1][1])
        if len(ts) > 1:
            warnings.append(f"{key}: {len(ts)} tables, used the {'medal' if any(m for m, _ in ts) else 'last'} one")
        finals[key] = final
    return meta, finals, warnings


def fetch(title, cache):
    path = os.path.join(cache, re.sub(r"\W+", "_", title) + ".json") if cache else None
    if path and os.path.exists(path):
        return json.load(open(path))
    url = "https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode(
        {"action": "parse", "format": "json", "page": title, "prop": "text|revid", "redirects": 1, "formatversion": 2})
    for attempt in range(4):
        try:
            d = json.load(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60))["parse"]
            break
        except Exception as e:
            print("  retry:", e)
            time.sleep(10 * (attempt + 1))
    d = {"title": d["title"], "revid": d["revid"], "html": d["text"]}
    if path:
        json.dump(d, open(path, "w"))
    time.sleep(3)
    return d


ORDER = ["60", "100", "200", "400", "800", "1500", "mile", "3000", "5000", "10000", "60H", "100H", "110H", "400H",
         "3000SC", "HJ", "PV", "LJ", "TJ", "SP", "DT", "HT", "JT", "WT"]


def main():
    a, b = (int(x) for x in sys.argv[1].split("-"))
    cache = sys.argv[sys.argv.index("--cache") + 1] if "--cache" in sys.argv else None
    pages = {(y, kind, k): fetch(f"{y} NCAA Division I {kind} Track and Field Championships", cache)["html"]
             for y in range(a, b + 1) if y not in CANCELLED for kind, k in (("Indoor", "I"), ("Outdoor", "O"))}
    countries = set().union(*map(page_countries, pages.values()))
    parsed = {key: parse_page(html, countries) for key, html in pages.items()}
    # Some pages add the mascot ("Texas Longhorns"). A school is a name used on 3+ pages; other names map
    # to the longest school name they start with.
    seen = {}
    for key, (_, finals, _) in parsed.items():
        for rows in finals.values():
            for r in rows:
                seen.setdefault(r[2], set()).add(key)
    schools = {t for t, ks in seen.items() if len(ks) >= 3}
    def school(t):
        if t in schools:
            return t
        w = t.split()
        keep = {"State", "St.", "St", "Tech", "A&M", "Christian", "Southern", "Baptist", "University", "College",
                "Poly", "Methodist", "Atlantic", "International", "Valley", "Kentucky", "Carolina", "Illinois",
                "Michigan", "Florida", "Texas", "Tennessee", "Washington", "Arizona", "Colorado", "Mississippi",
                "Eastern", "Upstate", "RedHawks", "(OH)", "(Ohio)", "A&M-CC"}   # different schools, not mascots
        return next((" ".join(w[:i]) for i in range(len(w) - 1, 0, -1)
                     if " ".join(w[:i]) in schools and w[i] not in keep), t)
    renamed = sorted({(t, school(t)) for t in seen if school(t) != t})
    print(f"{len(renamed)} team names shortened, e.g. " + "; ".join(f"{a} -> {b}" for a, b in renamed[:8]))
    for (y, kind, k), (meta, finals, warnings) in parsed.items():
        for key in list(finals):
            finals[key] = [(p, n, school(t), m, f) for p, n, t, m, f in finals[key]]
            if len(finals[key]) < 5:   # some pages list only the winner
                warnings.append(f"{key}: only {len(finals[key])} finishers listed, skipped")
                del finals[key]
        if True:
            city = re.split(r",", re.sub(r"\{[^}]*\}", "", meta.get("host city", meta.get("location", ""))))[0].strip()
            dates = meta.get("dates", meta.get("date", ""))
            cid = f"{y}-NCAA{k}"
            for (c, key, who), (mark, src, *more) in CORRECTIONS.items():
                if c != cid or key not in finals:
                    continue
                name = more[0] if more and more[0] else who
                if len(more) > 1 and all(n != who for _, n, *_ in finals[key]):
                    place, team = more[1]
                    finals[key] = sorted(finals[key] + [(place, name, team, mark, "")], key=lambda r: r[0])
                else:
                    finals[key] = [(p, name if n == who else n, t, mark if n == who else m, f) for p, n, t, m, f in finals[key]]
                warnings.append(f"{key}: {who} -> {name} {mark} ({src})")
            out = [f"#CH {cid}|NCAA {kind} Championships|{city}|{y}", f"#DATES {dates}"]
            for key in sorted(finals, key=lambda k: (k[0] != "M", ORDER.index(k[1:]))):
                out.append("@" + key)
                if len(finals[key]) < FIELD_SIZE[k].get(key[1:], 8) - 3:
                    out.append("CUT")
                out += [f"{p}|{n}|{t}|{m}|{f}" for p, n, t, m, f in finals[key]]
            with open(os.path.join(ROOT, "data", "raw", cid + ".txt"), "w", encoding="utf-8") as fh:
                fh.write("\n".join(out) + "\n")
            print(f"{cid}: {len(finals)} finals, {city}, {dates}" + "".join("\n  " + w for w in warnings))


if __name__ == "__main__":
    main()
