# Setup plan for Claude Code

Goal: get Photo Finish running on this computer, under git, on GitHub, with the game published on GitHub Pages. Do the steps in order, check each one, and stop to ask me where it says **Ask**.

Read `CLAUDE.md` first. It explains the project and the decisions behind it.

## 1. Check the folder

- This folder should contain `build.sh`, `data/raw/` (8 files), `scripts/`, `src/`, `.github/workflows/pages.yml`, `README.md`, `CLAUDE.md` and this file.
- If it is still inside a zip or nested one level deep (e.g. `photo-finish/photo-finish/`), move it so the project root is the folder I opened you in. **Ask** before moving anything outside this folder.

## 2. Check the tools

- `python3 --version` must be 3.9 or newer. The build uses only the standard library.
- `git --version`.
- `gh --version` and `gh auth status`. If `gh` is missing, tell me how to install it for my OS. If it's not logged in, ask me to run `gh auth login` myself; don't handle my credentials.
- Optional: `pip install openpyxl` is only needed for the spreadsheet (`sh build.sh --xlsx`).

## 3. Build and test locally

- Run `sh build.sh`. Expected output: `304 questions; 12 with a world record set in the final`, a review count line, and `site/index.html written`.
- Open `site/index.html` in my browser (`open` on macOS, `xdg-open` on Linux, `start` on Windows) and tell me to play one round. The page is self-contained, so no server is needed.
- If anything fails, fix it and explain what changed. Don't change game behaviour or data while doing this.

## 4. Put it under git

- `git init -b main`, then commit everything except what `.gitignore` excludes (`site/` is built, not committed).
- First commit message: `Photo Finish prototype and 2016–2025 question bank`.
- Check that `data/raw/*.txt`, `data/questions.json`, `data/wr_history.json`, `data/review.csv` and `data/photo-finish-bank.xlsx` are committed.

## 5. Create the GitHub repo

- **Ask** me for the repo name (suggest `photo-finish`) and whether it should be public or private.
  - GitHub Pages on a free account only works for **public** repos. If I choose private on a free plan, skip step 6 and tell me the options.
- `gh repo create <name> --<public|private> --source=. --remote=origin --push`.
- Show me the repo URL.

## 6. Publish the game on GitHub Pages

- Turn on Pages with GitHub Actions as the source: `gh api -X POST repos/{owner}/{repo}/pages -f build_type=workflow`. If it already exists, use `-X PUT` instead.
- The workflow in `.github/workflows/pages.yml` runs `sh build.sh` and deploys `site/` on every push to `main`. Trigger it with `gh workflow run pages.yml` if the first push didn't, then watch it with `gh run watch`.
- Give me the live URL (usually `https://<user>.github.io/<repo>/`) and confirm it loads.

## 7. Wrap up

- Summarise what was set up: local path, repo URL, live game URL.
- Suggest, but don't start, the first follow-ups from the "Next up" list in `CLAUDE.md`.
