# Photo Finish

A daily track and field guessing game. You get five championship finals, one guess at each winning mark, and up to 5,000 points.

```sh
sh build.sh            # rebuild the question bank and site/index.html
sh build.sh --xlsx     # also rebuild data/photo-finish-bank.xlsx (needs openpyxl)
open site/index.html   # play locally
```

The question bank is in `data/`. It holds 304 Olympic and World Championships finals from 2016 to 2025, with world record history. To add a championship, add a file to `data/raw/` in the same format and rebuild. Pushing to `main` deploys the game to GitHub Pages.

Results data comes from Wikipedia (CC BY-SA 4.0) and has not yet been checked against World Athletics results. See `CLAUDE.md` for how the game works and why.
