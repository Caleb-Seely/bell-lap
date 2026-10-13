# Bell-Lap

A daily track and field guessing game. You get five championship finals, one guess at each winning mark, and up to 5,000 points.

```sh
sh build.sh            # rebuild the question bank and site/index.html
sh build.sh --xlsx     # also rebuild data/bell-lap-bank.xlsx (needs openpyxl)
open site/index.html   # play locally
```

The question bank is in `data/`. It holds 1,089 finals from 2000 to 2025: Olympics, World Championships, World Indoors and NCAA Division I, each with the world, world indoor or collegiate record going in. New meets are collected with `scripts/fetch_pro.py` (Olympics, World Indoors) and `scripts/fetch_ncaa.py`. To add a championship, add a file to `data/raw/` in the same format and rebuild. Pushing to `main` deploys the game to https://bell-lap.vercel.app.

Results data comes from Wikipedia (CC BY-SA 4.0) and has not yet been checked against World Athletics results. See `CLAUDE.md` for how the game works and why.
