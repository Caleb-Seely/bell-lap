"""Daily sets: data/questions.json + data/schedule.json -> data/schedule.json

Days that may already have been played (up to tomorrow in UTC, since some time zones are a day ahead)
are frozen and never change. Later days are generated from the current bank, so new or removed
questions only affect days nobody has seen yet. The generator is a straight port of the original
in-browser picker, so with an unchanged bank it reproduces the same days.

Each day is {"day": n, "cycle": c, "ids": [5 question ids]}. A cycle walks the bank without repeats.
"""
import json, os, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
START = datetime.date(2026, 10, 11)   # Day 1
AHEAD = 400                           # days generated past the frozen ones
BUCKETS = [("sprint", "hurdles"), ("middle", "distance", "road"), ("jumps",), ("throws",)]


def rng(seed):
    def r():
        nonlocal seed
        seed = (seed * 1664525 + 1013904223) % 2**32
        return seed / 4294967296
    return r


def shuffle(a, r):
    for i in range(len(a) - 1, 0, -1):
        j = int(r() * (i + 1))
        a[i], a[j] = a[j], a[i]


def pick(seed, bank, byid, used):
    """One sprint/hurdles, one middle/distance/road, one jump, one throw, one wildcard; balanced men/women."""
    r = rng(seed)
    order = [q["id"] for q in bank if q["id"] not in used]
    shuffle(order, r)
    chosen = []
    for b in BUCKETS:
        chosen.append(next((i for i in order if i not in chosen and byid[i]["group"] in b), None)
                      or next(i for i in order if i not in chosen))
    men = sum(byid[i]["gender"] == "Men" for i in chosen)
    want = "Women" if men > 2 else "Men" if men < 2 else None
    chosen.append(next((i for i in order if i not in chosen and (not want or byid[i]["gender"] == want)), None)
                  or next(i for i in order if i not in chosen))
    shuffle(chosen, r)
    return chosen


def build(today=None):
    bank = json.load(open(os.path.join(DATA, "questions.json"), encoding="utf-8"))
    byid = {q["id"]: q for q in bank}
    path = os.path.join(DATA, "schedule.json")
    old = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else []
    today = today or datetime.datetime.now(datetime.timezone.utc).date()
    frozen = (today - START).days + 2          # tomorrow's day number
    days = old[:frozen]
    for d in days:
        missing = [i for i in d["ids"] if i not in byid]
        if missing:
            raise SystemExit(f'day {d["day"]} was already played but its questions are gone from the bank: {missing}')
    cycle = days[-1]["cycle"] if days else 1
    used = {i for d in days if d["cycle"] == cycle for i in d["ids"]}
    for n in range(len(days) + 1, frozen + AHEAD + 1):
        if len(bank) - len(used & byid.keys()) < 5:
            cycle, used = cycle + 1, set()
        ids = pick(n * 7919 + 13, bank, byid, used)
        used.update(ids)
        days.append({"day": n, "cycle": cycle, "ids": ids})
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("[\n" + ",\n".join(json.dumps(d) for d in days) + "\n]\n")
    return days, frozen


if __name__ == "__main__":
    days, frozen = build()
    print(f"schedule: {len(days)} days, days 1-{frozen} frozen")
