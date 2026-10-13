# Bell-Lap

A daily guessing game for track and field fans. Each day has five championship finals (Olympics, World Championships and NCAA Division I). For each one the player sees the event and a clue (a slower finisher's mark) and makes **one guess** at the winning time or distance. Points depend on how close the guess is, up to 1,000 a round and 5,000 a day. The reveal places the guess among the real field, and a share line shows coloured squares per round.

## Layout

```
data/raw/*.txt        Source of truth: one file per championship (see format below)
data/questions.json   Built bank: one object per final (generated, committed)
data/wr_history.json  World record per event, going into each championship and set in its finals (generated)
data/cr_history.json  Collegiate record progression per event (from scripts/fetch_cr.py; committed)
data/review.csv       Items to check by hand (generated)
data/schedule.json    Each day's five questions (generated; days already played are frozen, so commit it)
data/bell-lap-bank.xlsx  Review workbook (generated with `sh build.sh --xlsx`)
scripts/fetch_ncaa.py  Wikipedia -> data/raw/YYYY-NCAAI.txt / YYYY-NCAAO.txt (network; not part of build.sh)
scripts/fetch_cr.py   Wayback snapshots of Track & Field News collegiate record lists -> data/cr_history.json (network)
scripts/build.py      raw -> questions.json, wr_history.json, review.csv
scripts/schedule.py   questions.json -> schedule.json (freezes days up to tomorrow UTC, regenerates the rest)
scripts/export_game.py  questions.json + schedule.json + src/ -> site/index.html (`const BANK=...`, `const SCHEDULE=...`)
scripts/make_xlsx.py  questions.json -> review workbook
src/page.html         Page markup and CSS (tokens at the top, light + dark)
src/game.js           Game logic
site/index.html       Built, self-contained game. Not committed
vercel.json           Vercel build settings (`sh build.sh`, serves `site/`)
```

Live at https://bell-lap.vercel.app (Vercel's GitHub integration deploys every push to `main`). The share text links there (`SITE` in `src/game.js`). GitHub Pages was used at first and is turned off.

Analytics: Vercel Web Analytics (script tag in `src/page.html`, enabled in the Vercel dashboard under Analytics). `track()` in `src/game.js` sends three custom events with `mode` and `practice`: `Start` (first guess of a game), `Finish` (with `score`, plus `intervals` in Workout) and `Share` (Copy pressed). Custom events need a Vercel Pro plan; on Hobby only page views are recorded. No cookies.

Build everything with `sh build.sh`. Only Python 3's standard library is needed (openpyxl only for `--xlsx`).

## Raw data format

```
#CH 2024-OG|Olympic Games|Paris|2024
@M100                      <- M/W + event code
WR|9.58|Usain Bolt|2009    <- world record going into the championship
1|Noah Lyles|USA|9.79|     <- place|athlete|country|mark|"WR" if a world record was set
```

Event codes: 60 100 200 400 800 1500 mile 3000 5000 10000 marathon 60H 100H 110H 400H 3000SC HJ PV LJ TJ SP DT HT JT WT.
NCAA files use the school in place of the country, start with `#DATES`, and may have a `CUT` line under an event: the list stops at the scoring places, so the game doesn't state a field size ("would place 4th", "outside the top 8"). Times are written as shown (9.79, 1:41.19, 13:13.66, 2:06:26); field marks are plain metres. Tied places repeat. DNF/DNS/DQ/no-mark athletes are left out. Fields with more than 20 finishers (marathons, some 10,000 m) list places 1–10 plus the last finisher with their real place.

Current bank: 830 finals. 304 pro: every individual event at the 2016, 2020 and 2024 Olympics and the 2017, 2019, 2022, 2023 and 2025 World Championships. 526 NCAA Division I: indoor and outdoor 2016–2025 (no 2020: both cancelled), every individual event Wikipedia has a usable table for. Gaps: 2016–17 Indoor miss some men's events, 2021–22 Outdoor and 2022 Indoor have empty tables for some events. To add a year: `python3 scripts/fetch_ncaa.py 2026-2026`, check its warnings and `data/review.csv`, rebuild. Relays, race walks and combined events are left out. Collected from each event's Wikipedia page in October 2026 (`source_page` in questions.json; the reveal links to it and the footer credits Wikipedia, CC BY-SA 4.0). **Not checked against World Athletics results** (`verified: false` everywhere). Unverified finals are fine to play.

## Game decisions (keep unless asked to change)

- **Modes** (tabs under the header; last one used is remembered in `pf9-mode`):
  - **Warm-up:** multiple choice. The answer plus three decoys ~1.5% apart (jittered), answer in a random slot. 1000 for the right pick, 300/100/0 by how many slots off.
  - **Standard** (default): the original game, untimed free-text guess.
  - **Bell-Lap:** Standard rules with 60 seconds for all five. The clock runs only while a guess is open (paused on reveals) and is stored as a wall-clock start, so reloading or switching modes doesn't stop it. Unanswered finals score 0 when it hits zero.
  - **Workout:** endless finals in a daily order (every final not in today's other sets). Each final adds 15 s; unused time carries over (no cap). The run ends on an empty clock or a guess under 500 ("Missed split"). Score = intervals cleared (finals scoring 500+).
  - Timed modes open on a Start screen. Share text names the mode ("· Warm-up", "· 60 s", "· Workout").
- **One guess per final.** A second guess with a higher/lower hint was tried and removed.
- **Clue = last finisher**, shown only as a popup ("8th place" over "Name | mark") from a "Hint" button in the header during a guess. Free: no points cost or share marker. Exceptions:
  - If the last finisher was far behind (an injury, e.g. Ta Lou-Smith 13.84 in the Paris 100 m), the clue is the next one up. "Far behind" means the last gap is more than 3× the typical gap and more than half the rest of the field's spread.
  - Partial (big) fields use 10th place.
  - NCAA lists longer than 12 (outdoor field events and distance races list all 24) use 12th place, so the clue stays within ~26% of the winner like everywhere else.
  
  Showing the world record as a second clue was tried. It made typing in the world record the best strategy, so it was dropped.
- **Scoring is deliberately generous** ("big numbers feel good"). `points = 1000 / (1 + e²)`, where `e = |guess − winner| / tolerance` and `tolerance = winner × max(4%, |clue − winner| / winner)`. The scoring is not explained in the UI.
- **NCAA in daily sets:** at most two NCAA finals per set (usually two). Pro and NCAA finals cycle separately (`cycle` ~31 days, `ncycle` ~110 days). Workout and Practice draw from everything (Practice also caps NCAA at two).
- **Daily sets:** Standard, Warm-up and Bell-Lap each get their own five (one sprint/hurdles, one middle/distance/road, one jump, one throw and one wildcard, balanced men/women). Days walk through the bank with no repeats across modes (about 20 days per cycle). Day 1 = 2026-10-11. Standard days 1–4 predate the other modes and are unchanged. Sets come from `data/schedule.json`: days up to tomorrow (UTC) never change, so adding or removing questions only affects days nobody has played. Removing a question that a played day uses fails the build. The page wraps around if the schedule (built 400 days ahead on every build) runs out.
- **Input:** free text. Dots work in place of colons. Ambiguous input like "1.57" is read as whichever meaning is closer to the clue mark (1:57).
- **Typo guard:** a guess more than ~1.5x from the clue mark (the real winner is never more than 26% away) shows "Did you mean …?" with the digits re-read (6759 → 67.59) and needs a second press ("Sure?") to submit.
- **Reveal:** winner, points, a placing line ("That mark would place 4th of 8", never "you finished": the player didn't race), a red "straight" with the finish line on the right (winner at the finish, clue runner at the left), then the Next button. Below it a collapsed "Results" section holds the full results board (every finisher we have, guess slotted in, world record going in as a row; big road fields show "N more" for the unlisted places), the old-record note if a record fell, and a link to the event's Wikipedia page. A record also shows a "New world record" badge. No "% off".
- **Design:** minimal and mobile-first. Off-white or charcoal background, one track-red accent, Barlow Condensed / Barlow / IBM Plex Mono. The five rounds are shown as lane boxes. Avoid adding explanatory copy.
- Progress is stored in localStorage per mode and day (`pf9-day-YYYY-MM-DD` for Standard, `pf9-<mode>-YYYY-MM-DD` for the others). Bump the prefix if the saved-state shape changes. Each Workout run saves its order (`seq`), so a bank change can't reshuffle a run in progress, but it can change a day's Workout order before it's started.

## Known data questions

- `data/review.csv`: 45 far-behind last places (handled automatically, worth a glance), 16 short sprint fields, Ortega's shared bronze (Doha 110mH), Amusan's wind-aided 12.06 (Eugene, not a record), and Tiffany Porter's Rio mark (12.76, unconfirmed).
- The women's marathon record uses the outright mark (Radcliffe 2:15:25 until Kosgei 2019), not the women-only one.
- Chepngetich's 2:09:56 is listed as the record going into 2025, despite her 2025 doping suspension. Decided to keep it.
- Results stand as Wikipedia showed them, including later reallocations. Some athletes have since been sanctioned.
- NCAA: Wikipedia errors found by the order checks were verified against official Flash Results / TFRRS and fixed in `CORRECTIONS` in `scripts/fetch_ncaa.py` (7 so far, each with its source). Still flagged: 2023 Indoor women's high jump 15th/16th (no source found).
- NCAA finals show the **collegiate record going in** (row "CR", badge "New collegiate record"). Built from every monthly Wayback snapshot of T&FN's in-season record lists since 2015 (`cr_history.json`, each record with when it was first/last listed, so marks T&FN later dropped don't count). Record going in = best mark set before the meet that was still listed in the last snapshot before it. A final sets a record when the winner beats it and (the history has that mark at the meet, or the results note CR/CL, or the event isn't wind-affected outdoors), unless it already fell earlier at the same meet. Gap: no snapshots March 2017–July 2019, so a record set and broken inside that window is missing. `review.csv` `cr-mismatch` lists winners that beat the record without counting (wind-aided sprints/hurdles, a semifinal record).
- Tokyo is labelled "Tokyo 2021" (the year it was held), not the official "Tokyo 2020". Decided to keep it.

## Next up (ideas, not started)

1. Verify the bank against World Athletics results and mark finals verified. NCAA finals cite official Flash Results PDFs on Wikipedia, which could verify them automatically.
2. Load one day's questions at a time instead of embedding the whole bank, if answers in the page source become a problem.
3. Add more championships (earlier Olympics/Worlds, Diamond League finals, NCAA). Add a raw file and rebuild.
4. Streaks and stats across days. Accounts or a database only if leaderboards are wanted.
