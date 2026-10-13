"""Build the Bell-Lap question bank from raw championship files.

Input:  data/raw/*.txt  (one file per championship; see format in raw files)
Output: data/questions.json   every final, ready for the game
        wr_history.json  world record per event, as it stood before each championship, plus records set in finals
        review.csv       everything a person should look at before a question goes live
"""
import json, glob, os, re, csv, statistics
from datetime import date, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")

EVENTS = {
    "60": ("60 m", "s"), "60H": ("60 m hurdles", "s"), "mile": ("mile", "ms"), "3000": ("3000 m", "ms"),
    "WT": ("weight throw", "m"),
    "100": ("100 m", "s"), "200": ("200 m", "s"), "400": ("400 m", "s"),
    "800": ("800 m", "ms"), "1500": ("1500 m", "ms"), "5000": ("5000 m", "ms"),
    "10000": ("10,000 m", "ms"), "marathon": ("marathon", "hms"),
    "100H": ("100 m hurdles", "s"), "110H": ("110 m hurdles", "s"), "400H": ("400 m hurdles", "s"),
    "3000SC": ("3000 m steeplechase", "ms"),
    "HJ": ("high jump", "m"), "PV": ("pole vault", "m"), "LJ": ("long jump", "m"), "TJ": ("triple jump", "m"),
    "SP": ("shot put", "m"), "DT": ("discus", "m"), "HT": ("hammer", "m"), "JT": ("javelin", "m"),
}
WINDY = {"100", "200", "100H", "110H", "LJ", "TJ"}   # outdoor events where a tailwind can void a record
FIELD = {"HJ": "high", "PV": "high", "LJ": "far", "TJ": "far", "SP": "far", "DT": "far", "HT": "far", "JT": "far", "WT": "far"}
GROUP = {"60": "sprint", "60H": "hurdles", "mile": "middle", "3000": "distance", "WT": "throws",
         "100": "sprint", "200": "sprint", "400": "sprint", "100H": "hurdles", "110H": "hurdles", "400H": "hurdles",
         "800": "middle", "1500": "middle", "5000": "distance", "10000": "distance", "3000SC": "distance",
         "marathon": "road", "HJ": "jumps", "PV": "jumps", "LJ": "jumps", "TJ": "jumps",
         "SP": "throws", "DT": "throws", "HT": "throws", "JT": "throws"}
WIKI_EVENT = {"10000": "10,000 metres", "marathon": "marathon", "100H": "100 metres hurdles", "110H": "110 metres hurdles",
              "400H": "400 metres hurdles", "3000SC": "3000 metres steeplechase", "HJ": "high jump", "PV": "pole vault",
              "LJ": "long jump", "TJ": "triple jump", "SP": "shot put", "DT": "discus throw", "HT": "hammer throw",
              "JT": "javelin throw"}


def wiki_page(champ, gender, ev):
    """Title of the event's Wikipedia page (the results source). Uses the edition's name year: Tokyo 2020 was held in 2021."""
    y = champ["id"][:4]
    if champ["name"].startswith("NCAA"):   # one page per meet
        return f'{y} NCAA Division I {champ["name"].split()[1]} Track and Field Championships'
    games = f"Athletics at the {y} Summer Olympics" if champ["name"] == "Olympic Games" else \
        f"{y} World Athletics Championships" if int(y) >= 2019 else f"{y} World Championships in Athletics"
    return f"{games} – {gender}'s {WIKI_EVENT.get(ev, ev + ' metres')}"


def to_value(mark, fmt):
    """Mark string -> seconds (track) or metres (field)."""
    m = mark.strip().rstrip("m").strip()
    if fmt == "m" or (fmt == "s" and ":" not in m):   # a sprinter who fell can take minutes
        return float(m)
    parts = [float(p) for p in m.split(":")]
    v = 0.0
    for p in parts:
        v = v * 60 + p
    return v


def meet_dates(text):
    """'June 7–10, 2023' / 'March 9-10, 2018' -> (first day, last day)."""
    m = re.search(r"([A-Z][a-z]+)\.? (\d{1,2})(?:\s*[–-]\s*(\d{1,2}))?, (\d{4})", text)
    first = datetime.strptime(f"{m.group(1)[:3]} {m.group(2)} {m.group(4)}", "%b %d %Y").date()
    return first, first.replace(day=int(m.group(3) or m.group(2)))


