"""Collegiate record history from archived Track & Field News record lists -> data/cr_history.json

Not part of build.sh: it needs the network (Wayback Machine). Run it after adding NCAA years.
    python3 scripts/fetch_cr.py [--cache DIR]

T&FN publishes the current collegiate records (men/women, indoor/outdoor) with the date each was set.
Every record seen in any monthly snapshot since 2015 is kept with when it was first and last listed, so
the list for an event is its record progression and marks T&FN later dropped can be ignored. build.py
takes as the record going into a meet the best mark set before it that was still listed then. Only the
in-season section is used (the summer/post-season section that follows is skipped), as on Wikipedia.
"""
import json, os, re, sys, time, urllib.request
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_ncaa import Walker   # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = {"User-Agent": "bell-lap-build/1.0 (https://github.com/Caleb-Seely/bell-lap)"}
PAGES = {   # (indoor/outdoor, gender): addresses the lists have lived at
    ("O", "M"): ["www.trackandfieldnews.com/index.php/records/30-records/276-mens-outdoor-collegiate-records",
                 "trackandfieldnews.com/records/mens-collegiate-records/"],
    ("O", "W"): ["www.trackandfieldnews.com/index.php/records/30-records/280-womens-outdoor-collegiate-records",
                 "trackandfieldnews.com/records/womens-collegiate-records/"],
    ("I", "M"): ["www.trackandfieldnews.com/index.php/records/30-records/474-mens-indoor-collegiate-records",
                 "trackandfieldnews.com/records/mens-indoor-collegiate-records/"],
    ("I", "W"): ["www.trackandfieldnews.com/index.php/records/30-records/503-womens-indoor-collegiate-records",
                 "trackandfieldnews.com/records/womens-indoor-collegiate-records/"],
}
EVENTS = {"60": "60", "100": "100", "200": "200", "400": "400", "800": "800", "1500": "1500", "mile": "mile",
          "3000": "3000", "5000": "5000", "10,000": "10000", "10000": "10000", "steeplechase": "3000SC",
          "steeple": "3000SC", "60 hurdles": "60H", "100 hurdles": "100H", "110 hurdles": "110H",
          "400 hurdles": "400H", "high jump": "HJ", "pole vault": "PV", "long jump": "LJ", "triple jump": "TJ",
          "shot": "SP", "discus": "DT", "hammer": "HT", "javelin": "JT", "weight": "WT"}


def get(url, tries=4):
    for a in range(tries):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=90).read()
        except Exception as e:
            print("  retry:", e)
            time.sleep(15 * (a + 1))
    return None


def snapshots(cache):
    """(kind, gender, timestamp, html) for every monthly snapshot from 2015 on."""
    for (kind, g), urls in PAGES.items():
        for u in urls:
            cdx = json.loads(get(f"https://web.archive.org/cdx/search/cdx?url={u}&output=json&fl=timestamp"
                                 "&filter=statuscode:200&collapse=timestamp:6"))[1:]
            for (ts,) in cdx:
                if int(ts[:4]) < 2015:
                    continue
                path = os.path.join(cache, f"{kind}{g}_{ts}.html") if cache else None
                if path and os.path.exists(path):
                    yield kind, g, ts, open(path, encoding="utf-8", errors="replace").read()
                    continue
                b = get(f"https://web.archive.org/web/{ts}id_/http://{u}")
                time.sleep(2.5)
                if b:
                    if path:
                        open(path, "wb").write(b)
                    yield kind, g, ts, b.decode("utf-8", "replace")


def parse_date(s):
    """'6/07/17', '4/9-10/21', '3/11/01 3/12/11' (a tie) -> earliest date."""
    out = []
    for m, d, y in re.findall(r"(\d{1,2})/(\d{1,2})(?:-\d{1,2})?/(\d{2})\b", s):
        y = int(y)
        out.append(date(2000 + y if y < 50 else 1900 + y, int(m), int(d)))
    return min(out) if out else None


def records(html):
    """In-season records on one snapshot: [(event code, mark, holder, date)]."""
    w = Walker()
    w.feed(html)
    out, sections, event = [], 0, None
    for it in w.items:
        if it[0] != "table":
            continue
        for r in it[2]:
            if not r or not r[0] and len(r) < 4:
                continue
            if r[0].strip().lower() == "track events":   # some years print section headers in capitals
                sections += 1
                if sections > 1:   # the post-season list starts with its own "Track Events"
                    return out
                continue
            if len(r) < 5 or r[0].startswith("("):   # "(American CR)", "(low-altitude)", relay legs
                continue
            if r[0]:
                event = EVENTS.get(r[0].lower().strip())
            if not event:
                continue
            mark = re.sub(r"\(A\)|[ipA]+$", "", r[1].split("|")[0].strip()).strip()
            when = parse_date(r[4])
            if re.fullmatch(r"(\d{1,2}:)?\d{1,3}\.\d{1,2}", mark) and when:
                holder = re.sub(r"\s*\(.*$", "", r[2]).replace("’", "").replace("'", "").strip()
                out.append((event, mark, holder, when))
    return out


def main():
    cache = sys.argv[sys.argv.index("--cache") + 1] if "--cache" in sys.argv else None
    hist, taken, listed = {}, {}, {}
    for kind, g, ts, html in snapshots(cache):
        day = f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}"
        taken.setdefault(f"{kind}-{g}", set()).add(day)
        for event, mark, holder, when in records(html):
            entries = hist.setdefault(f"{kind}-{g}{event}", [])
            listed.setdefault(f"{kind}-{g}{event}", set()).add(day)
            e = next((e for e in entries if e["mark"] == mark and e["date"] == when.isoformat()), None)
            if not e:
                e = {"mark": mark, "holder": holder, "date": when.isoformat(), "first_seen": day, "last_seen": day}
                entries.append(e)
            e["first_seen"], e["last_seen"] = min(e["first_seen"], day), max(e["last_seen"], day)
    for v in hist.values():
        v.sort(key=lambda e: e["date"])
    # "snapshots": per event, the snapshot days that listed it (a page that failed to show an event
    # mustn't look like its record was removed)
    out = {"snapshots": {k: sorted(v) for k, v in sorted(listed.items())}, "records": dict(sorted(hist.items()))}
    with open(os.path.join(ROOT, "data", "cr_history.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    seen = sum(map(len, taken.values()))
    print(f"{seen} snapshots, {len(hist)} events, {sum(map(len, hist.values()))} records")


if __name__ == "__main__":
    main()
