# Sambad ePaper → PDF

A small Streamlit app that grabs every page of a Sambad ePaper edition and stitches them into one high-resolution PDF you can download in a click.

I built this because flipping through the ePaper page by page (and saving each image manually) got old fast. This just does it for you.

## What it does

1. You paste the edition URL, something like `https://sambadepaper.com/epaper/1/82/2026-09-20/1`
2. The app reads the listing page and figures out the real image link for every page (the site hides them behind a `show_pop()` click handler, so we recreate that).
3. It downloads all the pages in parallel, shows you a progress bar and a few thumbnails so you know it's working.
4. Once everything's downloaded, it bundles the pages into a single PDF and gives you a download button.

That's it — no login, no browser automation, just a couple of HTTP requests per page.

## Running it locally

```powershell
# from this folder
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run streamlit_app.py
```

It'll open in your browser at `http://localhost:8501`.

## Deploying to Streamlit Cloud

1. Push this folder to a GitHub repo (make sure `streamlit_app.py`, `requirements.txt`, and `.streamlit/config.toml` are all included).
2. Go to [share.streamlit.io](https://share.streamlit.io), sign in, and click "New app".
3. Point it at your repo/branch and set the main file to `streamlit_app.py`.
4. Deploy — Streamlit Cloud installs everything from `requirements.txt` automatically and picks up the theme from `.streamlit/config.toml`.

## A couple of things to know

- If a page fails to download (site hiccup, changed markup, etc.), the app will tell you which page numbers failed instead of silently skipping them.
- You can tweak how many pages download at once from the sidebar — lower it if you're getting a lot of failures, since that usually means the site is rate-limiting you.
- This only works for Sambad ePaper edition URLs in the `/epaper/<edition>/<edcode>/<date>/<page>` format. If the site changes its page structure, the regex patterns near the top of `streamlit_app.py` are the first place to look.

## Files

- `streamlit_app.py` — the whole app
- `requirements.txt` — Python dependencies
- `.streamlit/config.toml` — theme/server config for Streamlit Cloud
