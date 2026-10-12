"""Build the Photo Finish question bank from raw championship files.

Input:  data/raw/*.txt  (one file per championship; see format in raw files)
Output: data/questions.json   every final, ready for the game
        wr_history.json  world record per event, as it stood before each championship, plus records set in finals
        review.csv       everything a person should look at before a question goes live
"""
import json, glob, os, re, csv, statistics

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")

EVENTS = {
    "100": ("100 m", "s"), "200": ("200 m", "s"), "400": ("400 m", "s"),
    "800": ("800 m", "ms"), "1500": ("1500 m", "ms"), "5000": ("5000 m", "ms"),
    "10000": ("10,000 m", "ms"), "marathon": ("marathon", "hms"),
    "100H": ("100 m hurdles", "s"), "110H": ("110 m hurdles", "s"), "400H": ("400 m hurdles", "s"),
    "3000SC": ("3000 m steeplechase", "ms"),
    "HJ": ("high jump", "m"), "PV": ("pole vault", "m"), "LJ": ("long jump", "m"), "TJ": ("triple jump", "m"),
    "SP": ("shot put", "m"), "DT": ("discus", "m"), "HT": ("hammer", "m"), "JT": ("javelin", "m"),
}
FIELD = {"HJ": "high", "PV": "high", "LJ": "far", "TJ": "far", "SP": "far", "DT": "far", "HT": "far", "JT": "far"}
GROUP = {"100": "sprint", "200": "sprint", "400": "sprint", "100H": "hurdles", "110H": "hurdles", "400H": "hurdles",
         "800": "middle", "1500": "middle", "5000": "distance", "10000": "distance", "3000SC": "distance",
         "marathon": "road", "HJ": "jumps", "PV": "jumps", "LJ": "jumps", "TJ": "jumps",
         "SP": "throws", "DT": "throws", "HT": "throws", "JT": "throws"}


def to_value(mark, fmt):
    """Mark string -> seconds (track) or metres (field)."""
    m = mark.strip().rstrip("m").strip()
    if fmt == "m" or fmt == "s":
        return float(m)
    parts = [float(p) for p in m.split(":")]
    v = 0.0
    for p in parts:
        v = v * 60 + p
    return v


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
        if line.startswith("@"):
            code = line[1:]
            cur = {"code": code, "wr": None, "rows": []}
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
            partial = len(rows) >= 2 and places[-1] - places[-2] > 1
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
            wr_value = to_value(wr["mark"], fmt) if wr else None
            # Trust the source's WR annotation (wind-aided or semifinal records must not count)
            wr_broken = winner["flag"] == "WR"
            if not wr_broken and wr_value is not None and better(winner["value"], wr_value):
                flag("wr-mismatch", f'winner {winner["mark"]} beats WR going in {wr["mark"]} but is not marked WR (wind? annulled?)')

            note = None
            if wr_broken:
                note = f'World record. The old mark was {wr["mark"]} by {wr["holder"]} ({wr["year"]}).'

            questions.append({
                "id": qid,
                "championship": champ["name"], "city": champ["city"], "year": champ["year"],
                "gender": gender, "event": ev, "label": f"{gender}'s {label}",
                "group": GROUP[ev], "fmt": fmt, "field": field,
                "answer": winner["value"], "answer_mark": winner["mark"],
                "clue_index": clue_idx,
                "results": [[r["place"], r["name"], r["nat"], r["value"]] for r in rows],
                "partial": partial,
                "wr_before": {"mark": wr["mark"], "value": wr_value, "holder": wr["holder"], "year": wr["year"]} if wr else None,
                "wr_broken": wr_broken,
                "note": note,
                "flags": flags,
                "verified": False,
                "source": "Wikipedia event page (final results table)",
            })

    # World record history per event: the record going into each championship, plus records set in these finals.
    history = {}
    for q in questions:
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
    print(len(qs), "questions;", sum(q["wr_broken"] for q in qs), "with a world record set in the final")
    print("review items:", Counter(r["issue"] for r in rev))
