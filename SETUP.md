# Setting up your self-updating neofetch profile

Your profile card is a pre-rendered SVG (dark + light — GitHub picks the right
one for the viewer's theme). A GitHub Action re-fetches your real stats and
rebuilds the card automatically, so you never hand-edit the numbers.

- **`config.json`** — the text fields (OS, Uptime, Host, Shell, IDE, Languages,
  Interests, Contact). You edit these.
- **`update_stats.py`** — queries the GitHub API for repos / stars / commits /
  followers / lines-of-code and writes them into `config.json`.
- **`generate.py`** — renders `assets/dark_mode.svg` + `light_mode.svg`.
- **`.github/workflows/build.yaml`** — runs the two scripts on a schedule.

Because the stats update in CI, **push the whole folder** to your repo (not just
the SVGs) — the Action needs the scripts, the portrait PNGs, and the `cache/`
folder to run.

---

## Step 1 — Create the special profile repo

1. Go to https://github.com/new
2. Set **Repository name** to your username, spelled **exactly**: `0xAbdou404`.
   The repo must be `0xAbdou404/0xAbdou404` (GitHub shows a "✨ You found a
   secret!" note when you get it right).
3. Set it **Public**.
4. Create it. (This repo is already created and cloned to this folder.)

## Step 2 — Push this folder

Origin is already configured. From this folder:

```bash
git push origin main
```

Visit `github.com/0xAbdou404` — the card shows on your profile right away, using
the current numbers in `config.json`. Next we make those numbers self-updating.

## Step 3 — Create the access token

The Action needs a token to read your GitHub data. Use a **fine-grained** token
with **read-only** scopes — nothing more.

1. Open https://github.com/settings/personal-access-tokens/new
   (Settings ▸ Developer settings ▸ Personal access tokens ▸ Fine-grained tokens
   ▸ Generate new token).
2. **Token name:** `profile-card`
3. **Expiration:** pick a length you're comfortable with (e.g. 90 days or 1 year).
   You'll need to regenerate it when it expires.
4. **Resource owner:** your account (`0xAbdou404`).
5. **Repository access:** *All repositories* — so lines-of-code can be counted
   across everything you own. (Pick *Public repositories* only if you want the
   numbers to exclude private work.)
6. **Permissions ▸ Repository permissions:**
   - **Contents** → Read-only
   - **Metadata** → Read-only (selected automatically)
   - **Commit statuses** → Read-only *(optional)*
7. **Permissions ▸ Account permissions:**
   - **Followers** → Read-only
   - **Starring** → Read-only
8. **Generate token** and **copy it now** — GitHub shows it only once.

## Step 4 — Add the token as a repo secret

1. In your `0xAbdou404/0xAbdou404` repo: **Settings ▸ Secrets and variables ▸
   Actions ▸ New repository secret**.
2. **Name:** `ACCESS_TOKEN` (exactly).
3. **Secret:** paste the token.
4. **Add secret.**

You do **not** need a `USER_NAME` secret — the workflow reads the repo owner
automatically.

## Step 5 — Allow the Action to commit

**Settings ▸ Actions ▸ General ▸ Workflow permissions** → select
**Read and write permissions** → **Save**. This lets the bot push the refreshed
card back to the repo.

## Step 6 — Run it once now

1. Go to the **Actions** tab.
2. Pick **Update profile card** in the left sidebar.
3. Click **Run workflow ▸ Run workflow**.
4. Wait ~1–2 minutes. It fetches your real numbers, rebuilds the SVGs, and
   commits them with a `chore: refresh profile stats` message.

After that it runs on its own **every day at 04:00 UTC**, plus whenever you push
a change to the scripts. You can always trigger it manually from the Actions tab.

---

## Editing the card later

For the **text** fields (OS, Interests, links, etc.), edit `config.json` and
push — the next Action run re-renders. To preview locally:

```bash
pip install pycairo          # one-time
python3 generate.py          # rewrites the two SVGs from config.json
```

You don't touch the **stats** block — the Action overwrites it every run.

## Swapping the portrait

Replace `assets/portrait_dark.png` / `assets/portrait_light.png` (same size),
then re-run `generate.py` — or send Claude a new image to recolor.

## Token scopes, at a glance

Read-only: Contents, Metadata, Commit statuses (repo) · Followers, Starring
(account). No write scopes, no admin, no delete. If a run fails, it's almost
always the token.

## Troubleshooting

- **`ACCESS_TOKEN is not set`** in the log → the secret is missing or misnamed.
- **`Permission ... denied` / 403 on the commit step** → do Step 5 (Read and
  write permissions).
- **Lines of code look low / zero** → the token can't see those repos; set
  repository access to *All repositories* (Step 3.5).
- **Numbers include private repos and you don't want that** → regenerate the
  token with *Public repositories* access only.
- **Nothing happens on a normal push** → expected. The Action only rebuilds on a
  push when you change the scripts; otherwise it's the daily schedule or the
  manual button.
