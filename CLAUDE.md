# Bell-Lap

A daily guessing game for track and field fans. Each day has five championship finals. For each one the player sees the event and a clue (a slower finisher's mark) and makes **one guess** at the winning time or distance. Points depend on how close the guess is, up to 1,000 a round and 5,000 a day. The reveal places the guess among the real field, and a share line shows coloured squares per round.

## Layout

```
data/raw/*.txt        Source of truth: one file per championship (see format below)
data/questions.json   Built bank: one object per final (generated, committed)
data/wr_history.json  World record per event, going into each championship and set in its finals (generated)
data/review.csv       Items to check by hand (generated)
data/schedule.json    Each day's five questions (generated; days already played are frozen, so commit it)
data/bell-lap-bank.xlsx  Review workbook (generated with `sh build.sh --xlsx`)
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

Build everything with `sh build.sh`. Only Python 3's standard library is needed (openpyxl only for `--xlsx`).

## Raw data format

```
#CH 2024-OG|Olympic Games|Paris|2024
@M100                      <- M/W + event code
WR|9.58|Usain Bolt|2009    <- world record going into the championship
1|Noah Lyles|USA|9.79|     <- place|athlete|country|mark|"WR" if a world record was set
```

Event codes: 100 200 400 800 1500 5000 10000 marathon 100H 110H 400H 3000SC HJ PV LJ TJ SP DT HT JT. Times are written as shown (9.79, 1:41.19, 13:13.66, 2:06:26); field marks are plain metres. Tied places repeat. DNF/DNS/DQ/no-mark athletes are left out. Fields with more than 20 finishers (marathons, some 10,000 m) list places 1–10 plus the last finisher with their real place.

Current bank: 304 finals, covering every individual event at the 2016, 2020 and 2024 Olympics and the 2017, 2019, 2022, 2023 and 2025 World Championships. Relays, race walks and combined events are left out. Collected from each event's Wikipedia page in October 2026 (`source_page` in questions.json; the reveal links to it and the footer credits Wikipedia, CC BY-SA 4.0). **Not checked against World Athletics results** (`verified: false` everywhere). Unverified finals are fine to play.

## Game decisions (keep unless asked to change)

- **One guess per final.** A second guess with a higher/lower hint was tried and removed.
- **Clue = last finisher**, shown only as a popup ("8th place" over "Name | mark") from a "Hint" button in the header during a guess. Free: no points cost or share marker. Exceptions:
  - If the last finisher was far behind (an injury, e.g. Ta Lou-Smith 13.84 in the Paris 100 m), the clue is the next one up. "Far behind" means the last gap is more than 3× the typical gap and more than half the rest of the field's spread.
  - Partial (big) fields use 10th place.
  
  Showing the world record as a second clue was tried. It made typing in the world record the best strategy, so it was dropped.
- **Scoring is deliberately generous** ("big numbers feel good"). `points = 1000 / (1 + e²)`, where `e = |guess − winner| / tolerance` and `tolerance = winner × max(4%, |clue − winner| / winner)`. The scoring is not explained in the UI.
- **Daily set:** one sprint/hurdles, one middle/distance/road, one jump, one throw and one wildcard, balanced men/women. Days walk through the bank without repeats (about 60 days per cycle). Day 1 = 2026-10-11. Sets come from `data/schedule.json`: days up to tomorrow (UTC) never change, so adding or removing questions only affects days nobody has played. Removing a question that a played day uses fails the build. The page wraps around if the schedule (built 400 days ahead on every build) runs out.
- **Input:** free text. Dots work in place of colons. Ambiguous input like "1.57" is read as whichever meaning is closer to the clue mark (1:57).
- **Typo guard:** a guess more than ~1.5x from the clue mark (the real winner is never more than 26% away) shows "Did you mean …?" with the digits re-read (6759 → 67.59) and needs a second press ("Sure?") to submit.
- **Reveal:** winner, points, a placing line ("That mark would place 4th of 8", never "you finished": the player didn't race), a red "straight" with the finish line on the right (winner at the finish, clue runner at the left), then the Next button. Below it a collapsed "Results" section holds the full results board (every finisher we have, guess slotted in, world record going in as a row; big road fields show "N more" for the unlisted places), the old-record note if a record fell, and a link to the event's Wikipedia page. A record also shows a "New world record" badge. No "% off".
- **Design:** minimal and mobile-first. Off-white or charcoal background, one track-red accent, Barlow Condensed / Barlow / IBM Plex Mono. The five rounds are shown as lane boxes. Avoid adding explanatory copy.
- Progress is stored in localStorage per day (key `pf9-day-YYYY-MM-DD`). Bump the prefix if the saved-state shape changes.

## Known data questions

- `data/review.csv`: 45 far-behind last places (handled automatically, worth a glance), 16 short sprint fields, Ortega's shared bronze (Doha 110mH), Amusan's wind-aided 12.06 (Eugene, not a record), and Tiffany Porter's Rio mark (12.76, unconfirmed).
- The women's marathon record uses the outright mark (Radcliffe 2:15:25 until Kosgei 2019), not the women-only one.
- Chepngetich's 2:09:56 is listed as the record going into 2025, despite her 2025 doping suspension. Decided to keep it.
- Results stand as Wikipedia showed them, including later reallocations. Some athletes have since been sanctioned.

## Next up (ideas, not started)

1. Verify the bank against World Athletics results and mark finals verified.
2. Load one day's questions at a time instead of embedding the whole bank, if answers in the page source become a problem.
3. Add more championships (earlier Olympics/Worlds, Diamond League finals, NCAA). Add a raw file and rebuild.
4. Streaks and stats across days. Accounts or a database only if leaderboards are wanted.
