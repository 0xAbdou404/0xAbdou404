# Setting up your neofetch-style GitHub profile

Your profile card is a pre-rendered SVG (dark + light). GitHub shows the right
one automatically based on the viewer's theme. Everything you need is in this
folder.

## What actually gets uploaded to GitHub

Only three files are required — the SVGs already have the portrait embedded, so
you do **not** need the PNGs:

```
README.md
assets/dark_mode.svg
assets/light_mode.svg
```

The rest (`generate.py`, `config.json`, `photo_to_ascii.py`, the PNGs) are just
the "source" so you can regenerate the card later. Keep them, but they don't
have to be in the profile repo.

## Step 1 — Create the special profile repo

1. Go to https://github.com/new
2. Set **Repository name** to your username, spelled **exactly** the same.
   If your username is `janedoe`, the repo must be `janedoe/janedoe`.
   (GitHub will show a little "✨ You found a secret!" note when you get it right.)
3. Set it to **Public**.
4. Tick **Add a README file**.
5. Click **Create repository**.

## Step 2 — Add the files (easiest: web upload)

1. In your new repo click **Add file ▸ Upload files**.
2. Drag in `README.md`.
3. Drag in the whole `assets` folder (or create an `assets` folder and drop the
   two `*_mode.svg` files inside it). The paths must stay `assets/dark_mode.svg`
   and `assets/light_mode.svg`.
4. **Commit changes.**

Prefer git? From this folder:

```bash
git init
git add README.md assets/dark_mode.svg assets/light_mode.svg
git commit -m "neofetch profile"
git branch -M main
git remote add origin https://github.com/<username>/<username>.git
git push -u origin main
```

Visit `github.com/<username>` — the card shows on your profile.

## Step 3 — Editing it later

Open `config.json`, change any text (name, links, stats, interests), then:

```bash
pip install pycairo pillow      # one-time
python3 generate.py             # rewrites assets/dark_mode.svg + light_mode.svg
```

Re-upload the two SVGs. That's it. If you'd rather not run Python, just send the
updated details to Claude and ask for freshly regenerated SVGs.

## Swapping the portrait

Put your ASCII-art image next to the scripts and re-run the recolor step (Claude
can do this for you), or replace `assets/portrait_dark.png` /
`assets/portrait_light.png` and re-run `generate.py`.

## Notes

- The stats (repos, commits, lines of code) are **static** numbers you set in
  `config.json` — update them whenever you like.
- Want them to auto-update instead? That needs a GitHub Actions workflow; ask
  Claude to set up the automated version.
