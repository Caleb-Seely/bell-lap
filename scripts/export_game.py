"""Build the playable page: src/page.html + the bank (as a compact BANK constant) + src/game.js -> site/index.html"""
import json, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
qs = json.load(open(os.path.join(ROOT, "data", "questions.json")))
out = []
for q in qs:
    w = q["wr_before"]
    item = {"id": q["id"], "label": q["label"],
            "ctx": ("Olympic final" if q["championship"] == "Olympic Games" else "World Championships final") + f' · {q["city"]} {q["year"]}',
            "group": q["group"], "g": q["gender"][0], "fmt": q["fmt"], "clue": q["clue_index"],
            "results": [[r[0], r[1], r[2], round(r[3], 2)] for r in q["results"]]}
    if q["field"]: item["field"] = q["field"]
    if q["partial"]: item["partial"] = 1
    if w: item["wr"] = [round(w["value"], 2), w["holder"], w["year"]]
    if q["wr_broken"]: item["wrBroken"] = 1
    out.append(item)
bank = "const BANK=" + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";\n"
page = open(os.path.join(ROOT, "src", "page.html"), encoding="utf-8").read()
game = open(os.path.join(ROOT, "src", "game.js"), encoding="utf-8").read()
os.makedirs(os.path.join(ROOT, "site"), exist_ok=True)
with open(os.path.join(ROOT, "site", "index.html"), "w", encoding="utf-8") as fh:
    fh.write(page + "\n<script>\n" + bank + game + "</script>\n")
print("site/index.html written")