def collegiate_record(cr, champ, gender, ev, fmt, better):
    """The collegiate record going into an NCAA meet: the best mark set before it that T&FN still listed in
    its last snapshot before the meet (marks it later dropped don't count). Also returns marks set at the meet."""
    kind = champ["id"][-1]
    entries = cr["records"].get(f"{kind}-{gender[0]}{ev}", [])
    first, last = champ["dates"]
    snap = max((d for d in cr["snapshots"].get(f"{kind}-{gender[0]}{ev}", []) if d <= first.isoformat()), default=None)
    best = None
    for e in entries:
        if e["date"] < first.isoformat() and (snap is None or e["last_seen"] >= snap or e["first_seen"] > snap):
            v = to_value(e["mark"], fmt)
            if best is None or better(v, best[0]):
                best = (v, e)
    at_meet = [to_value(e["mark"], fmt) for e in entries if first.isoformat() <= e["date"] <= last.isoformat()]
    if not best:
        return None, at_meet
    v, e = best
    return {"mark": e["mark"], "value": v, "holder": e["holder"], "year": int(e["date"][:4]), "kind": "CR"}, at_meet


def parse_file(path):
    finals, champ = [], None
    cur = None
    for raw in open(path, encoding="utf-8"):
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#CH"):
            cid, name, city, year = line[4:].split("|")
            champ = {"id": cid, "name": name, "city": city, "year": int(year)}
            continue
        if line.startswith("#DATES"):
            champ["dates"] = meet_dates(line[7:])
            continue
        if line.startswith("#"):
            continue
        if line == "CUT":   # list stops at the scoring places; the field was bigger
            cur["cut"] = True
            continue
        if line.startswith("@"):
            code = line[1:]
            cur = {"code": code, "wr": None, "rows": [], "cut": False}
            finals.append(cur)
            continue
        f = line.split("|")
        if f[0] == "WR":
            cur["wr"] = {"mark": f[1].strip(), "holder": f[2].strip(), "year": int(re.sub(r"\D", "", f[3])[:4])}
        else:
            cur["rows"].append({"place": int(f[0]), "name": f[1].strip(), "nat": f[2].strip(),
                                "mark": f[3].strip(), "flag": (f[4].strip() if len(f) > 4 else "")})
    return champ, finals


