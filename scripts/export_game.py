"""Build the playable page: src/page.html + the bank (BANK) + daily sets (SCHEDULE) + src/game.js -> site/index.html,
plus src/public/* (icons, share image, robots.txt, llms.txt) and a sitemap -> site/"""
import base64, datetime, json, os, shutil
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
# The bank is scrambled (XOR with a fixed keystream, then base64) so answers and athlete names
# can't be read with View Source or Ctrl-F. It's decoded on load, so devtools can still get it.
raw = bytearray(json.dumps(out, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
x = SEED = 0x6C61700A
for k in range(len(raw)):
    x = (x * 1103515245 + 12345) & 0xFFFFFFFF
    raw[k] ^= x >> 24
bank = ("const BANK=(s=>{const b=Uint8Array.from(atob(s),c=>c.charCodeAt(0));let x=%d;"
        "for(let k=0;k<b.length;k++){x=(Math.imul(x,1103515245)+12345)>>>0;b[k]^=x>>>24;}"
        "return JSON.parse(new TextDecoder().decode(b));})(\"%s\");\n") % (SEED, base64.b64encode(raw).decode("ascii"))
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
             f'  <url><loc>https://bell-lap.vercel.app/</loc><lastmod>{datetime.date.today().isoformat()}</lastmod><changefreq>daily</changefreq></url>\n</urlset>\n')
print("site/index.html written")
