"""Build the playable page: src/page.html + the bank (BANK) + daily sets (SCHEDULE) + src/game.js -> site/index.html,
plus src/public/* (icons, share image, robots.txt, llms.txt) and a sitemap -> site/"""
import datetime, json, os, random, shutil
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
qs = json.load(open(os.path.join(ROOT, "data", "questions.json")))
CTX = {"Olympic Games": "Olympic final", "World Championships": "World Championships final",
       "NCAA Indoor Championships": "NCAA Indoor final", "NCAA Outdoor Championships": "NCAA Outdoor final"}
out = []
for q in qs:
    w = q["wr_before"]
    item = {"id": q["id"], "label": q["label"],
            "ctx": CTX[q["championship"]] + f' · {q["city"]} {q["year"]}',
            "group": q["group"], "g": q["gender"][0], "fmt": q["fmt"], "clue": q["clue_index"],
            "results": [[r[0], r[1], r[2], round(r[3], 2)] for r in q["results"]], "src": q["source_page"]}
    if q["field"]: item["field"] = q["field"]
    if q["partial"]: item["partial"] = 1
    if q["cut"]: item["cut"] = 1
    if q["ncaa"]: item["ncaa"] = 1
    if w: item["wr"] = [round(w["value"], 2), w["holder"], w["year"]] + (["CR"] if w.get("kind") == "CR" else [])
    if q["wr_broken"]: item["wrBroken"] = 1
    out.append(item)
# The bank is scrambled so answers and athlete names can't be read with View Source or Ctrl-F: every printable ASCII
# character is swapped for another by a fixed shuffle. A one-for-one swap keeps the text as repetitive as plain JSON,
# so it still compresses on the wire (a stream cipher made the page ~4x bigger). Decoded on load; devtools can still get it.
text = json.dumps(out, ensure_ascii=False, separators=(",", ":"))
ascii_ = [chr(c) for c in range(32, 127)]
key = ascii_[:]
random.Random(0x6C61700A).shuffle(key)
swap = dict(zip(ascii_, key))
scrambled = "".join(swap.get(c, c) for c in text)
js_str = lambda v: json.dumps(v, ensure_ascii=False).replace("<", "\\u003c")
bank = ("const BANK=((k,s)=>{const d={};for(let i=0;i<95;i++)d[k[i]]=String.fromCharCode(32+i);"
        "return JSON.parse(s.replace(/[ -~]/g,c=>d[c]));})(%s,%s);\n") % (js_str("".join(key)), js_str(scrambled))
index = {q["id"]: k for k, q in enumerate(qs)}
days = json.load(open(os.path.join(ROOT, "data", "schedule.json"), encoding="utf-8"))
bank += "const SCHEDULE=" + json.dumps([[[index[i] for i in d[m]] for m in ("ids", "warmup", "bell")] for d in days], separators=(",", ":")) + ";\n"
page = open(os.path.join(ROOT, "src", "page.html"), encoding="utf-8").read()
game = open(os.path.join(ROOT, "src", "game.js"), encoding="utf-8").read()
os.makedirs(os.path.join(ROOT, "site"), exist_ok=True)
with open(os.path.join(ROOT, "site", "index.html"), "w", encoding="utf-8") as fh:
    fh.write(page + "\n<script>\n" + bank + game + "</script>\n")
pub = os.path.join(ROOT, "src", "public")
for f in sorted(os.listdir(pub)):
    shutil.copy(os.path.join(pub, f), os.path.join(ROOT, "site", f))
with open(os.path.join(ROOT, "site", "sitemap.xml"), "w", encoding="utf-8") as fh:
    fh.write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
             f'  <url><loc>https://bell-lap.vercel.app/</loc><lastmod>{datetime.date.today().isoformat()}</lastmod><changefreq>daily</changefreq></url>\n'
             '  <url><loc>https://bell-lap.vercel.app/how-to-play</loc></url>\n</urlset>\n')
print("site/index.html written")