def build():
    questions, review = [], []
    cr_path = os.path.join(DATA, "cr_history.json")
    cr = json.load(open(cr_path, encoding="utf-8")) if os.path.exists(cr_path) else None
    for path in sorted(glob.glob(os.path.join(DATA, "raw", "*.txt"))):
        champ, finals = parse_file(path)
        for fin in finals:
            gender = "Men" if fin["code"][0] == "M" else "Women"
            ev = fin["code"][1:]
            label, fmt = EVENTS[ev]
            field = FIELD.get(ev)
            better = (lambda a, b: a > b) if field else (lambda a, b: a < b)
            rows = fin["rows"]
            for r in rows:
                r["value"] = to_value(r["mark"], fmt)
            qid = f'{champ["id"]}-{fin["code"]}'
            flags = []

            def flag(kind, note):
                flags.append(kind)
                review.append({"id": qid, "issue": kind, "note": note})

            # Partial fields: road / long races trimmed to top 10 + last finisher
            places = [r["place"] for r in rows]
            # (ties and a single missing place don't count: 12, 12, 14 or 6, 8)
            partial = len(rows) >= 2 and places[-1] > places[-2] + places.count(places[-2]) + 1
            if partial:
                flags.append("partial")

            # Order check: marks should never get better further down the list
            for a, b in zip(rows, rows[1:]):
                if better(b["value"], a["value"]):
                    flag("order", f'{b["name"]} {b["mark"]} placed below {a["name"]} {a["mark"]}')

            if any(r["flag"] == "CHECK" for r in rows):
                flag("check-mark", "a mark was unclear on the source page")
            if not field and GROUP[ev] in ("sprint", "hurdles") and len(rows) < 8:
                flag("short-field", f"only {len(rows)} finishers with a time")

            # Clue: last finisher, unless they were far behind (injury, fall).
            # "Far behind" = last gap is more than 3x the typical gap and more than half the rest of the field's spread.
            # Big road/10,000 m fields are stored as top 10 + last finisher; their clue is 10th place.
            clue_idx = len(rows) - 1
            if partial:
                clue_idx = len(rows) - 2
            elif champ["name"].startswith("NCAA") and len(rows) > 12:
                # NCAA field events and distance races list everyone (up to 24); the clue is 12th place,
                # like the last of a 12-athlete final, so it stays within reach of the winner
                clue_idx = max(k for k, r in enumerate(rows) if r["place"] <= 12)
            elif len(rows) >= 4:
                vals = [r["value"] for r in rows]
                gaps = [abs(b - a) for a, b in zip(vals, vals[1:])]
                typical = statistics.median(gaps[:-1]) or 1e-9
                spread = abs(vals[-2] - vals[0])
                if gaps[-1] > 3 * typical and gaps[-1] > 0.5 * spread:
                    clue_idx = len(rows) - 2
                    flag("outlier-last", f'{rows[-1]["name"]} {rows[-1]["mark"]} far behind; clue uses {rows[-2]["name"]} {rows[-2]["mark"]}')

            winner = rows[0]
            wr = fin["wr"]
            ncaa = champ["name"].startswith("NCAA")
            if ncaa:
                # NCAA finals show the collegiate record instead (data/cr_history.json, from scripts/fetch_cr.py)
                wr, at_meet = collegiate_record(cr, champ, gender, ev, fmt, better) if cr else (None, [])
                if wr is None:
                    flag("no-cr", "no collegiate record found for this event")
            wr_value = wr["value"] if wr and "value" in wr else to_value(wr["mark"], fmt) if wr else None
            kind = "CR" if ncaa else "WR"
            if ncaa:
                # a record set in this final shows up in the T&FN history with the meet's dates (or in the notes)
                # Without wind, beating the record is a record, unless it already fell earlier at this meet
                # (a semifinal). Records set and broken again between archived snapshots are only found this way.
                wr_broken = wr_value is not None and better(winner["value"], wr_value) and \
                    not any(better(v, winner["value"]) for v in at_meet) and \
                    (winner["flag"] == "CR" or any(abs(v - winner["value"]) < 1e-9 for v in at_meet)
                     or not (champ["id"].endswith("O") and ev in WINDY))
            else:
                # Trust the source's WR annotation (wind-aided or semifinal records must not count)
                wr_broken = winner["flag"] == "WR"
            if not wr_broken and wr_value is not None and better(winner["value"], wr_value):
                flag(kind.lower() + "-mismatch", f'winner {winner["mark"]} beats {kind} going in {wr["mark"]} but is not marked {kind} (wind? annulled?)')

            note = None
            if wr_broken:
                note = f'{"Collegiate" if ncaa else "World"} record. The old mark was {wr["mark"]} by {wr["holder"]} ({wr["year"]}).'

            questions.append({
                "id": qid,
                "championship": champ["name"], "city": champ["city"], "year": champ["year"],
                "gender": gender, "event": ev, "label": f"{gender}'s {label}",
                "group": GROUP[ev], "fmt": fmt, "field": field,
                "answer": winner["value"], "answer_mark": winner["mark"],
                "clue_index": clue_idx,
                "results": [[r["place"], r["name"], r["nat"], r["value"]] for r in rows],
                "partial": partial,
                "cut": fin["cut"],
                "ncaa": champ["name"].startswith("NCAA"),
                "wr_before": {"mark": wr["mark"], "value": wr_value, "holder": wr["holder"], "year": wr["year"], "kind": kind} if wr else None,
                "wr_broken": wr_broken,
                "note": note,
                "flags": flags,
                "verified": False,
                "source": "Wikipedia event page (final results table)",
                "source_page": wiki_page(champ, gender, ev),
            })

    # World record history per event: the record going into each championship, plus records set in these finals.
    history = {}
    for q in questions:
        if q["ncaa"]:   # collegiate records live in cr_history.json
            continue
        key = f'{q["gender"][0]}{q["event"]}'
        h = history.setdefault(key, {"label": q["label"], "fmt": q["fmt"], "records": {}})
        if q["wr_before"]:
            w = q["wr_before"]
            h["records"].setdefault(w["mark"], {"mark": w["mark"], "value": w["value"], "holder": w["holder"], "year": w["year"], "seen_before": []})
            h["records"][w["mark"]]["seen_before"].append(q["id"])
        if q["wr_broken"]:
            win = q["results"][0]
            h["records"].setdefault(q["answer_mark"], {"mark": q["answer_mark"], "value": q["answer"], "holder": win[1], "year": q["year"], "seen_before": []})
            h["records"][q["answer_mark"]]["set_in"] = q["id"]
    for key, h in history.items():
        field = FIELD.get(key[1:])
        recs = sorted(h["records"].values(), key=lambda r: (r["year"], -r["value"] if not field else r["value"]))
        h["records"] = recs
        # Consistency: a later record should never be worse than an earlier one
        for a, b in zip(recs, recs[1:]):
            worse = (b["value"] < a["value"]) if field else (b["value"] > a["value"])
            if worse:
                review.append({"id": key, "issue": "wr-history", "note": f'{b["mark"]} ({b["year"]}) is worse than earlier {a["mark"]} ({a["year"]}); check women-only vs mixed record or an annulled mark'})

    json.dump(questions, open(os.path.join(DATA, "questions.json"), "w"), ensure_ascii=False, indent=1)
    json.dump(history, open(os.path.join(DATA, "wr_history.json"), "w"), ensure_ascii=False, indent=1)
    with open(os.path.join(DATA, "review.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["id", "issue", "note"])
        w.writeheader()
        w.writerows(review)
    return questions, history, review


if __name__ == "__main__":
    qs, hist, rev = build()
    from collections import Counter
    print(len(qs), "questions;", sum(q["wr_broken"] and not q["ncaa"] for q in qs), "with a world record set in the final;",
          sum(q["wr_broken"] and q["ncaa"] for q in qs), "with a collegiate record")
    print("review items:", Counter(r["issue"] for r in rev))
